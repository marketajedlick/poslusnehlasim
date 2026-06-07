"""Stahování stenozáznamů přímo z webu PSP (eknih), když Hlídač ještě nemá import."""

from __future__ import annotations

import html
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Iterator

from psp.hlidac import HlidacClient, StenoRecord

_USER_AGENT = "poslusnehlasim/1.0"
_CHARSET = "windows-1250"

_MONTHS = {
    "ledna": 1,
    "února": 2,
    "unora": 2,
    "března": 3,
    "brezna": 3,
    "dubna": 4,
    "května": 5,
    "kvetna": 5,
    "června": 6,
    "cervna": 6,
    "července": 7,
    "cervence": 7,
    "srpna": 8,
    "září": 9,
    "zari": 9,
    "října": 10,
    "rijna": 10,
    "listopadu": 11,
    "prosince": 12,
}

_SPEAKER_PREFIXES = (
    "Předsedající ",
    "Predsedajici ",
    "Předseda PSP ",
    "Predseda PSP ",
    "Předseda vlády ČR ",
    "Místopředseda PSP ",
    "Mistopredseda PSP ",
    "Poslanec ",
    "Poslankyně ",
    "Poslankyne ",
    "Ministr ",
    "Ministryně ",
    "Ministryne ",
)

_PAGE_FOOTER_MARKERS = (
    "<!-- sy -->",
    '<div class="document-nav no-print">',
    "Související",
    "<!--/ Body",
    '<div id="footer"',
)

_ANCHOR_START = re.compile(
    r'<p[^>]*>\s*<b>\s*<a[^>]*\bid="(r\d+)"[^>]*>([^<]*)</a>\s*</b>\s*:\s*',
    re.I,
)

_DATE_RE = re.compile(
    r"(\d{1,2})\.\s*(?:&nbsp;|\s)*([A-Za-zÁČĎÉĚÍŇÓŘŠŤÚŮÝŽáčďéěíňóřšťúůýž]+)\s*(?:&nbsp;|\s)*(\d{4})"
)

_INDEX_TOKEN_RE = re.compile(
    r'<b>\s*(\d+\.\s*.*?)\s*</b>|<a\s+href="(s\d+\.htm)#(r\d+)"',
    re.I | re.S,
)


@dataclass
class _ParsedSpeech:
    anchor: str
    speaker_label: str
    text: str
    page_url: str
    datum: str | None


class _NextLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.next_href: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        d = {k: v for k, v in attrs if k and v is not None}
        href = d.get("href") or ""
        if d.get("class") == "next" and href.endswith((".htm", ".html")):
            self.next_href = href


