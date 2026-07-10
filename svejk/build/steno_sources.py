"""Stenoprotokol: druhá stránka vydání a odkazy z článků na konkrétní pasáže."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from svejk.build.io import iter_jsonl, read_json, write_json
from svejk.build.nav import steno_sources_pages_href
from svejk.paths import SchuzePaths
from svejk.text_norm import bez_dlouhych_pomlc, expand_szif_for_display

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
    article_phrase: str = ""


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
) -> str:
    if link_mode == "pages":
        return steno_sources_pages_href(obdobi, schuze, datum_unl, base_path)
    from datetime import datetime

    d = datetime.strptime(datum_unl, "%d.%m.%Y")
    return f"{d.strftime('%Y-%m-%d')}-steno.html"


def _norm_ws(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text or "")).strip()


def _steno_refs_path(paths: SchuzePaths):
    return paths.aligned / "steno_refs.json"


def write_steno_refs(paths: SchuzePaths):
    """Z raw/steno.jsonl uloží lehký index pro CI (steno.jsonl není v gitu)."""
    if not paths.steno_jsonl.is_file():
        return None
    refs: dict[str, dict[str, Any]] = {}
    for rec in iter_jsonl(paths.steno_jsonl):
        steno_id = rec.get("id")
        if not steno_id:
            continue
        refs[steno_id] = {
            "url": rec.get("url") or "",
            "cele_jmeno": rec.get("cele_jmeno") or "",
            "poradi": rec.get("poradi"),
            "text": rec.get("text") or "",
        }
    if not refs:
        return None
    paths.aligned.mkdir(parents=True, exist_ok=True)
    out = _steno_refs_path(paths)
    write_json(out, refs)
    return out


def _load_steno_index(paths: SchuzePaths) -> dict[str, dict[str, Any]]:
    if paths.steno_jsonl.is_file():
        return {r["id"]: r for r in iter_jsonl(paths.steno_jsonl) if r.get("id")}
    refs_path = _steno_refs_path(paths)
    if refs_path.is_file():
        data = read_json(refs_path)
        if isinstance(data, dict):
            return data
    return {}


def _poradi_from_steno_id(steno_id: str) -> int | None:
    if not steno_id:
        return None
    try:
        return int(steno_id.rsplit("_", 1)[-1])
    except ValueError:
        return None


def _load_poradi_urls(paths: SchuzePaths) -> dict[str, str]:
    cache_path = _psp_index_path(paths)
    if not cache_path.is_file():
        return {}
    data = read_json(cache_path)
    if data.get("obdobi") != paths.obdobi or data.get("schuze") != paths.schuze:
        return {}
    urls = data.get("poradi_urls") or {}
    return {str(k): str(v) for k, v in urls.items() if v}


_PSP_URL_CACHE_VERSION = "v2"


def _psp_cache_key(fallback_url: str, citace: str) -> str:
    base = fallback_url.split("#", 1)[0]
    return f"{_PSP_URL_CACHE_VERSION}|{base}|{citace[:120]}"


def _lookup_cached_psp_url(url_cache: dict[str, str], fallback_url: str, citace: str) -> str:
    if not url_cache:
        return ""
    citace_key = citace[:120]
    if fallback_url and citace_key:
        for key in (
            _psp_cache_key(fallback_url, citace),
            f"{_PSP_URL_CACHE_VERSION}|{fallback_url}|{citace_key}",
        ):
            exact = url_cache.get(key)
            if exact:
                return exact
        base = fallback_url.split("#", 1)[0]
        exact = url_cache.get(f"{_PSP_URL_CACHE_VERSION}|{base}|{citace_key}")
        if exact:
            return exact
    return ""


def _offline_psp_url(
    paths: SchuzePaths,
    steno_id: str,
    citace: str,
    *,
    fallback_url: str = "",
    url_cache: dict[str, str] | None = None,
) -> str:
    """PSP odkaz bez steno.jsonl — cache + poradi_urls v aligned/."""
    cache = url_cache if url_cache is not None else {}
    if fallback_url:
        hit = _lookup_cached_psp_url(cache, fallback_url, citace)
        if hit:
            return hit
    poradi = _poradi_from_steno_id(steno_id)
    poradi_urls = _load_poradi_urls(paths)
    if poradi is not None:
        poradi_url = poradi_urls.get(str(poradi), "")
        if poradi_url:
            hit = _lookup_cached_psp_url(cache, poradi_url, citace)
            return hit or poradi_url
    return fallback_url


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

        url_cache = self._load_url_cache()
        cached = _lookup_cached_psp_url(url_cache, fallback_url, citace)
        if cached:
            return cached

        offline = _offline_psp_url(
            self.paths,
            "",
            citace,
            fallback_url=fallback_url,
            url_cache=url_cache,
        )
        if offline and offline != fallback_url:
            return offline

        cache_key = _psp_cache_key(fallback_url, citace)
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


def resolve_psp_url_for_steno(
    paths: SchuzePaths,
    steno_id: str,
    citace: str,
) -> str:
    """Odkaz na konkrétní místo ve stenoprotokolu na webu Sněmovny."""
    steno_by_id = _load_steno_index(paths)
    rec = steno_by_id.get(steno_id) or {}
    fallback = (rec.get("url") or "").strip()
    speaker = (rec.get("cele_jmeno") or "").strip()
    citace = (citace or "").strip()
    offline_psp = bool(
        steno_by_id
        or _steno_refs_path(paths).is_file()
        or _psp_url_cache_path(paths).is_file()
        or _load_poradi_urls(paths)
    )
    if offline_psp:
        return PspUrlResolver(paths).resolve(speaker, fallback, citace)
    if fallback and citace:
        cache_path = _psp_url_cache_path(paths)
        cache = read_json(cache_path).get("resolved") or {} if cache_path.is_file() else {}
        hit = _lookup_cached_psp_url(cache, fallback, citace)
        if hit:
            return hit
    resolved = _offline_psp_url(
        paths,
        steno_id,
        citace,
        fallback_url=fallback,
    )
    return resolved or fallback


def _passage_from_fact(
    fact_entry: dict[str, Any],
    *,
    paths: SchuzePaths,
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
    if source == "votes":
        if not citace:
            return None
    elif source in ("manual", "notes"):
        return None
    elif not steno_id:
        # ponytail: redakční poznámky bez kotvy ve stenozáznamu nepatří na stránku zdrojů
        return None

    rec = steno_by_id.get(steno_id) if steno_id else None
    speaker = (rec or {}).get("cele_jmeno") or ""
    poradi = (rec or {}).get("poradi")
    if poradi is None and steno_id:
        poradi = _poradi_from_steno_id(steno_id)
    full_text = (rec or {}).get("text") or ""
    psp_url = (rec or {}).get("url") or ""
    anchor = (
        f"{steno_anchor(steno_id)}-p{passage_idx}"
        if steno_id
        else f"vote-{topic_slug}-{passage_idx}"
    )

    if not citace and full_text:
        citace = _excerpt_around(full_text, "", radius=180)
    if source == "steno" and steno_id:
        cache = psp_resolver._load_url_cache() if psp_resolver else None
        if psp_resolver and psp_url:
            psp_url = psp_resolver.resolve(speaker, psp_url, citace)
        elif not psp_url:
            psp_url = _offline_psp_url(
                paths,
                steno_id,
                citace,
                url_cache=cache,
            )
        elif psp_resolver:
            psp_url = psp_resolver.resolve(speaker, psp_url, citace)
    excerpt = _excerpt_around(full_text, citace) if full_text else citace
    citace = expand_szif_for_display(bez_dlouhych_pomlc(citace))
    excerpt = expand_szif_for_display(bez_dlouhych_pomlc(excerpt))
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


def _article_text_from_fact(fact: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("lead", "pointa", "mean", "kuriozita", "citace_text"):
        val = (fact.get(key) or "").strip()
        if val:
            parts.append(val)
    return " ".join(parts)


def _resolve_article_phrase(passage: StenoPassage, article_text: str) -> str:
    if passage.link_phrase:
        found = _find_phrase_in_text(article_text, passage.link_phrase)
        if found:
            return found
    found = link_phrase_for_passage(passage, article_text)
    return found or ""


def collect_steno_sources(
    paths: SchuzePaths,
    datum_unl: str,
) -> list[StenoTopicBlock]:
    from svejk.build.mezin_smlouvy import append_smlouvy_steno_block

    from datetime import datetime

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
    offline_psp = bool(
        steno_by_id
        or _steno_refs_path(paths).is_file()
        or _psp_url_cache_path(paths).is_file()
        or _load_poradi_urls(paths)
    )
    psp_resolver = PspUrlResolver(paths) if offline_psp else None
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
        fact = fact_raw
        num += 1
        title = (fact.get("nadpis") or "").strip() or slug
        block = StenoTopicBlock(slug=slug, title=title, num=num)
        article_text = _article_text_from_fact(fact)
        for f in fact.get("fakty") or []:
            if not isinstance(f, dict):
                continue
            merged = dict(f)
            passage = _passage_from_fact(
                merged,
                paths=paths,
                steno_by_id=steno_by_id,
                topic_slug=slug,
                topic_title=title,
                article_num=num,
                passage_idx=global_passage_idx,
                psp_resolver=psp_resolver,
            )
            global_passage_idx += 1
            if passage:
                passage.article_phrase = bez_dlouhych_pomlc(
                    _resolve_article_phrase(passage, article_text)
                )
                block.passages.append(passage)
        if block.passages:
            blocks.append(block)
    num, global_passage_idx = append_smlouvy_steno_block(
        blocks,
        paths=paths,
        day=day,
        steno_by_id=steno_by_id,
        psp_resolver=psp_resolver,
        num=num,
        global_passage_idx=global_passage_idx,
    )
    num = append_jazykolam_steno_block(
        blocks,
        paths=paths,
        day=day,
        steno_by_id=steno_by_id,
        psp_resolver=psp_resolver,
        num=num,
    )
    return blocks


def append_jazykolam_steno_block(
    blocks: list[StenoTopicBlock],
    *,
    paths: SchuzePaths,
    day: dict[str, Any],
    steno_by_id: dict[str, dict[str, Any]],
    psp_resolver: PspUrlResolver | None,
    num: int,
) -> int:
    """Kotva steno-{id} musí sedět s jazykolam.steno_anchor na stránce vydání."""
    j = day.get("jazykolam") or {}
    text = (j.get("text") or "").strip()
    if not text:
        return num

    steno_id = (j.get("steno_id") or "").strip()
    if not steno_id:
        poradi = j.get("poradi")
        if poradi is not None:
            for sid, rec in steno_by_id.items():
                if rec.get("poradi") == poradi:
                    steno_id = sid
                    break
    if not steno_id:
        return num

    rec = steno_by_id.get(steno_id) or {}
    speaker = (j.get("autor") or rec.get("cele_jmeno") or "").strip()
    poradi = rec.get("poradi") if rec.get("poradi") is not None else j.get("poradi")
    full_text = (rec.get("text") or "").strip()
    citace = expand_szif_for_display(bez_dlouhych_pomlc(text))
    excerpt = expand_szif_for_display(
        bez_dlouhych_pomlc(_excerpt_around(full_text, text) if full_text else text)
    )
    psp_url = (rec.get("url") or (j.get("url") or "")).strip()
    if psp_resolver and psp_url:
        psp_url = psp_resolver.resolve(speaker, psp_url, text)
    elif steno_id and not psp_url:
        psp_url = _offline_psp_url(paths, steno_id, text)

    num += 1
    block = StenoTopicBlock(slug="jazykolam-dne", title="Jazykolam dne", num=num)
    block.passages.append(
        StenoPassage(
            steno_id=steno_id,
            anchor=steno_anchor(steno_id),
            speaker=speaker,
            poradi=poradi,
            topic_slug="jazykolam-dne",
            topic_title="Jazykolam dne",
            article_num=num,
            summary="",
            citace=citace,
            excerpt=excerpt,
            psp_url=psp_url,
            source="steno",
            nav_label=_nav_label(speaker, citace, text),
            article_phrase=citace,
        )
    )
    blocks.append(block)
    return num


def has_steno_sources(paths: SchuzePaths, datum_unl: str) -> bool:
    """True, pokud existuje exportovatelná stránka se zdroji (shodně s collect_steno_sources)."""
    return bool(collect_steno_sources(paths, datum_unl))


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


def _normalize_psp_url(url: str) -> str:
    return (url or "").split("#", 1)[0].rstrip("/")


def find_passage_for_citace(
    passages: list[StenoPassage],
    *,
    citace_text: str,
    citace_href: str = "",
) -> StenoPassage | None:
    """Najde pasáž odpovídající citaci v bloku (text nebo PSP URL z facts)."""
    if not passages:
        return None
    text = _norm_ws(citace_text)
    psp_base = _normalize_psp_url(citace_href)
    if text:
        for passage in passages:
            pc = _norm_ws(passage.citace)
            if not pc:
                continue
            if text == pc or text in pc or pc in text:
                return passage
            for n in (80, 60, 40, 25):
                if len(text) >= n and text[:n] in pc:
                    return passage
    if psp_base:
        for passage in passages:
            if _normalize_psp_url(passage.psp_url) == psp_base:
                return passage
    return None


def resolve_item_citace_href(
    item: Any,
    passages: list[StenoPassage],
    page_href: str,
) -> None:
    """Citace v článku vede nejdřív na naši stránku se zdroji, ne rovnou na PSP."""
    text = (getattr(item, "citace_text", None) or "").strip()
    href = (getattr(item, "citace_href", None) or "").strip()
    if not text and not href:
        return
    if not page_href:
        return
    passage = find_passage_for_citace(
        passages,
        citace_text=text,
        citace_href=href,
    )
    if passage:
        item.citace_href = passage_href(passage, page_href)
    elif href.startswith("https://www.psp.cz/") or text:
        item.citace_href = page_href


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


def _word_in_html_pattern(word: str) -> str:
    w = re.escape(word)
    return (
        rf"(?:{w}|"
        rf'<span class="term-tip"[^>]*>{w}'
        rf'(?:<span[^>]*>.*?</span>)*</span>)'
    )


def _find_phrase_in_html(text: str, phrase: str) -> str | None:
    words = phrase.split()
    if len(words) < 2:
        return None
    pat = r"\s*".join(_word_in_html_pattern(w) for w in words)
    m = re.search(pat, text, re.I | re.S)
    return m.group(0) if m else None


def inject_steno_link(text: str, phrase: str, href: str) -> str:
    if not text or not phrase or not href:
        return text
    match = _find_phrase_in_text(text, phrase)
    if not match and "<" in text:
        match = _find_phrase_in_html(text, phrase)
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
    # citace_text obaluje card-citace — odkaz řeší citace_href, ne inline fráze
    all_fields = ("lead", "mean", "kuriozita", "pointa")
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


def _all_passages(blocks: list[StenoTopicBlock]) -> list[StenoPassage]:
    out: list[StenoPassage] = []
    for block in blocks:
        out.extend(block.passages)
    return out


def link_steno_phrases_in_text(
    text: str,
    passages: list[StenoPassage],
    page_href: str,
    *,
    used_phrases: set[str] | None = None,
) -> str:
    """Vloží steno odkazy do libovolného textu vydání (lead, dnesni_ucet…)."""
    if not (text or "").strip() or not passages:
        return text
    used = used_phrases if used_phrases is not None else set()
    out = text
    ordered = sorted(
        passages,
        key=lambda p: (-len(p.link_phrase or ""), p.link_phrase is None),
    )
    for p in ordered:
        if not p.link_phrase:
            continue
        phrase = _find_phrase_in_text(out, p.link_phrase)
        if not phrase or phrase in used:
            continue
        new_out = inject_steno_link(out, phrase, passage_href(p, page_href))
        if new_out != out:
            out = new_out
            used.add(phrase)
    return out


def apply_steno_links_to_content(
    content: Any,
    paths: SchuzePaths,
    *,
    obdobi: int | None = None,
    link_mode: str = "file",
    base_path: str = "",
) -> str | None:
    """Doplní odkazy z článku na stenoprotokol; vrátí href stránky se zdroji."""
    if not has_steno_sources(paths, content.datum):
        return None
    ob = obdobi if obdobi is not None else paths.obdobi
    page_href = steno_sources_href(
        ob,
        paths.schuze,
        content.datum,
        link_mode=link_mode,
        base_path=base_path,
    )
    blocks = collect_steno_sources(paths, content.datum)
    used_phrases: set[str] = set()
    for item in content.items:
        item_passages = passages_for_slug(blocks, item.slug)
        if item_passages:
            resolve_item_citace_href(item, item_passages, page_href)
            build_item_steno_links(item_passages, item, page_href)
            for field in ("lead", "mean", "kuriozita", "pointa"):
                raw = getattr(item, field, None) or ""
                for m in re.finditer(r'class="steno-link"[^>]*>(.*?)</a>', raw, re.I | re.S):
                    used_phrases.add(re.sub(r"<[^>]+>", "", m.group(1)))
    all_passages = _all_passages(blocks)
    if all_passages and (getattr(content, "dnesni_ucet", None) or "").strip():
        content.dnesni_ucet = link_steno_phrases_in_text(
            content.dnesni_ucet,
            all_passages,
            page_href,
            used_phrases=used_phrases,
        )
    for field in ("zaver_body",):
        raw = (getattr(content, field, None) or "").strip()
        if raw and all_passages:
            linked = link_steno_phrases_in_text(
                raw,
                all_passages,
                page_href,
                used_phrases=used_phrases,
            )
            setattr(content, field, linked)
            key = (getattr(content, "zaver_key", None) or "").strip()
            if key:
                content.zaver = f"{key} {linked}"
    listy = getattr(content, "snemovni_listy", None)
    if listy and all_passages:
        for section in listy.get("sections") or []:
            section["paragraphs"] = [
                link_steno_phrases_in_text(
                    p,
                    all_passages,
                    page_href,
                    used_phrases=used_phrases,
                )
                for p in (section.get("paragraphs") or [])
            ]
    return page_href


def passages_for_slug(blocks: list[StenoTopicBlock], slug: str) -> list[StenoPassage]:
    for block in blocks:
        if block.slug == slug:
            return block.passages
    return []
