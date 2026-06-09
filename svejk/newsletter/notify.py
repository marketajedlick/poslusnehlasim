"""Po exportu: rozeslat e-mail odběratelům přes Ecomail API (volitelné)."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from svejk.build.nav import Edition, edition_pages_href, list_obdobi_editions
from svejk.newsletter.api import (
    api_key_from_env,
    create_campaign,
    list_id_from_env,
    send_campaign,
    send_campaigns_enabled_from_env,
)
from svejk.newsletter.config import NewsletterConfig
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
    editions = list_obdobi_editions(obdobi)
    return editions[-1] if editions else None


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
    dry_run: bool = False,
    force: bool = False,
    send: bool = False,
    base_path: str = "",
    out_dir: str | Path | None = None,
) -> dict[str, Any]:
    """
    Při novém vydání na webu vytvoří kampaň v Ecomailu (výchozí: jen koncept).
    S --send nebo ECOMAIL_SEND_CAMPAIGNS=1 kampaň i rozešle.
    Stav v newsletter-state.json brání duplicitám při opakovaném deployi.
    E-maily odběratelů nejsou v repozitáři — drží je Ecomail (GDPR, double opt-in).
    """
    draft_only = not send and not send_campaigns_enabled_from_env()
    api_key = api_key_from_env()
    list_id = list_id_from_env()
    from_email = (os.environ.get("ECOMAIL_FROM_EMAIL") or "").strip()
    from_name = (os.environ.get("ECOMAIL_FROM_NAME") or "Poslušně hlásím").strip()
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
    latest = _latest_edition(obdobi)
    if not latest:
        return {"skipped": True, "reason": "žádné vydání"}

    eid = edition_id(latest)
    state = load_state()
    if draft_only:
        if state.get("last_drafted_id") == eid and not force:
            return {"skipped": True, "reason": "už vytvořeno", "edition_id": eid}
    elif state.get("last_notified_id") == eid and not force:
        return {"skipped": True, "reason": "už odesláno", "edition_id": eid}
    if state.get("last_attempted_id") == eid and not force:
        return {
            "skipped": True,
            "reason": "už zkoušeno — použij --force pro nový pokus",
            "edition_id": eid,
        }

    if not _edition_ready(latest):
        return {"skipped": True, "reason": "vydání nemá data pro web", "edition_id": eid}

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
        "draft_only": draft_only,
    }

    if dry_run:
        result["skipped_send"] = True
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

    if draft_only:
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

    sent = send_campaign(
        api_key=api_key,
        list_id=list_id,
        subject=subject,
        html_body=html,
        plain_body=plain,
        from_name=from_name,
        from_email=from_email,
        reply_to=reply_to,
    )
    result["ecomail"] = sent

    save_state(
        {
            **load_state(),
            "last_notified_id": eid,
            "last_notified_at": datetime.now(timezone.utc).isoformat(),
            "last_subject": subject,
        }
    )
    result["notified"] = True
    return result
