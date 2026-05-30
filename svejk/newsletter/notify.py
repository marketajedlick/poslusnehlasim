"""Po exportu: rozeslat e-mail odběratelům přes Ecomail API (volitelné)."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from svejk.build.io import read_json
from svejk.build.nav import Edition, list_obdobi_editions
from svejk.newsletter.api import api_key_from_env, list_id_from_env, send_campaign
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


def _plain_to_html(text: str) -> str:
    parts: list[str] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        line = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", line)
        line = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', line)
        if line.startswith("• "):
            parts.append(f"<li>{line[2:]}</li>")
        else:
            parts.append(f"<p>{line}</p>")
    body = "\n".join(parts)
    if "<li>" in body:
        body = re.sub(
            r"(<li>.*?</li>\n?)+",
            lambda m: f"<ul>{m.group(0)}</ul>",
            body,
            flags=re.DOTALL,
        )
    return body


def _build_email_body(edition: Edition, *, site_url: str, base_path: str) -> tuple[str, str, str]:
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
    lines.extend(
        [
            "",
            f"[Číst vydání na webu]({url})",
            "",
            "Odhlášení: odkaz v patičce každého e-mailu od Ecomailu.",
        ]
    )
    subject = f"Nové vydání · {title}"
    plain = "\n".join(ln for ln in lines if ln is not None).strip()
    html = _plain_to_html(plain)
    return subject, plain, html


def run_newsletter_notify(
    obdobi: int,
    *,
    dry_run: bool = False,
    force: bool = False,
    base_path: str = "",
) -> dict[str, Any]:
    """
    Pokud je novější vydání než v newsletter-state.json, pošle e-mail přes Ecomail.
    E-maily odběratelů nejsou v repozitáři — drží je Ecomail (GDPR, double opt-in).
    """
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
    if state.get("last_notified_id") == eid and not force:
        return {"skipped": True, "reason": "už odesláno", "edition_id": eid}

    subject, plain, html = _build_email_body(latest, site_url=cfg.site_url, base_path=base_path)
    result: dict[str, Any] = {
        "edition_id": eid,
        "subject": subject,
        "dry_run": dry_run,
    }

    if dry_run:
        result["skipped_send"] = True
        result["body_plain"] = plain
        return result

    sent = send_campaign(
        api_key=api_key,
        list_id=list_id,
        subject=subject,
        html_body=html,
        from_name=from_name,
        from_email=from_email,
        reply_to=reply_to,
    )
    result["ecomail"] = sent

    save_state(
        {
            "last_notified_id": eid,
            "last_notified_at": datetime.now(timezone.utc).isoformat(),
            "last_subject": subject,
        }
    )
    result["notified"] = True
    return result
