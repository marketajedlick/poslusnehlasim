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


_SZIF_EM = re.compile(r"\bSZIFem\b", re.I)
_SZIF_U = re.compile(r"\bSZIFu\b", re.I)
_SZIF_POSKYTOVANYCH = re.compile(r"poskytovaných\s+SZIF\b", re.I)
_SZIF_POSTUPU = re.compile(r"postupu\s+SZIF\b", re.I)
_SZIF_SE_NETYKA = re.compile(r"který\s+se\s+SZIF\b", re.I)
_SZIF = re.compile(r"\bSZIF\b", re.I)


def expand_szif_for_display(text: str) -> str:
    """Zkratku SZIF nahradí srozumitelnou češtinou (stenové citace, kontext)."""
    if not text or "SZIF" not in text.upper():
        return text
    t = _SZIF_EM.sub("státním fondem na zemědělské dotace", text)
    t = _SZIF_U.sub("státního fondu na zemědělské dotace", t)
    t = _SZIF_POSKYTOVANYCH.sub(
        "poskytovaných státním fondem na zemědělské dotace", t
    )
    t = _SZIF_POSTUPU.sub("postupu státního fondu na zemědělské dotace", t)
    t = _SZIF_SE_NETYKA.sub(
        "který se státního fondu na zemědělské dotace", t
    )
    return _SZIF.sub("státní fond na zemědělské dotace", t)


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
