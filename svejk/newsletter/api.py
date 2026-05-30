"""Buttondown REST API (https://api.buttondown.com/v1)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

API_BASE = "https://api.buttondown.com/v1"


def api_key_from_env() -> str:
    return (os.environ.get("BUTTONDOWN_API_KEY") or "").strip()


def _headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Token {api_key}",
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
        raise RuntimeError(f"Buttondown API {e.code}: {err_body}") from e


def list_subscribers(api_key: str) -> dict[str, Any]:
    return api_request(api_key, "GET", "/subscribers")


def send_email(*, api_key: str, subject: str, body: str) -> dict[str, Any]:
    return api_request(
        api_key,
        "POST",
        "/emails",
        payload={"subject": subject, "body": body, "status": "sent"},
    )
