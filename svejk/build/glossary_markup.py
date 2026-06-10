"""Obalí známé sněmovní pojmy HTML tooltipem."""

from __future__ import annotations

import re

from markupsafe import Markup, escape

from svejk.glossary import GLOSSARY


def _pattern(phrase: str) -> re.Pattern[str]:
    parts = [re.escape(p) for p in phrase.split()]
    body = r"\s+".join(parts)
    return re.compile(rf"(?<![\w/]){body}(?![\w/])", re.IGNORECASE)


def _wrap(label: str, tip: str) -> str:
    safe_tip = escape(tip)
    return (
        f'<span class="term-tip" tabindex="0" role="term" '
        f'aria-label="{safe_tip}">{escape(label)}'
        f'<span class="term-tip-bubble" role="tooltip">{safe_tip}</span></span>'
    )


def markup_glossary(text: str) -> str:
    """Vrátí HTML s hover tooltipem u známých pojmů (bez překrývání)."""
    if not text or "<" in text:
        return text

    matches: list[tuple[int, int, str, str]] = []
    for phrase, tip in GLOSSARY:
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


def glossary_markup(text: str) -> Markup:
    return Markup(markup_glossary(text))
