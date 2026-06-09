"""Ecomail REST API (https://api2.ecomailapp.cz)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from svejk.newsletter.config import DEFAULT_ECOMAIL_LIST_ID

API_BASE = "https://api2.ecomailapp.cz"


def api_key_from_env() -> str:
    return (os.environ.get("ECOMAIL_API_KEY") or "").strip()


def list_id_from_env() -> int | None:
    raw = (os.environ.get("ECOMAIL_LIST_ID") or DEFAULT_ECOMAIL_LIST_ID).strip()
    return int(raw) if raw.isdigit() else None


def _headers(api_key: str) -> dict[str, str]:
    return {
        "key": api_key,
        "Content-Type": "application/json",
    }


def api_request(
    api_key: str,
    method: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
    timeout: int = 60,
) -> Any:
    url = f"{API_BASE}{path}"
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers=_headers(api_key),
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"Ecomail API {e.code}: {err_body}") from e


def list_subscribers(api_key: str, list_id: int) -> dict[str, Any]:
    return api_request(api_key, "GET", f"/lists/{list_id}/subscribers")


def add_subscriber(
    api_key: str,
    list_id: int,
    email: str,
    *,
    source: str = "poslusnehlasim",
) -> dict[str, Any]:
    return api_request(
        api_key,
        "POST",
        f"/lists/{list_id}/subscribe",
        payload={
            "subscriber_data": {"email": email, "source": source},
            "trigger_autoresponders": True,
            "update_existing": True,
            "resubscribe": True,
        },
    )


def create_campaign(
    *,
    api_key: str,
    list_id: int,
    subject: str,
    html_body: str,
    from_name: str,
    from_email: str,
    reply_to: str,
) -> dict[str, Any]:
    created = api_request(
        api_key,
        "POST",
        "/campaigns",
        payload={
            "title": subject,
            "from_name": from_name,
            "from_email": from_email,
            "reply_to": reply_to,
            "subject": subject,
            "html_text": html_body,
            "recepient_lists": [list_id],
        },
    )
    campaign_id = created.get("id")
    if not campaign_id:
        raise RuntimeError(f"Ecomail API: chybí id kampaně v odpovědi: {created!r}")
    return {"id": campaign_id, "created": created}


def send_campaign(
    *,
    api_key: str,
    list_id: int,
    subject: str,
    html_body: str,
    from_name: str,
    from_email: str,
    reply_to: str,
) -> dict[str, Any]:
    created = create_campaign(
        api_key=api_key,
        list_id=list_id,
        subject=subject,
        html_body=html_body,
        from_name=from_name,
        from_email=from_email,
        reply_to=reply_to,
    )
    campaign_id = created["id"]
    sent = api_request(api_key, "POST", f"/campaigns/{campaign_id}/send")
    return {"id": campaign_id, "send": sent}


def send_campaigns_enabled_from_env() -> bool:
    return os.environ.get("ECOMAIL_SEND_CAMPAIGNS", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
