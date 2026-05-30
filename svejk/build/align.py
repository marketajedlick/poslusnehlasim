"""Spárování hlasování (UNL) se stenozáznamy."""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from typing import Any

from svejk.build.io import iter_jsonl, write_json
from svejk.noviny import _law_kategorie
from svejk.paths import SchuzePaths
from svejk.timeline import BlokDne, tema_z_nazvu


def _slug(text: str) -> str:
    norm = unicodedata.normalize("NFKD", text)
    ascii_text = norm.encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    return s[:48] or "topic"


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower().strip())


def _tema_match(nazev: str, tema: str) -> bool:
    n, t = _norm(nazev), _norm(tema)
    if not n or not t:
        return False
    if n in t or t in n:
        return True
    nw = {w for w in re.findall(r"\w{4,}", n)}
    tw = {w for w in re.findall(r"\w{4,}", t)}
    if not nw or not tw:
        return False
    return len(nw & tw) / min(len(nw), len(tw)) >= 0.35


def _vote_kategorie(nazev: str) -> str:
    blok = BlokDne(
        cas_od="",
        cas_do="",
        typ="law",
        svejk="",
        nazev=nazev,
    )
    return _law_kategorie(blok)


def run_align(paths: SchuzePaths) -> dict[str, Any]:
    paths.ensure_dirs()
    votes = list(iter_jsonl(paths.votes_jsonl))
    steno = list(iter_jsonl(paths.steno_jsonl))

    by_key: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for v in votes:
        if v.get("je_porad_schuze"):
            continue
        nazev = (v.get("nazev") or "").strip()
        if not nazev:
            continue
        key = (v.get("bod") or "", nazev)
        by_key[key].append(v)

    steno_by_cislo: dict[int, list[str]] = defaultdict(list)
    for s in steno:
        ch = s.get("cislo_hlasovani")
        if ch is not None:
            steno_by_cislo[int(ch)].append(s["id"])

    topics: list[dict[str, Any]] = []
    seen_slugs: set[str] = set()

    for (bod, nazev), group in sorted(by_key.items(), key=lambda x: (x[0][0], x[0][1])):
        group.sort(key=lambda v: (v.get("datum", ""), v.get("cas", "")))
        last = group[-1]
        datum = last.get("datum", "")
        cisla = [int(v["cislo"]) for v in group if v.get("cislo") is not None]
        prijato = sum(1 for v in group if v.get("vysledek") == "A")
        zamitnuto = sum(1 for v in group if v.get("vysledek") == "R")
        proslo = last.get("vysledek") == "A"

        slug = _slug(nazev)
        base = slug
        i = 2
        while slug in seen_slugs:
            slug = f"{base}-{i}"
            i += 1
        seen_slugs.add(slug)

        steno_ids: list[str] = []
        for c in cisla:
            steno_ids.extend(steno_by_cislo.get(c, []))
        if not steno_ids:
            for s in steno:
                if _tema_match(nazev, s.get("tema") or ""):
                    sid = s.get("id")
                    if sid and sid not in steno_ids:
                        steno_ids.append(sid)

        kat = _vote_kategorie(nazev)
        topics.append(
            {
                "slug": slug,
                "nazev": nazev,
                "bod": bod,
                "datum": datum,
                "vote_cisla": cisla,
                "steno_ids": steno_ids,
                "proslo": proslo,
                "pocet_hlasovani": len(group),
                "pocet_prijato": prijato,
                "pocet_zamitnuto": zamitnuto,
                "kategorie": kat,
                "tema_svejk": tema_z_nazvu(nazev).svejk,
                "tema_vysvetleni": tema_z_nazvu(nazev).vysvetleni,
            }
        )

    payload = {"obdobi": paths.obdobi, "schuze": paths.schuze, "topics": topics}
    write_json(paths.topics_json, payload)
    return {"topics": len(topics)}
