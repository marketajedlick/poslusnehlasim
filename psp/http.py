"""Minimal HTTP helpers (stdlib only)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


def get_bytes(
    url: str,
    *,
    timeout: float = 60,
    headers: dict[str, str] | None = None,
    method: str = "GET",
) -> bytes:
    req = urllib.request.Request(url, method=method, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def get_json(
    url: str,
    *,
    timeout: float = 60,
    headers: dict[str, str] | None = None,
) -> Any:
    return json.loads(get_bytes(url, timeout=timeout, headers=headers).decode("utf-8"))
