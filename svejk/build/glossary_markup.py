"""Obalí známé sněmovní pojmy HTML tooltipem."""

from __future__ import annotations

import re
from typing import Any

from markupsafe import Markup, escape

from svejk.glossary import (
    glossary_entries,
    slovnicek_entries,
    slovnicek_term_label,
)


def _pattern(phrase: str) -> re.Pattern[str]:
    parts = [re.escape(p) for p in phrase.split()]
    body = r"\s+".join(parts)
    return re.compile(rf"(?<![\w]){body}(?![\w])", re.IGNORECASE)


def _wrap(label: str, tip: str) -> str:
    safe_tip = escape(tip)
    safe_label = escape(label)
    return (
        f'<button type="button" class="term-term" data-term="{safe_label}" '
        f'data-def="{safe_tip}" title="{safe_tip}">{safe_label}</button>'
    )


def _strip_term_term(text: str) -> str:
    return re.sub(
        r'<button[^>]*class="term-term"[^>]*>(.*?)</button>',
        r"\1",
        text,
        flags=re.I | re.S,
    )


_HTML_SPLIT = re.compile(r"(<[^>]+>)")
_TERM_TIP_BUBBLE = re.compile(
    r'<span class="term-tip-bubble"[^>]*>.*?</span>',
    re.I | re.S,
)
_TERM_TIP_WRAP = re.compile(
    r'<span class="term-tip"[^>]*>(.*?)</span>',
    re.I | re.S,
)
_HIGHLIGHT_MARK = re.compile(r"(?<![_\w])_([^_\n]+?)_(?![_\w])")
_HIGHLIGHT_SPAN = re.compile(r'<span class="hl">(.*?)</span>', re.I | re.S)


def highlight_markup(text: str) -> str:
    """`_klíčová fráze_` → oranžový inline highlight (ne celá věta)."""
    if not text or "_" not in text:
        return text
    return _HIGHLIGHT_MARK.sub(
        lambda m: f'<span class="hl">{escape(m.group(1))}</span>',
        text,
    )


def strip_highlight_markup(text: str) -> str:
    if not text:
        return text
    out = _HIGHLIGHT_SPAN.sub(r"\1", text)
    return _HIGHLIGHT_MARK.sub(r"\1", out)


def _markup_plain(text: str) -> str:
    """Tooltipy jen v prostém textu (bez HTML tagů)."""
    if not text:
        return text

    glossary = glossary_entries()
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


def strip_glossary_markup(text: str) -> str:
    """E-mail: tooltipy nefungují, nech jen viditelný label."""
    if not text:
        return text
    out = text
    if "term-tip" in out or "term-term" in out:
        out = _TERM_TIP_BUBBLE.sub("", out)
        while _TERM_TIP_WRAP.search(out):
            out = _TERM_TIP_WRAP.sub(lambda m: m.group(1), out)
        out = _strip_term_term(out)
    return strip_highlight_markup(out)


_TERM_TIP_BLOCK = re.compile(
    r'(<span class="term-tip"[^>]*>.*?</span>)',
    re.I | re.S,
)


def markup_glossary(text: str) -> str:
    """Vrátí HTML s hover tooltipem u známých pojmů (bez překrývání)."""
    if not text:
        return text
    if 'class="term-term"' in text:
        return text
    if "class=\"term-tip\"" in text:
        parts = _TERM_TIP_BLOCK.split(text)
        return "".join(
            part if part.startswith('<span class="term-tip"') else _markup_html_fragment(part)
            for part in parts
        )
    return _markup_html_fragment(text)


def _markup_html_fragment(text: str) -> str:
    if not text:
        return text
    if "<" not in text:
        return _markup_plain(text)

    parts = _HTML_SPLIT.split(text)
    return "".join(
        part if part.startswith("<") else _markup_plain(part)
        for part in parts
    )


def apply_glossary_to_content(content: Any) -> None:
    """Tooltipy v textu dne — před vložením odkazů, které frázi rozsekají."""
    for field in ("dnesni_ucet", "result_note", "zaver", "zaver_body"):
        val = getattr(content, field, None)
        if val:
            setattr(content, field, markup_glossary(val))
    for item in getattr(content, "items", []) or []:
        for field in ("lead", "mean", "kuriozita", "citace_text", "pointa"):
            val = getattr(item, field, None)
            if val:
                setattr(item, field, markup_glossary(val))


def glossary_markup(text: str) -> Markup:
    return Markup(markup_glossary(text))


def _needle_pattern(needle: str) -> re.Pattern[str]:
    """Shoda i na českých koncích (brzdách, pravidlech…)."""
    parts = [re.escape(p) for p in needle.split()]
    body = r"\s+".join(parts)
    return re.compile(rf"(?<![\w]){body}", re.IGNORECASE)


def _slovnicek_entry_for_needle(needle: str) -> tuple[str, str] | None:
    low = needle.lower()
    for term, tip in slovnicek_entries():
        if term.lower() == low:
            return term, tip
    pat = _needle_pattern(needle)
    for term, tip in slovnicek_entries():
        if pat.search(term):
            return term, tip
    return None


def _glossary_matches_in_text(combined: str) -> list[tuple[int, str, str]]:
    """Pojmy z glosáře v textu (pořadí prvního výskytu, bez překrývání)."""
    glossary = glossary_entries()
    raw: list[tuple[int, int, str, str]] = []
    for phrase, glossary_tip in glossary:
        for m in _pattern(phrase).finditer(combined):
            sk = _slovnicek_entry_for_needle(phrase) or _slovnicek_entry_for_needle(
                m.group(0)
            )
            if sk:
                display, tip = sk
            else:
                display, tip = m.group(0), glossary_tip
            raw.append((m.start(), m.end(), display, tip))

    raw.sort(key=lambda x: (-(x[1] - x[0]), x[0]))
    used: list[tuple[int, int]] = []
    selected: list[tuple[int, str, str]] = []
    seen_display: set[str] = set()
    for start, end, display, tip in raw:
        if any(not (end <= s or start >= e) for s, e in used):
            continue
        key = display.lower()
        if key in seen_display:
            continue
        used.append((start, end))
        seen_display.add(key)
        selected.append((start, display, tip))

    selected.sort(key=lambda x: x[0])
    return [(slovnicek_term_label(display), tip) for _, display, tip in selected]


def svejkov_slovnik(*texts: str, limit: int = 6) -> list[tuple[str, str]]:
    """Pojmy z textu dne pro box Švejkův slovník (název, vysvětlení)."""
    found = _glossary_matches_in_text("\n".join(t for t in texts if t))
    return found if limit <= 0 else found[:limit]


def slovnicek_dne(*texts: str) -> list[tuple[str, str]]:
    """Všechny pojmy z textu dne pro sekci Slovníček dne."""
    combined = "\n".join(strip_glossary_markup(t) for t in texts if t)
    if not combined.strip():
        return []
    return _glossary_matches_in_text(combined)


if __name__ == "__main__":
    sample = (
        "Podle pana Rakušana je mise u OSN moc pěkné místečko, "
        "zvlášť když se na něj nastupuje _bez prezidentova podpisu_."
    )
    assert (
        highlight_markup(sample)
        == "Podle pana Rakušana je mise u OSN moc pěkné místečko, "
        "zvlášť když se na něj nastupuje "
        '<span class="hl">bez prezidentova podpisu</span>.'
    )
    assert "2025_24_01097" not in highlight_markup("kotva steno-2025_24_01097")
    print("highlight_markup ok")
