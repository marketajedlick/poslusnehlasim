"""Ecomail REST API (https://api2.ecomailapp.cz)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from svejk.newsletter.config import (
    DEFAULT_ECOMAIL_LIST_ID,
    DEFAULT_ECOMAIL_SUBSCRIBE_LIST_ID,
    DEFAULT_ECOMAIL_SUBSCRIBE_LIST_ID_EN,
)

API_BASE = "https://api2.ecomailapp.cz"


def api_key_from_env() -> str:
    return (os.environ.get("ECOMAIL_API_KEY") or "").strip()


def list_id_from_env() -> int | None:
    """Seznam pro rozesílání kampaní (výchozí: dev/test)."""
    raw = (os.environ.get("ECOMAIL_LIST_ID") or DEFAULT_ECOMAIL_LIST_ID).strip()
    return int(raw) if raw.isdigit() else None


def subscribe_list_id_from_env() -> int | None:
    """Seznam pro zápis z webu a DOI (výchozí: dev/test)."""
    raw = (
        os.environ.get("ECOMAIL_SUBSCRIBE_LIST_ID")
        or DEFAULT_ECOMAIL_SUBSCRIBE_LIST_ID
    ).strip()
    return int(raw) if raw.isdigit() else None


def subscribe_list_id_en_from_env() -> int | None:
    """Anglický seznam pro zápis z webu a DOI."""
    raw = (
        os.environ.get("ECOMAIL_SUBSCRIBE_LIST_ID_EN")
        or DEFAULT_ECOMAIL_SUBSCRIBE_LIST_ID_EN
    ).strip()
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


def show_list(api_key: str, list_id: int) -> dict[str, Any]:
    return api_request(api_key, "GET", f"/lists/{list_id}")


def update_list(api_key: str, list_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    return api_request(api_key, "PUT", f"/lists/{list_id}", payload=payload)


def list_templates(api_key: str) -> list[dict[str, Any]]:
    data = api_request(api_key, "GET", "/templates")
    return data if isinstance(data, list) else []


def create_template(
    api_key: str,
    *,
    name: str,
    html: str,
    inline_css: bool = True,
) -> dict[str, Any]:
    return api_request(
        api_key,
        "POST",
        "/templates",
        payload={"name": name, "html": html, "inline_css": inline_css},
    )


def update_template(
    api_key: str,
    template_id: int,
    *,
    name: str,
    html: str,
    inline_css: bool = True,
) -> dict[str, Any]:
    return api_request(
        api_key,
        "PUT",
        f"/templates/{template_id}",
        payload={"name": name, "html": html, "inline_css": inline_css},
    )


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
            "skip_confirmation": False,
        },
    )


def create_campaign(
    *,
    api_key: str,
    list_id: int,
    subject: str,
    html_body: str,
    plain_body: str = "",
    from_name: str,
    from_email: str,
    reply_to: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "title": subject,
        "from_name": from_name,
        "from_email": from_email,
        "reply_to": reply_to,
        "subject": subject,
        "html_text": html_body,
        "recepient_lists": [list_id],
    }
    if plain_body.strip():
        payload["plain_text"] = plain_body
    created = api_request(
        api_key,
        "POST",
        "/campaigns",
        payload=payload,
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
    plain_body: str = "",
    from_name: str,
    from_email: str,
    reply_to: str,
) -> dict[str, Any]:
    created = create_campaign(
        api_key=api_key,
        list_id=list_id,
        subject=subject,
        html_body=html_body,
        plain_body=plain_body,
        from_name=from_name,
        from_email=from_email,
        reply_to=reply_to,
    )
    campaign_id = created["id"]
    sent = api_request(api_key, "POST", f"/campaigns/{campaign_id}/send")
    return {"id": campaign_id, "send": sent}


