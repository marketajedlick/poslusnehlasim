"""Klient API Hlídače státu – dataset stenozaznamy-psp."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Iterator


@dataclass
class StenoRecord:
    id: str
    poradi: int
    obdobi: int
    schuze: int
    datum: str | None
    cele_jmeno: str
    tema: str
    text: str
    pocet_slov: int
    url: str | None
    cislo_hlasovani: int | None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> StenoRecord:
        return cls(
            id=data.get("id") or data.get("Id") or "",
            poradi=int(data.get("poradi") or 0),
            obdobi=int(data.get("obdobi") or 0),
            schuze=int(data.get("schuze") or 0),
            datum=data.get("datum"),
            cele_jmeno=data.get("celeJmeno") or "",
            tema=data.get("tema") or "",
            text=data.get("text") or "",
            pocet_slov=int(data.get("pocetSlov") or 0),
            url=data.get("url"),
            cislo_hlasovani=data.get("cisloHlasovani"),
        )


def normalize_hlidac_token(token: str) -> str:
    """Očistí token a ověří, že jde o ASCII (urllib vyžaduje latin-1 v hlavičkách)."""
    cleaned = token.strip().strip('"').strip("'")
    if not cleaned:
        raise ValueError("HLIDAC_TOKEN je prázdný.")
    if not cleaned.isascii():
        bad = [c for c in cleaned if ord(c) > 127][:5]
        raise ValueError(
            "HLIDAC_TOKEN obsahuje znaky mimo ASCII "
            f"({bad!r}). Zkopíruj token z hlidacstatu.cz — bez diakritiky a mezer navíc."
        )
    return cleaned


class HlidacClient:
    """REST klient pro stenozáznamy PSP."""

    BASE = "https://api.hlidacstatu.cz/api/v2/datasety/stenozaznamy-psp"

    def __init__(self, token: str, rate_limit_s: float = 1.0):
        self.token = normalize_hlidac_token(token)
        self.rate_limit_s = rate_limit_s
        self._last_request = 0.0

    def _wait(self) -> None:
        elapsed = time.monotonic() - self._last_request
        if elapsed < self.rate_limit_s:
            time.sleep(self.rate_limit_s - elapsed)
        self._last_request = time.monotonic()

    def _request(self, url: str, *, max_retries: int = 8) -> dict[str, Any]:
        last_err: urllib.error.HTTPError | None = None
        for attempt in range(max_retries):
            self._wait()
            req = urllib.request.Request(
                url,
                headers={"Authorization": f"Token {self.token}"},
            )
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    return json.loads(resp.read())
            except urllib.error.HTTPError as e:
                last_err = e
                if e.code == 429:
                    retry_after = e.headers.get("Retry-After")
                    try:
                        wait = float(retry_after) if retry_after else 0.0
                    except ValueError:
                        wait = 0.0
                    if wait <= 0:
                        wait = min(120.0, 5.0 * (2**attempt))
                    time.sleep(wait)
                    continue
                raise
        if last_err:
            raise last_err
        raise RuntimeError("request failed without HTTPError")

    @staticmethod
    def steno_id(obdobi: int, schuze: int, poradi: int) -> str:
        return f"{obdobi}_{schuze}_{poradi:05d}"

    def fetch_steno(self, record_id: str) -> StenoRecord | None:
        """Načte jeden stenozáznam podle ID (např. 2025_20_00011)."""
        try:
            data = self._request(f"{self.BASE}/zaznamy/{record_id}")
            return StenoRecord.from_api(data)
        except urllib.error.HTTPError as e:
            # Konec schůze: API vrací 404 nebo 400 na neplatné / chybějící pořadí
            if e.code in (400, 404):
                return None
            raise

    def iter_steno(
        self,
        obdobi: int,
        schuze: int,
        start: int = 1,
        max_records: int | None = None,
    ) -> Iterator[StenoRecord]:
        """Projde stenozáznamy schůze sekvenčně podle pořadí."""
        count = 0
        for poradi in range(start, start + (max_records or 10_000)):
            record = self.fetch_steno(self.steno_id(obdobi, schuze, poradi))
            if record is None:
                break
            yield record
            count += 1
            if max_records is not None and count >= max_records:
                break

    def find_by_keywords(
        self,
        obdobi: int,
        schuze: int,
        keywords: list[str],
        max_scan: int = 400,
    ) -> list[StenoRecord]:
        """Projde záznamy schůze a vrátí ty, kde keyword padne do textu/tématu/jména."""
        keywords_lower = [k.lower() for k in keywords]
        found: list[StenoRecord] = []
        for record in self.iter_steno(obdobi, schuze, max_records=max_scan):
            haystack = " ".join(
                [record.text, record.tema, record.cele_jmeno]
            ).lower()
            if any(kw in haystack for kw in keywords_lower):
                found.append(record)
        return found

    def top_speeches(
        self,
        obdobi: int,
        schuze: int,
        min_words: int = 200,
        max_scan: int = 400,
        limit: int = 20,
    ) -> list[StenoRecord]:
        """Vrátí nejdelší projevy schůze."""
        speeches = [
            r
            for r in self.iter_steno(obdobi, schuze, max_records=max_scan)
            if r.pocet_slov >= min_words and r.text.strip() not in ("", "Neautorizováno!")
        ]
        speeches.sort(key=lambda r: r.pocet_slov, reverse=True)
        return speeches[:limit]
