"""Úryvky a věty ze stenoprotokolu — celé věty, ne useknuté regex okno."""

from __future__ import annotations

import re
from typing import Any


def rozdelit_vety_steno(text: str) -> list[str]:
    if not text or text.strip().lower() == "neautorizováno!":
        return []
    t = re.sub(r"\s+", " ", text.strip())
    parts = re.split(r"(?<=[.!?])\s+", t)
    return [p.strip() for p in parts if len(p.strip()) >= 25]


def _skore_vety(veta: str) -> int:
    low = veta.lower()
    sk = 0
    if re.search(r"\d", veta):
        sk += 4
    if re.search(r"\d{1,2}\s*\d{3}\s*(?:korun|Kč)|\d+\s*%", veta, re.I):
        sk += 3
    if any(
        w in low
        for w in (
            "klesne",
            "sníží",
            "zvýší",
            "zůstane",
            "platí",
            "od ledna",
            "živnost",
            "staví",
            "úřad",
            "občan",
            "poslanec",
            "návrh",
            "zamítn",
            "schvál",
        )
    ):
        sk += 2
    n = len(veta.split())
    if 12 <= n <= 35:
        sk += 2
    elif n < 8:
        sk -= 2
    if veta.endswith((".", "!", "?")):
        sk += 1
    if re.search(r"\b(z\.?\s*o\.?|novela|paragraf|článek)\b", low):
        sk -= 1
    return sk


def nejlepsi_vety(
    text: str,
    *,
    limit: int = 3,
    min_skore: int = 2,
) -> list[str]:
    scored: list[tuple[int, str]] = []
    for v in rozdelit_vety_steno(text):
        sk = _skore_vety(v)
        if sk >= min_skore:
            scored.append((sk, v))
    scored.sort(key=lambda x: (-x[0], -len(x[1])))
    out: list[str] = []
    seen: set[str] = set()
    for _, v in scored:
        key = v[:50].lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(v if v.endswith((".", "!", "?")) else f"{v}.")
        if len(out) >= limit:
            break
    return out


def fakty_z_steno_text(steno_text: str, steno_id: str, *, limit: int = 3) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for veta in nejlepsi_vety(steno_text, limit=limit):
        citace = veta[:200]
        out.append(
            {
                "text": veta[:320],
                "source": "steno",
                "steno_id": steno_id,
                "citace": citace,
            }
        )
    return out
