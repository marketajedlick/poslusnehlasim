"""Obalí známé sněmovní pojmy HTML tooltipem."""

from __future__ import annotations

import re

from markupsafe import Markup, escape

from svejk.glossary import GLOSSARY

def _pattern(phrase: str) -> re.Pattern[str]:
    parts = [re.escape(p) for p in phrase.split()]
    body = r"\s+".join(parts)
    return re.compile(rf"(?<![\w/]){body}(?![\w/])", re.IGNORECASE)


def markup_glossary(text: str) -> str:
    """Vrátí HTML s hover tooltipem u známých pojmů."""
    if not text or "<" in text:
        return text

    out = text
    for phrase, tip in GLOSSARY:
        pat = _pattern(phrase)

        def _wrap(m: re.Match[str], *, _tip: str = tip) -> str:
            label = m.group(0)
            safe_tip = escape(_tip)
            return (
                f'<span class="term-tip" tabindex="0" role="term" '
                f'aria-label="{safe_tip}">{escape(label)}'
                f'<span class="term-tip-bubble" role="tooltip">{safe_tip}</span></span>'
            )

        out = pat.sub(_wrap, out)

    return out


def glossary_markup(text: str) -> Markup:
    return Markup(markup_glossary(text))
