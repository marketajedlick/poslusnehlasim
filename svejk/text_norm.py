"""Normalizace textu: bez em a en pomlček (zakázané ve výstupech)."""

from __future__ import annotations

import re

_EM = "\u2014"  # —
_EN = "\u2013"  # –
_DLOUHE = _EM + _EN
_PATTERN = re.compile(f"[{_DLOUHE}]")


def ma_dlouhou_pomlcku(text: str) -> bool:
    return bool(text and _PATTERN.search(text))


def bez_dlouhych_pomlc(text: str) -> str:
    """Em/en pomlčka → čárka (mezi slovy) nebo ASCII pomlčka."""
    if not text:
        return text
    t = str(text)
    t = re.sub(r"\s+[—–]\s+", ", ", t)
    t = t.replace(_EM, "-").replace(_EN, "-")
    t = re.sub(r",\s*,+", ", ", t)
    t = re.sub(r",\s+([.!?])", r"\1", t)
    return t


def lcfirst_preserve_proper(text: str) -> str:
    """První písmeno malé, ale Sněmovna jako instituce zůstane."""
    if not text:
        return text
    if text.startswith("Sněmovna"):
        return text
    return text[0].lower() + text[1:]


def assert_bez_dlouhych_pomlc(text: str, *, kde: str = "") -> None:
    if ma_dlouhou_pomlcku(text):
        raise ValueError(f"Zakázaná dlouhá pomlčka ({kde}): {text[:80]!r}…")
