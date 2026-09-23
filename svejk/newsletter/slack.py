"""Slack: share karta + link na vydání (Incoming Webhook)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

from svejk.build.day_content import datum_design
from svejk.build.io import read_json
from svejk.build.nav import Edition, edition_pages_href
from svejk.build.og_image import share_cache_key, share_hero_abs_url
from svejk.newsletter.config import NewsletterConfig
from svejk.newsletter.notify import (
    edition_id,
    load_state,
    save_state,
    _edition_day_path,
    _find_edition,
    _find_edition_by_den,
    _latest_edition,
)


def _subject(day: dict[str, Any], *, datum_label: str) -> str:
    # stejná logika jako newsletter_subject — bez importu html (cyklus přes __init__)
    custom = " ".join((day.get("nwl_predmet") or "").split())
    if custom:
        return custom
    ucet = (day.get("dnesni_ucet") or "").split("\n", 1)[0].strip()
    if ucet:
        return ucet
    return f"Nové vydání · {datum_label}"


def webhook_url_from_env() -> str:
    return (os.environ.get("SLACK_WEBHOOK_URL") or "").strip()


def _image_reachable(image_url: str, *, timeout: int = 15) -> bool:
    """Slack image block vyžaduje veřejně stažitelnou URL (jinak invalid_blocks)."""
    url = (image_url or "").strip()
    if not url.startswith(("http://", "https://")):
        return False
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= int(resp.status) < 400
    except Exception:
        # některé CDN HEAD neumí — zkus krátký GET
        try:
            req = urllib.request.Request(
                url, method="GET", headers={"Range": "bytes=0-0"}
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return 200 <= int(resp.status) < 400
        except Exception:
            return False


def post_share_card(
    *,
    webhook_url: str,
    subject: str,
    edition_url: str,
    image_url: str,
    timeout: int = 30,
) -> dict[str, Any]:
    """Pošle do Slacku share kartu a odkaz na vydání."""
    title = (subject or "Poslušně hlásím").strip()
    payload = {
        "text": f"{title}\n{edition_url}",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{title}*\n<{edition_url}|Otevřít vydání>",
                },
            },
            {
                "type": "image",
                "image_url": image_url,
                "alt_text": title[:120],
            },
        ],
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return {"ok": True, "status": resp.status, "body": body}
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"Slack webhook {e.code}: {err}") from e


def _slack_payload_for_edition(
    edition: Edition,
    *,
    site_url: str,
    base_path: str,
) -> tuple[str, str, str]:
    day_path = _edition_day_path(edition)
    day = read_json(day_path) if day_path.is_file() else {}
    datum_label = datum_design(edition.datum_unl, day.get("den") or "")
    subject = _subject(day, datum_label=datum_label)
    href = edition_pages_href(
        edition.obdobi, edition.schuze, edition.datum_unl, base_path
    )
    edition_url = f"{site_url.rstrip('/')}{href}"
    zaver = (day.get("zaver") or "").strip()
    image_url = share_hero_abs_url(
        site_url,
        base_path,
        edition.datum_unl,
        version=share_cache_key(zaver) if zaver else "",
    )
    return subject, edition_url, image_url


def notify_edition_slack(
    edition: Edition,
    *,
    dry_run: bool = False,
    force: bool = False,
    base_path: str = "",
) -> dict[str, Any]:
    """Pošle share kartu vydání do Slacku (dedupe přes newsletter-state.json)."""
    webhook = webhook_url_from_env()
    eid = edition_id(edition)
    result: dict[str, Any] = {"edition_id": eid, "dry_run": dry_run}

    if not webhook and not dry_run:
        return {**result, "skipped": True, "reason": "chybí SLACK_WEBHOOK_URL"}

    state = load_state()
    if state.get("last_slack_id") == eid and not force:
        return {**result, "skipped": True, "reason": "už ve Slacku", "edition_id": eid}

    cfg = NewsletterConfig.from_env()
    subject, edition_url, image_url = _slack_payload_for_edition(
        edition, site_url=cfg.site_url, base_path=base_path
    )
    result.update(
        {
            "subject": subject,
            "edition_url": edition_url,
            "image_url": image_url,
        }
    )

    if dry_run:
        return result

    if not _image_reachable(image_url):
        return {
            **result,
            "skipped": True,
            "reason": "share obrázek ještě není na webu (Slack by vrátil invalid_blocks)",
            "image_url": image_url,
        }

    posted = post_share_card(
        webhook_url=webhook,
        subject=subject,
        edition_url=edition_url,
        image_url=image_url,
    )
    save_state(
        {
            **load_state(),
            "last_slack_id": eid,
            "last_slack_at": datetime.now(timezone.utc).isoformat(),
            "last_slack_subject": subject,
        }
    )
    result["posted"] = True
    result["slack"] = posted
    return result


def run_newsletter_slack(
    obdobi: int,
    *,
    schuze: int | None = None,
    den: str | None = None,
    dry_run: bool = False,
    force: bool = False,
    base_path: str = "",
) -> dict[str, Any]:
    """
    Pošle do Slacku share kartu posledního (nebo zadaného) vydání.
    Typicky po deployi webu, až je /share/… živé.
    """
    if den is not None:
        if schuze is None:
            return {"skipped": True, "reason": "u --den uveď --schuze"}
        edition = _find_edition_by_den(obdobi, schuze, den)
        if not edition:
            return {
                "skipped": True,
                "reason": f"schůze {schuze} nemá schválené vydání pro {den}",
            }
    elif schuze is not None:
        edition = _find_edition(obdobi, schuze)
        if not edition:
            return {"skipped": True, "reason": f"schůze {schuze} nemá schválené vydání"}
    else:
        state = load_state()
        drafted = (state.get("last_drafted_id") or "").strip()
        edition = None
        if drafted:
            # last_drafted_id = "2025/30/09.09.2026"
            parts = drafted.split("/")
            if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit():
                edition = _find_edition_by_den(int(parts[0]), int(parts[1]), parts[2])
        if edition is None:
            edition = _latest_edition(obdobi)
        if not edition:
            return {"skipped": True, "reason": "žádné vydání"}

    day_path = _edition_day_path(edition)
    if not day_path.is_file():
        return {
            "skipped": True,
            "reason": "vydání nemá data",
            "edition_id": edition_id(edition),
        }

    return notify_edition_slack(
        edition, dry_run=dry_run, force=force, base_path=base_path
    )
