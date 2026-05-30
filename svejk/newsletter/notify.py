"""Po exportu: rozeslat e-mail odběratelům přes Buttondown API (volitelné)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from svejk.build.io import read_json
from svejk.build.nav import Edition, list_obdobi_editions
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


def _build_email_body(edition: Edition, *, site_url: str, base_path: str) -> tuple[str, str]:
    from svejk.build.day_content import build_den_content, datum_design
    from svejk.build.nav import edition_pages_href

    paths = SchuzePaths.create(edition.obdobi, edition.schuze)
    d = datetime.strptime(edition.datum_unl, "%d.%m.%Y")
    day_path = paths.facts_by_day / f"{d.strftime('%Y-%m-%d')}.json"
    day = read_json(day_path) if day_path.is_file() else {}
    den = day.get("den") or ""
    content = build_den_content(day_path, paths)
    title = datum_design(edition.datum_unl, den)
    href = edition_pages_href(
        edition.obdobi, edition.schuze, edition.datum_unl, base_path
    )
    url = f"{site_url.rstrip('/')}{href}"

    lines = [
        f"Vyšlo nové vydání: **{title}**",
        "",
        content.dnesni_ucet or "",
        "",
    ]
    for item in content.items:
        lines.append(f"• {item.nadpis}")
    zaver = (content.zaver_body or content.zaver or "").strip()
    if zaver:
        lines.extend(["", zaver])
    lines.extend(["", f"[Číst vydání na webu]({url})", "", "Odhlášení: odkaz v patičce každého e-mailu od Buttondown."])
    subject = f"Nové vydání · {title}"
    body = "\n".join(ln for ln in lines if ln is not None).strip()
    return subject, body


def _buttondown_send(*, api_key: str, subject: str, body: str) -> dict[str, Any]:
    payload = json.dumps(
        {"subject": subject, "body": body, "status": "sent"},
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://api.buttondown.email/v1/emails",
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Api-Key {api_key}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def run_newsletter_notify(
    obdobi: int,
    *,
    dry_run: bool = False,
    force: bool = False,
    base_path: str = "",
) -> dict[str, Any]:
    """
    Pokud je novější vydání než v newsletter-state.json, pošle e-mail přes Buttondown.
    E-maily odběratelů nejsou v repozitáři — drží je Buttondown (GDPR, double opt-in).
    """
    api_key = (os.environ.get("BUTTONDOWN_API_KEY") or "").strip()
    if not api_key and not dry_run:
        return {"skipped": True, "reason": "BUTTONDOWN_API_KEY není nastaven"}

    cfg = NewsletterConfig.from_env()
    latest = _latest_edition(obdobi)
    if not latest:
        return {"skipped": True, "reason": "žádné vydání"}

    eid = edition_id(latest)
    state = load_state()
    if state.get("last_notified_id") == eid and not force:
        return {"skipped": True, "reason": "už odesláno", "edition_id": eid}

    subject, body = _build_email_body(latest, site_url=cfg.site_url, base_path=base_path)
    result: dict[str, Any] = {
        "edition_id": eid,
        "subject": subject,
        "dry_run": dry_run,
    }

    if dry_run:
        result["skipped_send"] = True
        return result

    try:
        sent = _buttondown_send(api_key=api_key, subject=subject, body=body)
        result["buttondown"] = {"id": sent.get("id"), "status": sent.get("status")}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"Buttondown API {e.code}: {err_body}") from e

    save_state(
        {
            "last_notified_id": eid,
            "last_notified_at": datetime.now(timezone.utc).isoformat(),
            "last_subject": subject,
        }
    )
    result["notified"] = True
    return result
