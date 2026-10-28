#!/usr/bin/env python3
"""Znovu dohledá kotvy PSP, které se uložily proti zastaralému psp_steno_index.json.

U běžící schůze se seznam stránek neobnovoval: projev na stránce mimo seznam dostal
jen odkaz na začátek projevu a ten se natrvalo uložil do psp_url_cache.json.
Skript stáhne aktuální seznam stránek a takové záznamy dohledá znovu. Nenalezené
nechá být: stará hodnota (začátek projevu) není horší než to, co by dal build bez ní.

Bez --apply jen vypíše, co by změnil. Volitelně čísla schůzí: fix_stale_psp_url_cache.py 34 33
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from svejk.build.io import read_json, write_json  # noqa: E402
from svejk.build.steno_sources import (  # noqa: E402
    _PSP_URL_CACHE_VERSION,
    PspUrlResolver,
    _psp_index_path,
    _psp_url_cache_path,
)
from svejk.paths import SchuzePaths, processed_root  # noqa: E402

OBDOBI = 2025


def _schuze_list(only: set[int]) -> list[int]:
    out = []
    for p in processed_root().glob(f"{OBDOBI}-s*"):
        try:
            cislo = int(p.name.split("-s", 1)[1])
        except ValueError:
            continue
        if not only or cislo in only:
            out.append(cislo)
    return sorted(out)


def fix_schuze(schuze: int, *, apply: bool) -> tuple[int, int, int]:
    paths = SchuzePaths.create(OBDOBI, schuze)
    index_path = _psp_index_path(paths)
    cache_path = _psp_url_cache_path(paths)
    if not index_path.is_file() or not cache_path.is_file():
        return 0, 0, 0
    old_pages = set(read_json(index_path).get("page_urls") or [])
    resolved: dict[str, str] = read_json(cache_path).get("resolved") or {}
    stale = {
        k: v
        for k, v in resolved.items()
        # Klíče bez verze (starší formát) lookup nečte, nechat být.
        if k.startswith(f"{_PSP_URL_CACHE_VERSION}|")
        and (k.split("|")[1] not in old_pages or v.split("#", 1)[0] not in old_pages)
    }
    if not stale:
        return 0, 0, 0

    resolver = PspUrlResolver(paths)
    resolver._load_pages()
    if apply:
        resolver._fetch_pages(full=True)
    else:
        # Starý seznam bývá děravý i uprostřed → vždy celý.
        resolver._page_urls = resolver._fetcher_lazy().list_steno_page_urls(OBDOBI, schuze)
    fixed = kept = 0
    for key, old_url in stale.items():
        _, base, citace = key.split("|", 2)
        # Stará hodnota nese kotvu řečníka na úvodní stránce projevu.
        fallback = old_url if old_url.split("#", 1)[0] == base else base
        new_url = resolver._resolve_online("", fallback, citace)
        if resolver._found_on_page(new_url, citace):
            if new_url != old_url:
                print(f"  s{schuze}: {old_url}\n        → {new_url}")
            resolved[key] = new_url
            fixed += 1
        else:
            print(f"  s{schuze}: nenalezeno, ponechat {old_url}: {citace[:60]!r}")
            kept += 1
    if apply:
        write_json(cache_path, {"resolved": resolved})
    return len(stale), fixed, kept


def main(argv: list[str]) -> int:
    apply = "--apply" in argv
    only = {int(a) for a in argv if a.isdigit()}
    for schuze in _schuze_list(only):
        total, fixed, kept = fix_schuze(schuze, apply=apply)
        if total:
            print(f"s{schuze}: {total} podezřelých, {fixed} ověřeno, {kept} ponecháno")
    if not apply:
        print("(dry run — přidej --apply)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
