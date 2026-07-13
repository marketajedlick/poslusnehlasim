"""Index zmínek slovníčkových pojmů ve vydáních (build-time)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from svejk.build.day_content import build_den_content, datum_design
from svejk.build.glossary_markup import _pattern, strip_glossary_markup
from svejk.build.nav import _den_z_index, _edition_headline, edition_pages_href
from svejk.build.publish import list_site_editions
from svejk.glossary import slovnicek_entries, slovnicek_term_slug
from svejk.paths import SchuzePaths


@dataclass(frozen=True)
class SlovnicekMention:
    href: str
    date_label: str
    headline: str
    excerpt: str


def _edition_plain_text(edition) -> str:
    paths = SchuzePaths.create(edition.obdobi, edition.schuze)
    d = edition.datum_unl
    from datetime import datetime

    day = datetime.strptime(d, "%d.%m.%Y")
    day_path = paths.facts_by_day / f"{day.strftime('%Y-%m-%d')}.json"
    if not day_path.is_file():
        return ""
    content = build_den_content(day_path, paths, link_mode="pages")
    chunks: list[str] = [content.dnesni_ucet, content.zaver]
    for item in content.items:
        chunks.extend([item.nadpis, item.lead, item.mean, item.pointa or "", item.pointa_tail or ""])
    return strip_glossary_markup(" ".join(c for c in chunks if c))


def _excerpt(text: str, start: int, end: int, *, radius: int = 70) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    snippet = " ".join(text[left:right].split())
    if left > 0:
        snippet = "… " + snippet
    if right < len(text):
        snippet = snippet + " …"
    return snippet


def build_slovnicek_mentions_index(
    obdobi: int,
    *,
    base_path: str = "",
    limit_per_term: int = 8,
) -> dict[str, tuple[SlovnicekMention, ...]]:
    """Pro každý pojem ze SLOVNIČEK najde až `limit_per_term` nejnovějších vydání."""
    terms = slovnicek_entries()
    patterns = {slovnicek_term_slug(term): (term, _pattern(term)) for term, _ in terms}
    index: dict[str, list[SlovnicekMention]] = {slug: [] for slug in patterns}
    for edition in reversed(list_site_editions(obdobi)):
        text = _edition_plain_text(edition)
        if not text:
            continue
        paths = SchuzePaths.create(edition.obdobi, edition.schuze)
        date_label = datum_design(edition.datum_unl, _den_z_index(paths, edition.datum_unl))
        headline = _edition_headline(edition) or date_label
        href = edition_pages_href(
            edition.obdobi, edition.schuze, edition.datum_unl, base_path
        )
        for slug, (term, pat) in patterns.items():
            if len(index[slug]) >= limit_per_term:
                continue
            m = pat.search(text)
            if not m:
                continue
            index[slug].append(
                SlovnicekMention(
                    href=href,
                    date_label=date_label,
                    headline=headline,
                    excerpt=_excerpt(text, m.start(), m.end()),
                )
            )
    return {slug: tuple(rows) for slug, rows in index.items()}


def term_mentions(
    term: str,
    index: dict[str, tuple[SlovnicekMention, ...]],
) -> tuple[SlovnicekMention, ...]:
    return index.get(slovnicek_term_slug(term), ())
