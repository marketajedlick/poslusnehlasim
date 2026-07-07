"""Hledání kandidátů na jazykolam dne ve stenoprotokolu."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

from svejk.build.io import iter_jsonl
from svejk.build.steno_text import (
    detekuj_predsedajici,
    je_organizacni_vstup,
    rozdelit_vety_steno,
    veta_je_hluk,
)

WORD_RE = re.compile(r"\b[\wáčďéěíňóřšťúůýžÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ-]+\b")
CISLO_SBIRKY = re.compile(r"\b\d{1,4}/\d{4}\s*Sb\.", re.I)
PROCEDURALNI_CTECKA = re.compile(r"ve znění pozdějších předpisů|sněmovní tisk \d+/", re.I)
HARD_CLUSTERS = re.compile(
    r"strč|prst|skrz|krk|ště|šč|ři|ře|předp|pozměň|zákonod|poslaneck|stanovisk|"
    r"ministerst|organizac|sociáln|ústavní|přechodn|předpokl|předlož|přijm|předpis|"
    r"jízdn|pruz|komunikac|přislíb|transpozic|směrnic",
    re.I,
)

# Opakující se šablony, které se špatně čtou nahlas.
TWISTER_TEMPLATES: tuple[tuple[str, int], ...] = (
    (r"můžeme se bavit o", 25),
    (r"zákon o .{3,30} zákon", 20),
    (r"\bzákon\b.*\bzákon\b.*\bzákon\b", 18),
    (r"pozměňovací návrh.*pozměňovací", 22),
    (r"před .{0,20} před", 12),
    (r"poslaneck.*poslaneck", 15),
    (r"stanovisko.*stanovisk", 14),
    (r"ministerstvo.*ministerst", 14),
    (r"organizac.*organizac", 14),
    (r"sociální.*sociální", 12),
    (r"ústavní.*ústavní", 16),
    (r"transpozic.*transpozic|směrnic.*směrnic|nařízení.*nařízení", 16),
    (r"účinnost.*účinnost", 14),
    (r"právní.*právní", 10),
    (r"veřejn.*veřejn", 10),
    (r"účast přislíbili", 18),
    (r"drahé jsou", 16),
    (r"jízdních pruz", 20),
    (r"musí fungovat.*musí fungovat", 14),
    (r"kolik.*kolik.*kolik", 14),
    (r"formuje.*formuje", 16),
    (r"baterií.*baterií", 14),
    (r"máme je na.*máme je na", 18),
)


@dataclass(frozen=True)
class JazykolamKandidat:
    skore: int
    text: str
    recnik: str
    steno_id: str
    tema: str


def _skore_vyslovnost(veta: str) -> int:
    """Čím víc bodů, tím hůř se věta čte nahlas."""
    if veta_je_hluk(veta):
        return -99
    n = len(veta)
    if n < 40 or n > 250:
        return -1
    if CISLO_SBIRKY.search(veta) and PROCEDURALNI_CTECKA.search(veta):
        return -1

    words = WORD_RE.findall(veta)
    if len(words) < 6:
        return -1

    sk = 0
    low = veta.lower()

    for pat, pts in TWISTER_TEMPLATES:
        if re.search(pat, low, re.I | re.DOTALL):
            sk += pts

    prefixes = Counter(w[:3].lower() for w in words if len(w) >= 4)
    for pref, cnt in prefixes.most_common(3):
        if cnt >= 3:
            sk += cnt * 4

    clusters = len(HARD_CLUSTERS.findall(veta))
    if clusters >= 4:
        sk += clusters * 3

    for i, w in enumerate(words[:-1]):
        if len(w) >= 4 and w.lower() == words[i + 1].lower():
            sk += 12
            break

    wc = Counter(w.lower() for w in words if len(w) >= 4)
    sk += sum(c - 1 for c in wc.values() if c > 1) * 4

    if re.search(r"\d{1,4}/\d{4}\s*Sb", veta):
        sk -= 20
    if veta.count("§") >= 2:
        sk -= 15
    if re.search(r"ve znění pozdějších", low):
        sk -= 20

    if 60 <= n <= 130:
        sk += 4

    return sk


def kandidati_z_dne(
    steno_records: list[dict[str, Any]],
    *,
    iso_date: str,
    limit: int = 5,
    min_skore: int = 15,
) -> list[JazykolamKandidat]:
    predsed = detekuj_predsedajici(steno_records)
    cands: list[JazykolamKandidat] = []
    seen: set[str] = set()

    for rec in steno_records:
        datum = (rec.get("datum") or "")[:10]
        if datum != iso_date:
            continue
        if je_organizacni_vstup(rec, predsed_jmena=predsed):
            continue
        recnik = (rec.get("cele_jmeno") or "").strip()
        if not recnik or recnik.isdigit():
            continue

        for veta in rozdelit_vety_steno(rec.get("text") or ""):
            sk = _skore_vyslovnost(veta)
            if sk < min_skore:
                continue
            key = veta[:60].lower()
            if key in seen:
                continue
            seen.add(key)
            cands.append(
                JazykolamKandidat(
                    skore=sk,
                    text=veta if veta.endswith((".", "!", "?")) else f"{veta}.",
                    recnik=recnik,
                    steno_id=(rec.get("id") or "").strip(),
                    tema=(rec.get("tema") or "").strip()[:80],
                )
            )

    cands.sort(key=lambda c: (-c.skore, -len(c.text)))
    return cands[:limit]


def kandidati_pro_schuze(paths, iso_date: str, *, limit: int = 5) -> list[JazykolamKandidat]:
    steno = list(iter_jsonl(paths.steno_jsonl))
    return kandidati_z_dne(steno, iso_date=iso_date, limit=limit)
