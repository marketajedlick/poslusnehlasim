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
    from svejk.build.email_html import render_email_html

    return render_email_html(edition, site_url=site_url, base_path=base_path)


_DRAFTED_KEEP = 60
# Bezpečnostní strop: při výpadku stavu nezaplavit Ecomail koncepty celé historie.
_MAX_PENDING = 5


def _keep_last(mapping: dict[str, Any], n: int) -> dict[str, Any]:
    keys = sorted(mapping, key=lambda k: _id_sort_key(k))[-n:]
    return {k: mapping[k] for k in keys}


def _id_sort_key(eid: str) -> tuple[datetime, int]:
    """Chronologické pořadí edition_id "obdobi/schuze/DD.MM.RRRR"."""
    try:
        _, schuze_s, datum = eid.split("/", 2)
        return datetime.strptime(datum, "%d.%m.%Y"), int(schuze_s)
    except ValueError:
        return datetime.min, 0


def _drafted_ids(state: dict[str, Any]) -> list[str]:
    ids = [str(x) for x in (state.get("drafted_ids") or [])]
    last = (state.get("last_drafted_id") or "").strip()
    if last and last not in ids:
        ids.append(last)
    return ids


def _pending_editions(obdobi: int, state: dict[str, Any]) -> list[Edition]:
    """Schválená vydání po posledním konceptu, která koncept ještě nemají.

    Publikace více dnů najednou (např. 20. a 21. 10.) musí dát koncept každému dni,
    ne jen poslednímu.
    """
    editions = list(list_approved_editions(obdobi))
    if not editions:
        return []
    drafted = set(_drafted_ids(state))
    last = (state.get("last_drafted_id") or "").strip()
    ids = [edition_id(e) for e in editions]
    if last in ids:
        pending = [e for e in editions[ids.index(last) + 1 :] if edition_id(e) not in drafted]
    else:
        pending = [editions[-1]] if edition_id(editions[-1]) not in drafted else []
    return pending[-_MAX_PENDING:]


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
    Bez --schuze projde všechna schválená vydání od posledního konceptu (chronologicky).
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

    if den is not None:
        if schuze is None:
            return {"skipped": True, "reason": "u --den uveď --schuze"}
        latest = _find_edition_by_den(obdobi, schuze, den)
        if not latest:
            return {
                "skipped": True,
                "reason": f"schůze {schuze} nemá schválené vydání pro {den}",
            }
        targets = [latest]
    elif schuze is not None:
        latest = _find_edition(obdobi, schuze)
        if not latest:
            return {"skipped": True, "reason": f"schůze {schuze} nemá schválené vydání"}
        targets = [latest]
    elif force:
        latest = _latest_edition(obdobi)
        targets = [latest] if latest else []
    else:
        latest = _latest_edition(obdobi)
        targets = _pending_editions(obdobi, load_state())
        if latest and not targets:
            return {"skipped": True, "reason": "už vytvořeno", "edition_id": edition_id(latest)}
    if not targets:
        return {"skipped": True, "reason": "žádné vydání"}

    results = [
        _notify_one(
            edition,
            dry_run=dry_run,
            force=force,
            base_path=base_path,
            out_dir=out_dir,
            api_key=api_key,
            list_id=list_id,
            from_name=from_name,
            from_email=from_email,
            reply_to=reply_to,
        )
        for edition in targets
    ]
    if len(results) == 1:
        return results[0]
    drafted = [r["edition_id"] for r in results if r.get("drafted")]
    return {
        "drafted": bool(drafted),
        "drafted_ids": drafted,
        "skipped": not drafted and not dry_run,
        "reason": "; ".join(
            f"{r.get('edition_id')}: {r['reason']}" for r in results if r.get("reason")
        ),
        "editions": results,
    }


def _notify_one(
    edition: Edition,
    *,
    dry_run: bool,
    force: bool,
    base_path: str,
    out_dir: str | Path | None,
    api_key: str,
    list_id: Any,
    from_name: str,
    from_email: str,
    reply_to: str,
) -> dict[str, Any]:
    cfg = NewsletterConfig.from_env()
    eid = edition_id(edition)
    state = load_state()
    if eid in _drafted_ids(state) and not force:
        return {"skipped": True, "reason": "už vytvořeno", "edition_id": eid}

    if not _edition_ready(edition):
        return {"skipped": True, "reason": "vydání nemá data pro web", "edition_id": eid}
    if not is_edition_approved(edition):
        return {
            "skipped": True,
            "reason": "vydání není v publish-approved.json",
            "edition_id": eid,
        }

    export_dir = Path(out_dir) if out_dir else None
    if export_dir is not None:
        page_path = _edition_export_path(edition, export_dir, base_path)
        if not page_path.is_file():
            return {
                "skipped": True,
                "reason": "stránka vydání není v exportu",
                "edition_id": eid,
                "expected": str(page_path),
            }

    subject, plain, html = _build_email_body(edition, site_url=cfg.site_url, base_path=base_path)
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

    try:
        created = create_campaign(
            api_key=api_key,
            list_id=list_id,
            subject=subject,
            title=f"{subject} [{eid}]",
            html_body=html,
            plain_body=plain,
            from_name=from_name,
            from_email=from_email,
            reply_to=reply_to,
        )
    except Exception as e:
        # Nezablokovat vydání: příští běh to zkusí znovu; chybu nechat ve stavu
        # a vyhodit, ať CLI skončí nenulově (CI z toho udělá ::error::).
        save_state(
            {
                **load_state(),
                "last_error_id": eid,
                "last_error_at": datetime.now(timezone.utc).isoformat(),
                "last_error": str(e)[:500],
            }
        )
        raise
    result["ecomail"] = created
    now_state = load_state()
    drafted_ids = [x for x in _drafted_ids(now_state) if x != eid] + [eid]
    if now_state.get("last_error_id") == eid:
        for k in ("last_error_id", "last_error_at", "last_error"):
            now_state.pop(k, None)
    prev_last = (now_state.get("last_drafted_id") or "").strip()
    save_state(
        {
            **now_state,
            # Jen dopředu: ruční --schuze na staré vydání nesmí vrátit značku zpět
            # (jinak by další běh draftoval všechno od té doby znovu).
            "last_drafted_id": max(prev_last, eid, key=_id_sort_key) if prev_last else eid,
            "last_drafted_at": datetime.now(timezone.utc).isoformat(),
            "last_subject": subject,
            "drafted_ids": drafted_ids[-_DRAFTED_KEEP:],
            # ID konceptu v Ecomailu pro každé vydání (dohledání duplicit / ruční úklid).
            "campaigns": _keep_last(
                {**(now_state.get("campaigns") or {}), eid: created.get("id")}, _DRAFTED_KEEP
            ),
        }
    )
    result["drafted"] = True

    # Slack až po deployi webu (share PNG musí být veřejně dostupné) —
    # viz pages.yml job `slack` / `./run-svejk.sh newsletter-slack`.
    return result