class PspStenoFetcher:
    """Stahuje stenozáznamy z eknih.psp.cz ve formátu kompatibilním s Hlídačem."""

    def __init__(self, rate_limit_s: float = 0.25):
        self.rate_limit_s = rate_limit_s
        self._last_request = 0.0

    @staticmethod
    def schuze_base_url(obdobi: int, schuze: int) -> str:
        return f"https://www.psp.cz/eknih/{obdobi}ps/stenprot/{schuze:03d}schuz/"

    @staticmethod
    def first_steno_page(schuze: int) -> str:
        return f"s{schuze:03d}001.htm"

    @staticmethod
    def first_index_page(schuze: int) -> str:
        return f"{schuze}-1.html"

    def _wait(self) -> None:
        elapsed = time.monotonic() - self._last_request
        if elapsed < self.rate_limit_s:
            time.sleep(self.rate_limit_s - elapsed)
        self._last_request = time.monotonic()

    def fetch_html(self, url: str) -> str:
        self._wait()
        req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return ""
            raise
        return raw.decode(_CHARSET, errors="replace")

    def _resolve_url(self, base: str, href: str) -> str:
        if href.startswith("http"):
            return href
        return base.rstrip("/") + "/" + href.lstrip("/")

    def _walk_pages(
        self,
        base: str,
        first_href: str,
        *,
        next_suffix: str | None = None,
    ) -> Iterator[tuple[str, str]]:
        url = self._resolve_url(base, first_href)
        seen: set[str] = set()
        while url and url not in seen:
            seen.add(url)
            html_text = self.fetch_html(url)
            if not html_text:
                break
            yield url, html_text
            parser = _NextLinkParser()
            parser.feed(html_text)
            if not parser.next_href:
                break
            if next_suffix and not parser.next_href.endswith(next_suffix):
                break
            url = self._resolve_url(base, parser.next_href)

    @staticmethod
    def _html_to_text(fragment: str) -> str:
        cut = len(fragment)
        for marker in (
            "<!-- sy -->",
            "<script",
            "tippy(",
            "Minulý",
            "Nahoru Další",
            '<div class="document-nav no-print">',
        ):
            idx = fragment.find(marker)
            if idx != -1:
                cut = min(cut, idx)
        fragment = fragment[:cut]
        s = re.sub(r"<script[^>]*>.*?</script>", "", fragment, flags=re.I | re.S)
        s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
        s = re.sub(r"</p>\s*<p[^>]*>", "\n", s, flags=re.I)
        s = re.sub(r"<[^>]+>", "", s)
        s = html.unescape(s)
        s = s.replace("\xa0", " ")
        s = re.sub(r"[ \t]+", " ", s)
        s = re.sub(r"\n{3,}", "\n\n", s)
        return s.strip()

    @staticmethod
    def _parse_date(html_text: str) -> str | None:
        for pattern in (
            r'class="date"[^>]*>.*?(\d{1,2}\.\s*\w+\s*\d{4})',
            r"Pondělí[^<]*(\d{1,2}\.\s*\w+\s*\d{4})",
            r"(\d{1,2})\.\s*(?:&nbsp;|\s)*(\w+)\s*(?:&nbsp;|\s)*(\d{4})",
        ):
            m = re.search(pattern, html_text, re.I | re.S)
            if not m:
                continue
            if m.lastindex == 1:
                inner = re.sub(r"<[^>]+>", "", m.group(1))
                inner = html.unescape(inner.replace("&nbsp;", " "))
                dm = _DATE_RE.search(inner)
                if dm:
                    return PspStenoFetcher._iso_date(dm.group(1), dm.group(2), dm.group(3))
            else:
                return PspStenoFetcher._iso_date(m.group(1), m.group(2), m.group(3))
        return None

    @staticmethod
    def _iso_date(day_s: str, month_s: str, year_s: str) -> str | None:
        month = _MONTHS.get(month_s.lower().strip())
        if not month:
            return None
        return f"{int(year_s):04d}-{month:02d}-{int(day_s):02d}T00:00:00+01:00"

    @staticmethod
    def _cele_jmeno(speaker_label: str) -> str:
        label = html.unescape(speaker_label).strip()
        if " ČR " in label:
            return label.split(" ČR ")[-1].strip()
        for prefix in _SPEAKER_PREFIXES:
            if label.startswith(prefix):
                return label[len(prefix) :].strip()
        if "," in label:
            tail = label.split(",")[-1].strip()
            if tail.lower().startswith("ministr "):
                tail = tail[8:].strip()
                if " ČR " in tail:
                    return tail.split(" ČR ")[-1].strip()
                return tail
            return tail
        return label

    @staticmethod
    def _page_content_end(html_text: str, after: int = 0) -> int:
        end = len(html_text)
        for marker in _PAGE_FOOTER_MARKERS:
            idx = html_text.find(marker, after)
            if idx != -1:
                end = min(end, idx)
        first_links = html_text.find('<p class="links', after)
        if first_links != -1:
            second_links = html_text.find('<p class="links', first_links + 1)
            if second_links != -1:
                end = min(end, second_links)
        return end

    @staticmethod
    def _pocet_slov(text: str) -> int:
        return len(re.findall(r"\S+", text))

    def _parse_tema_map(self, obdobi: int, schuze: int) -> dict[tuple[str, str], str]:
        base = self.schuze_base_url(obdobi, schuze)
        tema_map: dict[tuple[str, str], str] = {}
        current_tema = "Zahájení schůze"
        for _, html_text in self._walk_pages(
            base, self.first_index_page(schuze), next_suffix=".html"
        ):
            for m in _INDEX_TOKEN_RE.finditer(html_text):
                if m.group(1):
                    bod = self._html_to_text(m.group(1))
                    bod = re.sub(r"^\d+\.\s*", "", bod).strip()
                    if bod:
                        current_tema = bod
                elif m.group(2):
                    tema_map[(m.group(2).lower(), m.group(3).lower())] = current_tema
        return tema_map

    def _parse_speeches(self, page_url: str, html_text: str, datum: str | None) -> list[_ParsedSpeech]:
        matches = list(_ANCHOR_START.finditer(html_text))
        if not matches:
            return []
        page_end = self._page_content_end(html_text, after=matches[0].start())
        speeches: list[_ParsedSpeech] = []
        for i, m in enumerate(matches):
            start = m.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else page_end
            block = html_text[start:end]
            first_p_end = block.find("</p>")
            if first_p_end == -1:
                body_html = block[m.end() - start :]
            else:
                body_html = block[m.end() - start : first_p_end] + block[first_p_end + 4 :]
            text = self._html_to_text(body_html)
            speeches.append(
                _ParsedSpeech(
                    anchor=m.group(1).lower(),
                    speaker_label=m.group(2),
                    text=text,
                    page_url=page_url,
                    datum=datum,
                )
            )
        return speeches

    def _tema_for(
        self,
        tema_map: dict[tuple[str, str], str],
        page_file: str,
        anchor: str,
        speaker_label: str,
        last_tema: str,
    ) -> str:
        key = (page_file.lower(), anchor.lower())
        if key in tema_map:
            return tema_map[key]
        if speaker_label.startswith(("Předsedající ", "Predsedajici ")):
            return last_tema or "Zahájení schůze"
        return last_tema or "Zahájení schůze"

    def iter_steno(
        self,
        obdobi: int,
        schuze: int,
        *,
        start: int = 1,
        max_records: int | None = None,
    ) -> Iterator[StenoRecord]:
        tema_map = self._parse_tema_map(obdobi, schuze)
        poradi = 0
        last_tema = "Zahájení schůze"
        current_datum: str | None = None

        base = self.schuze_base_url(obdobi, schuze)
        for page_url, html_text in self._walk_pages(base, self.first_steno_page(schuze)):
            page_datum = self._parse_date(html_text)
            if page_datum:
                current_datum = page_datum
            page_file = page_url.rsplit("/", 1)[-1]

            for speech in self._parse_speeches(page_url, html_text, current_datum):
                poradi += 1
                if poradi < start:
                    last_tema = self._tema_for(
                        tema_map, page_file, speech.anchor, speech.speaker_label, last_tema
                    )
                    continue
                tema = self._tema_for(
                    tema_map, page_file, speech.anchor, speech.speaker_label, last_tema
                )
                last_tema = tema
                record_url = f"{speech.page_url}#{speech.anchor}"
                yield StenoRecord(
                    id=HlidacClient.steno_id(obdobi, schuze, poradi),
                    poradi=poradi,
                    obdobi=obdobi,
                    schuze=schuze,
                    datum=speech.datum,
                    cele_jmeno=self._cele_jmeno(speech.speaker_label),
                    tema=tema,
                    text=speech.text,
                    pocet_slov=self._pocet_slov(speech.text),
                    url=record_url,
                    cislo_hlasovani=None,
                )
                if max_records is not None and poradi - start + 1 >= max_records:
                    return
