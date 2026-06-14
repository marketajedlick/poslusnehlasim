"""Obalí známé sněmovní pojmy HTML tooltipem."""

from __future__ import annotations

import re

from markupsafe import Markup, escape

from svejk.glossary import SLOVNIK_BOX, glossary_for_locale


def _pattern(phrase: str) -> re.Pattern[str]:
    parts = [re.escape(p) for p in phrase.split()]
    body = r"\s+".join(parts)
    return re.compile(rf"(?<![\w]){body}(?![\w])", re.IGNORECASE)


def _wrap(label: str, tip: str) -> str:
    safe_tip = escape(tip)
    return (
        f'<span class="term-tip" tabindex="0" role="term" '
        f'aria-label="{safe_tip}">{escape(label)}'
        f'<span class="term-tip-bubble" role="tooltip">{safe_tip}</span></span>'
    )


_HTML_SPLIT = re.compile(r"(<[^>]+>)")


def _markup_plain(text: str, *, locale: str = "cs") -> str:
    """Tooltipy jen v prostém textu (bez HTML tagů)."""
    if not text:
        return text

    glossary = glossary_for_locale(locale)
    matches: list[tuple[int, int, str, str]] = []
    for phrase, tip in glossary:
        for m in _pattern(phrase).finditer(text):
            matches.append((m.start(), m.end(), m.group(0), tip))

    if not matches:
        return text

    # Delší shoda má přednost; při stejné délce dřívější v glosáři.
    matches.sort(key=lambda x: (-(x[1] - x[0]), x[0]))
    used: list[tuple[int, int]] = []
    selected: list[tuple[int, int, str, str]] = []
    for start, end, label, tip in matches:
        if any(not (end <= s or start >= e) for s, e in used):
            continue
        used.append((start, end))
        selected.append((start, end, label, tip))

    out = text
    for start, end, label, tip in sorted(selected, key=lambda x: x[0], reverse=True):
        out = out[:start] + _wrap(label, tip) + out[end:]
    return out


def markup_glossary(text: str, *, locale: str = "cs") -> str:
    """Vrátí HTML s hover tooltipem u známých pojmů (bez překrývání)."""
    if not text:
        return text
    if "<" not in text:
        return _markup_plain(text, locale=locale)

    parts = _HTML_SPLIT.split(text)
    return "".join(
        part if part.startswith("<") else _markup_plain(part, locale=locale)
        for part in parts
    )


def glossary_markup(text: str, *, locale: str = "cs") -> Markup:
    return Markup(markup_glossary(text, locale=locale))


def _tip_for_phrase(phrase: str, *, locale: str = "cs") -> str | None:
    glossary = glossary_for_locale(locale)
    for gp, tip in glossary:
        if gp.lower() == phrase.lower():
            return tip
    pat = _pattern(phrase)
    for gp, tip in glossary:
        if pat.search(gp):
            return tip
    return None


def _needle_pattern(needle: str) -> re.Pattern[str]:
    """Shoda i na českých koncích (brzdách, pravidlech…)."""
    parts = [re.escape(p) for p in needle.split()]
    body = r"\s+".join(parts)
    return re.compile(rf"(?<![\w]){body}", re.IGNORECASE)


def svejkov_slovnik(*texts: str, limit: int = 6, locale: str = "cs") -> list[tuple[str, str]]:
    """Pojmy z textu dne pro box Švejkův slovník (název, vysvětlení)."""
    combined = "\n".join(t for t in texts if t)
    if not combined.strip():
        return []

    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    for label, needle in SLOVNIK_BOX:
        if len(found) >= limit:
            break
        if not _needle_pattern(needle).search(combined):
            continue
        tip = _tip_for_phrase(needle, locale=locale) or _tip_for_phrase(label, locale=locale)
        if not tip:
            continue
        key = label.lower()
        if key in seen:
            continue
        seen.add(key)
        found.append((label, tip))
    return found
