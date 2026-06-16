"""Stenoprotokol: druhá stránka vydání a odkazy z článků na konkrétní pasáže."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from svejk.build.io import iter_jsonl, read_json, write_json
from svejk.build.nav import steno_sources_pages_href
from svejk.paths import SchuzePaths
from svejk.text_norm import bez_dlouhych_pomlc

_ANCHOR_SAFE = re.compile(r"[^a-zA-Z0-9_-]+")


@dataclass
class StenoPassage:
    steno_id: str
    anchor: str
    speaker: str
    poradi: int | None
    topic_slug: str
    topic_title: str
    article_num: int
    summary: str
    citace: str
    excerpt: str
    psp_url: str
    source: str
    nav_label: str = ""
    link_phrase: str = ""


@dataclass
class StenoTopicBlock:
    slug: str
    title: str
    num: int
    passages: list[StenoPassage] = field(default_factory=list)


def steno_anchor(steno_id: str) -> str:
    return f"steno-{_ANCHOR_SAFE.sub('-', steno_id).strip('-')}"


def steno_sources_href(
    obdobi: int,
    schuze: int,
    datum_unl: str,
    *,
    link_mode: str,
    base_path: str = "",
    locale: str = "cs",
) -> str:
    if link_mode == "pages":
        return steno_sources_pages_href(obdobi, schuze, datum_unl, base_path, locale)
    from datetime import datetime

    d = datetime.strptime(datum_unl, "%d.%m.%Y")
    return f"{d.strftime('%Y-%m-%d')}-steno.html"


def _norm_ws(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text or "")).strip()


def _load_steno_index(paths: SchuzePaths) -> dict[str, dict[str, Any]]:
    if not paths.steno_jsonl.is_file():
        return {}
    return {r["id"]: r for r in iter_jsonl(paths.steno_jsonl) if r.get("id")}


def _excerpt_around(full_text: str, citace: str, *, radius: int = 420) -> str:
    text = (full_text or "").strip()
    quote = (citace or "").strip()
    if not text:
        return quote
    if not quote:
        return text[:1200] + ("…" if len(text) > 1200 else "")
    flat = _norm_ws(text)
    flat_quote = _norm_ws(quote)
    pos = flat.lower().find(flat_quote.lower())
    if pos < 0:
        # zkus kratší začátek citace
        for n in (80, 60, 40, 24):
            chunk = flat_quote[:n].strip()
            if len(chunk) >= 16:
                pos = flat.lower().find(chunk.lower())
                if pos >= 0:
                    flat_quote = chunk
                    break
    if pos < 0:
        return text[:1200] + ("…" if len(text) > 1200 else "")
    start = max(0, pos - radius)
    end = min(len(flat), pos + len(flat_quote) + radius)
    out = flat[start:end].strip()
    if start > 0:
        out = "… " + out
    if end < len(flat):
        out = out + " …"
    return out


def _nav_label(speaker: str, citace: str, summary: str) -> str:
    name = (speaker or "Záznam").split()[-1] if speaker else "Záznam"
    src = _norm_ws(citace or summary)
    if len(src) > 52:
        src = src[:49].rstrip() + "…"
    return f"{name}: {src}" if src else name


def _psp_index_path(paths: SchuzePaths):
    return paths.aligned / "psp_steno_index.json"


def _psp_url_cache_path(paths: SchuzePaths):
    return paths.aligned / "psp_url_cache.json"


class PspUrlResolver:
    """Obohacuje URL z Hlídače o kotvy a stránku, kde je citace.

    Resolved URL jsou cachované na disk (psp_url_cache.json), takže opakované
    volání collect_steno_sources() nevyžaduje další síťové požadavky.
    """

    def __init__(self, paths: SchuzePaths):
        self.paths = paths
        self._fetcher = None
        self._page_urls: list[str] | None = None
        self._page_text_cache: dict[str, str] = {}
        self._url_cache: dict[str, str] | None = None

    def _fetcher_lazy(self):
        if self._fetcher is None:
            from psp.steno_web import PspStenoFetcher

            self._fetcher = PspStenoFetcher()
        return self._fetcher

    def _load_url_cache(self) -> dict[str, str]:
        if self._url_cache is None:
            cache_path = _psp_url_cache_path(self.paths)
            if cache_path.is_file():
                data = read_json(cache_path)
                self._url_cache = data.get("resolved") or {}
            else:
                self._url_cache = {}
        return self._url_cache

    def _save_url_cache(self) -> None:
        if self._url_cache is None:
            return
        self.paths.aligned.mkdir(parents=True, exist_ok=True)
        write_json(_psp_url_cache_path(self.paths), {"resolved": self._url_cache})

    def _load_pages(self) -> None:
        if self._page_urls is not None:
            return
        cache_path = _psp_index_path(self.paths)
        if cache_path.is_file():
            data = read_json(cache_path)
            if (
                data.get("obdobi") == self.paths.obdobi
                and data.get("schuze") == self.paths.schuze
                and data.get("page_urls")
            ):
                self._page_urls = list(data["page_urls"])
                return
        fetcher = self._fetcher_lazy()
        self._page_urls = fetcher.list_steno_page_urls(self.paths.obdobi, self.paths.schuze)
        self.paths.aligned.mkdir(parents=True, exist_ok=True)
        write_json(
            cache_path,
            {
                "obdobi": self.paths.obdobi,
                "schuze": self.paths.schuze,
                "page_urls": self._page_urls,
            },
        )

    def resolve(self, speaker: str, fallback_url: str, citace: str) -> str:
        if not fallback_url.startswith("https://www.psp.cz/"):
            return fallback_url
        if "#" in fallback_url and not citace.strip():
            return fallback_url

        cache_key = f"{fallback_url}|{citace[:120]}"
        url_cache = self._load_url_cache()
        if cache_key in url_cache:
            return url_cache[cache_key]

        self._load_pages()
        resolved = self._fetcher_lazy().resolve_url_for_citace(
            self.paths.obdobi,
            self.paths.schuze,
            speaker,
            citace,
            fallback_url=fallback_url,
            page_urls=self._page_urls,
            page_text_cache=self._page_text_cache,
        )
        url_cache[cache_key] = resolved
        self._save_url_cache()
        return resolved


def _passage_from_fact(
    fact_entry: dict[str, Any],
    *,
    steno_by_id: dict[str, dict[str, Any]],
    topic_slug: str,
    topic_title: str,
    article_num: int,
    passage_idx: int,
    psp_resolver: PspUrlResolver | None = None,
) -> StenoPassage | None:
    source = (fact_entry.get("source") or "steno").strip()
    citace = (fact_entry.get("citace") or "").strip()
    summary = (fact_entry.get("text") or "").strip()
    if not citace and not summary:
        return None
    steno_id = (fact_entry.get("steno_id") or "").strip()
    if source == "votes" and not citace:
        return None

    rec = steno_by_id.get(steno_id) if steno_id else None
    speaker = (rec or {}).get("cele_jmeno") or ""
    poradi = (rec or {}).get("poradi")
    full_text = (rec or {}).get("text") or ""
    psp_url = (rec or {}).get("url") or ""
    anchor = (
        f"{steno_anchor(steno_id)}-p{passage_idx}"
        if steno_id
        else f"vote-{topic_slug}-{passage_idx}"
    )

    if not citace and full_text:
        citace = _excerpt_around(full_text, "", radius=180)
    if psp_resolver and psp_url and source == "steno":
        psp_url = psp_resolver.resolve(speaker, psp_url, citace)
    excerpt = _excerpt_around(full_text, citace) if full_text else citace
    citace = bez_dlouhych_pomlc(citace)
    excerpt = bez_dlouhych_pomlc(excerpt)
    summary = bez_dlouhych_pomlc(summary)

    return StenoPassage(
        steno_id=steno_id or anchor,
        anchor=anchor,
        speaker=speaker,
        poradi=poradi,
        topic_slug=topic_slug,
        topic_title=topic_title,
        article_num=article_num,
        summary=summary,
        citace=citace,
        excerpt=excerpt,
        psp_url=psp_url,
        source=source,
        nav_label=_nav_label(speaker, citace, summary),
        link_phrase=(fact_entry.get("link_phrase") or "").strip(),
    )


def collect_steno_sources(
    paths: SchuzePaths,
    datum_unl: str,
    *,
    locale: str = "cs",
) -> list[StenoTopicBlock]:
    from datetime import datetime

    from svejk.build.facts_i18n import localized_fact, pick_field
    from svejk.locale import normalize_locale

    loc = normalize_locale(locale)
    d = datetime.strptime(datum_unl, "%d.%m.%Y")
    day_path = paths.facts_by_day / f"{d.strftime('%Y-%m-%d')}.json"
    if not day_path.is_file():
        return []
    day = read_json(day_path)
    if day.get("steno_zdroje") is False:
        return []
    if not day.get("steno_zdroje"):
        return []

    steno_by_id = _load_steno_index(paths)
    psp_resolver = PspUrlResolver(paths) if steno_by_id else None
    blocks: list[StenoTopicBlock] = []
    num = 0
    global_passage_idx = 0
    for slug in day.get("topic_slugs") or []:
        fp = paths.facts_by_topic / f"{slug}.json"
        if not fp.is_file():
            continue
        fact_raw = read_json(fp)
        if not fact_raw.get("publikovat"):
            continue
        fact = localized_fact(fact_raw, loc)
        num += 1
        title = pick_field(fact_raw, "nadpis", loc) or fact.get("nadpis") or slug
        block = StenoTopicBlock(slug=slug, title=title, num=num)
        en_fakty = (fact_raw.get("en") or {}).get("fakty") if loc == "en" else None
        for i, f in enumerate(fact.get("fakty") or []):
            if not isinstance(f, dict):
                continue
            merged = dict(f)
            if en_fakty and i < len(en_fakty):
                for key in ("text", "citace"):
                    if (en_fakty[i].get(key) or "").strip():
                        merged[key] = en_fakty[i][key]
            passage = _passage_from_fact(
                merged,
                steno_by_id=steno_by_id,
                topic_slug=slug,
                topic_title=title,
                article_num=num,
                passage_idx=global_passage_idx,
                psp_resolver=psp_resolver,
            )
            global_passage_idx += 1
            if passage:
                block.passages.append(passage)
        if block.passages:
            blocks.append(block)
    return blocks


def has_steno_sources(paths: SchuzePaths, datum_unl: str) -> bool:
    """Rychlá kontrola bez síťových požadavků: jen čte JSON, nestahuje PSP."""
    from datetime import datetime

    d = datetime.strptime(datum_unl, "%d.%m.%Y")
    day_path = paths.facts_by_day / f"{d.strftime('%Y-%m-%d')}.json"
    if not day_path.is_file():
        return False
    day = read_json(day_path)
    if not day.get("steno_zdroje"):
        return False
    steno_by_id = _load_steno_index(paths)
    if not steno_by_id:
        return False
    for slug in day.get("topic_slugs") or []:
        fp = paths.facts_by_topic / f"{slug}.json"
        if not fp.is_file():
            continue
        fact = read_json(fp)
        if not fact.get("publikovat"):
            continue
        for f in (fact.get("fakty") or []):
            if not isinstance(f, dict):
                continue
            source = (f.get("source") or "steno").strip()
            steno_id = (f.get("steno_id") or "").strip()
            citace = (f.get("citace") or "").strip()
            summary = (f.get("text") or "").strip()
            if source == "votes" and not citace:
                continue
            if not citace and not summary:
                continue
            if source == "steno" and steno_id and steno_id in steno_by_id:
                return True
            if source != "steno" and (citace or summary):
                return True
    return False


def _speaker_clause(speaker: str, article_text: str) -> str | None:
    """Fráze od příjmení řečníka do čárky před dalším jménem."""
    surname = (speaker or "").split()[-1] if speaker else ""
    if len(surname) < 3:
        return None
    pattern = re.compile(
        rf"\b{re.escape(surname)}\b[^,.]*?(?=,\s+[A-ZÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ]|\.$|$)",
        re.IGNORECASE,
    )
    matches = [m.group(0).strip() for m in pattern.finditer(article_text)]
    if not matches:
        if article_text.lower().count(surname.lower()) == 1:
            return surname
        return None
    best = max(matches, key=len)
    return best if len(best) >= len(surname) + 3 else None


def link_phrase_for_passage(passage: StenoPassage, article_text: str) -> str | None:
    article = article_text or ""
    clause = _speaker_clause(passage.speaker, article)
    if clause and clause in article:
        return clause
    summary = passage.summary
    citace = passage.citace
    if summary:
        words = summary.split()
        for length in range(min(12, len(words)), 2, -1):
            for start in range(len(words) - length + 1):
                phrase = " ".join(words[start : start + length])
                if len(phrase) >= 10 and phrase in article:
                    return phrase
    if citace:
        flat = _norm_ws(citace)
        for n in (min(60, len(flat)), 45, 30, 20):
            if n < 10:
                continue
            chunk = flat[:n].strip()
            if chunk and chunk in article:
                return chunk
    return None


def passage_href(passage: StenoPassage, page_href: str) -> str:
    """Odkaz z článku na naši stranu se zdroji (kotva u pasáže). PSP až odtud."""
    return f"{page_href}#{passage.anchor}"


def _find_phrase_in_text(text: str, phrase: str) -> str | None:
    """Vrátí přesnou podmnožinu textu odpovídající frázi (case-insensitive)."""
    if not text or not phrase:
        return None
    if phrase in text:
        return phrase
    low_text = text.lower()
    low_phrase = phrase.lower()
    pos = low_text.find(low_phrase)
    if pos < 0:
        return None
    return text[pos : pos + len(phrase)]


def inject_steno_link(text: str, phrase: str, href: str) -> str:
    if not text or not phrase or not href:
        return text
    match = _find_phrase_in_text(text, phrase)
    if not match:
        return text
    for m in re.finditer(r"<a\b[^>]*>.*?</a>", text, re.I | re.S):
        if match in m.group(0):
            return text
    external = href.startswith("http://") or href.startswith("https://")
    attrs = ' class="steno-link" href="{href}"'
    if external:
        attrs += ' target="_blank" rel="noopener"'
    repl = f"<a{attrs.format(href=href)}>{match}</a>"
    return text.replace(match, repl, 1)


def inject_steno_links(text: str, links: list[tuple[str, str]]) -> str:
    out = text
    used: set[str] = set()
    for phrase, href in sorted(links, key=lambda x: -len(x[0])):
        if phrase in used:
            continue
        new_out = inject_steno_link(out, phrase, href)
        if new_out != out:
            out = new_out
            used.add(phrase)
    return out


def build_item_steno_links(
    passages: list[StenoPassage],
    item: Any,
    page_href: str,
) -> None:
    """Vloží odkazy do lead / mean / kuriozita přímo v textu článku."""
    used_phrases: set[str] = set()
    ordered = sorted(
        passages,
        key=lambda p: (-len(p.link_phrase or ""), p.link_phrase is None),
    )
    all_fields = ("lead", "mean", "kuriozita", "citace_text")
    for p in ordered:
        href = passage_href(p, page_href)
        if p.link_phrase:
            fields = [
                f
                for f in all_fields
                if _find_phrase_in_text((getattr(item, f, None) or ""), p.link_phrase)
            ]
            if not fields:
                fields = list(all_fields)
        else:
            fields = list(all_fields)
        placed = False
        for field in fields:
            text = (getattr(item, field, None) or "").strip()
            if not text or placed:
                continue
            if p.link_phrase:
                phrase = _find_phrase_in_text(text, p.link_phrase)
                if not phrase:
                    phrase = link_phrase_for_passage(p, text)
            else:
                phrase = link_phrase_for_passage(p, text)
            if not phrase or phrase in used_phrases:
                continue
            new_text = inject_steno_link(text, phrase, href)
            if new_text != text:
                setattr(item, field, new_text)
                used_phrases.add(phrase)
                placed = True
                break


def apply_steno_links_to_content(
    content: Any,
    paths: SchuzePaths,
    *,
    obdobi: int | None = None,
    link_mode: str = "file",
    base_path: str = "",
    locale: str = "cs",
) -> str | None:
    """Doplní odkazy z článku na stenoprotokol; vrátí href stránky se zdroji."""
    if not has_steno_sources(paths, content.datum):
        return None
    from svejk.locale import normalize_locale

    loc = normalize_locale(locale)
    ob = obdobi if obdobi is not None else paths.obdobi
    page_href = steno_sources_href(
        ob,
        paths.schuze,
        content.datum,
        link_mode=link_mode,
        base_path=base_path,
        locale=loc,
    )
    blocks = collect_steno_sources(paths, content.datum, locale=loc)
    for item in content.items:
        passages = passages_for_slug(blocks, item.slug)
        if passages:
            build_item_steno_links(passages, item, page_href)
    return page_href


def passages_for_slug(blocks: list[StenoTopicBlock], slug: str) -> list[StenoPassage]:
    for block in blocks:
        if block.slug == slug:
            return block.passages
    return []
