"""Po exportu: připravit koncept kampaně v Ecomailu (odeslání ručně v UI)."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from svejk.build.nav import Edition, edition_pages_href
from svejk.build.publish import is_edition_approved, list_approved_editions
from svejk.newsletter.api import (
    api_key_from_env,
    create_campaign,
    list_id_from_env,
)
from svejk.newsletter.config import NewsletterConfig
from svejk.strings import load_strings
from svejk.paths import SchuzePaths, processed_root

_STATE_NAME = "newsletter-state.json"


def _state_path() -> Path:
    return processed_root() / _STATE_NAME


def load_state() -> dict[str, Any]:
    p = _state_path()
    if not p.is_file():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def save_state(state: dict[str, Any]) -> None:
    p = _state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def edition_id(edition: Edition) -> str:
    return f"{edition.obdobi}/{edition.schuze}/{edition.datum_unl}"


def _latest_edition(obdobi: int) -> Edition | None:
    editions = list_approved_editions(obdobi)
    return editions[-1] if editions else None


def _find_edition(obdobi: int, schuze: int) -> Edition | None:
    """Vrátí nejnovější schválené vydání z konkrétní schůze."""
    editions = [e for e in list_approved_editions(obdobi) if e.schuze == schuze]
    return editions[-1] if editions else None


def _find_edition_by_den(obdobi: int, schuze: int, den: str) -> Edition | None:
    paths = SchuzePaths.create(obdobi, schuze)
    from svejk.timeline import resolve_schuze_den

    d_unl, day_path = resolve_schuze_den(paths, den)
    if not day_path.is_file():
        return None
    for edition in list_approved_editions(obdobi):
        if edition.schuze == schuze and edition.datum_unl == d_unl:
            return edition
    return None


def _edition_day_path(edition: Edition) -> Path:
    paths = SchuzePaths.create(edition.obdobi, edition.schuze)
    d = datetime.strptime(edition.datum_unl, "%d.%m.%Y")
    return paths.facts_by_day / f"{d.strftime('%Y-%m-%d')}.json"


def _edition_ready(edition: Edition) -> bool:
    """Vydání má data — odpovídá stránce, kterou export-pages zapíše na web."""
    return _edition_day_path(edition).is_file()


def _edition_export_path(edition: Edition, out_dir: Path, base_path: str) -> Path:
    href = edition_pages_href(
        edition.obdobi, edition.schuze, edition.datum_unl, base_path
    )
    rel = href.lstrip("/")
    return out_dir / rel


def _build_email_body(edition: Edition, *, site_url: str, base_path: str) -> tuple[str, str, str]:
    from svejk.build.html import render_email_html

    return render_email_html(edition, site_url=site_url, base_path=base_path)


def run_newsletter_notify(
    obdobi: int,
    *,
    schuze: int | None = None,
    den: str | None = None,
    dry_run: bool = False,
    force: bool = False,
    base_path: str = "",
    out_dir: str | Path | None = None,
) -> dict[str, Any]:
    """
    Při novém vydání na webu vytvoří koncept kampaně v Ecomailu.
    Odeslání vždy ručně v Ecomailu — API nikdy nerozešle.
    Stav v newsletter-state.json brání duplicitám při opakovaném deployi.
    E-maily odběratelů nejsou v repozitáři — drží je Ecomail (GDPR, double opt-in).
    Při --schuze se cílí konkrétní schůze místo nejnovějšího vydání.
    Při --den (s --schuze) konkrétní den schůze.
    """
    api_key = api_key_from_env()
    list_id = list_id_from_env()
    from_email = (os.environ.get("ECOMAIL_FROM_EMAIL") or "").strip()
    from_name = (os.environ.get("ECOMAIL_FROM_NAME") or load_strings()["brand"]["name"]).strip()
    reply_to = (os.environ.get("ECOMAIL_REPLY_TO") or from_email).strip()

    if not dry_run and (not api_key or not list_id or not from_email):
        missing = []
        if not api_key:
            missing.append("ECOMAIL_API_KEY")
        if not list_id:
            missing.append("ECOMAIL_LIST_ID")
        if not from_email:
            missing.append("ECOMAIL_FROM_EMAIL")
        return {"skipped": True, "reason": f"chybí: {', '.join(missing)}"}

    cfg = NewsletterConfig.from_env()
    if den is not None:
        if schuze is None:
            return {"skipped": True, "reason": "u --den uveď --schuze"}
        latest = _find_edition_by_den(obdobi, schuze, den)
        if not latest:
            return {
                "skipped": True,
                "reason": f"schůze {schuze} nemá schválené vydání pro {den}",
            }
    elif schuze is not None:
        latest = _find_edition(obdobi, schuze)
        if not latest:
            return {"skipped": True, "reason": f"schůze {schuze} nemá schválené vydání"}
    else:
        latest = _latest_edition(obdobi)
    if not latest:
        return {"skipped": True, "reason": "žádné vydání"}

    eid = edition_id(latest)
    state = load_state()
    if state.get("last_drafted_id") == eid and not force:
        return {"skipped": True, "reason": "už vytvořeno", "edition_id": eid}
    if state.get("last_attempted_id") == eid and not force:
        return {
            "skipped": True,
            "reason": "už zkoušeno — použij --force pro nový pokus",
            "edition_id": eid,
        }

    if not _edition_ready(latest):
        return {"skipped": True, "reason": "vydání nemá data pro web", "edition_id": eid}
    if not is_edition_approved(latest):
        return {
            "skipped": True,
            "reason": "vydání není v publish-approved.json",
            "edition_id": eid,
        }

    export_dir = Path(out_dir) if out_dir else None
    if export_dir is not None:
        page_path = _edition_export_path(latest, export_dir, base_path)
        if not page_path.is_file():
            return {
                "skipped": True,
                "reason": "stránka vydání není v exportu",
                "edition_id": eid,
                "expected": str(page_path),
            }

    subject, plain, html = _build_email_body(latest, site_url=cfg.site_url, base_path=base_path)
    result: dict[str, Any] = {
        "edition_id": eid,
        "subject": subject,
        "dry_run": dry_run,
    }

    if dry_run:
        result["body_plain"] = plain
        result["body_html"] = html
        return result

    save_state(
        {
            **state,
            "last_attempted_id": eid,
            "last_attempted_at": datetime.now(timezone.utc).isoformat(),
            "last_subject": subject,
        }
    )

    created = create_campaign(
        api_key=api_key,
        list_id=list_id,
        subject=subject,
        html_body=html,
        plain_body=plain,
        from_name=from_name,
        from_email=from_email,
        reply_to=reply_to,
    )
    result["ecomail"] = created
    save_state(
        {
            **load_state(),
            "last_drafted_id": eid,
            "last_drafted_at": datetime.now(timezone.utc).isoformat(),
            "last_subject": subject,
        }
    )
    result["drafted"] = True
    return result
