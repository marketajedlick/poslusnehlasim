"""Spárování hlasování (UNL) se stenozáznamy."""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from typing import Any

from svejk.build.io import iter_jsonl, write_json
from svejk.build.vote_logic import (
    topic_proslo_druhe_cteni_ukonceno,
    topic_proslo_from_votes,
    vote_kategorie,
)
from svejk.jednaci_den import vote_jednaci_datum
from svejk.paths import SchuzePaths
from svejk.obcansky import tema_z_nazvu


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


_HLASOVANI_CISLO_RE = re.compile(r"hlasování(?:\s+pořadové)?\s+číslo\s+(\d+)", re.I)
_BOD_HEADER_RE = re.compile(r"^\s*(\d+)\s*\.")


def _steno_jiny_bod_v_textu(text: str, bod: str) -> bool:
    """Hlídač nechá staré `tema`; hlavička „109.Návrh…“ na začátku textu je spolehlivější."""
    if not bod:
        return False
    m = _BOD_HEADER_RE.match(text)
    if not m:
        return False
    return m.group(1) != str(bod).strip()


def _vote_dates_iso(votes: list[dict]) -> set[str]:
    out: set[str] = set()
    for v in votes:
        d = (v.get("datum") or "").strip()
        parts = d.split(".")
        if len(parts) == 3:
            out.add(f"{parts[2]}-{parts[1]}-{parts[0]}")
    return out


def _cislo_poradi_window(
    ids_cislo: list[str], steno_poradi: dict[str, int], margin: int = 3
) -> set[int] | None:
    if not ids_cislo:
        return None
    out: set[int] = set()
    for sid in ids_cislo:
        p = steno_poradi.get(sid)
        if p:
            out.update(range(p - margin, p + margin + 1))
    return out or None


def _steno_podle_hlasovani(
    steno: list[dict], known_cisla: set[int]
) -> dict[int, list[str]]:
    """Mapa lokální číslo hlasování -> steno id.

    Hlídač vrací v `cislo_hlasovani` globální ID hlasování (např. 87588),
    ne pořadové číslo ve schůzi. Lokální čísla se berou z textu
    („V hlasování číslo 6 …“); záznamy bez ohlášení v textu se dopočítají
    nejčastějším offsetem globální ID - lokální číslo.
    """
    from collections import Counter

    parsed: dict[str, list[int]] = {}
    offsets: Counter[int] = Counter()
    for s in steno:
        ch = s.get("cislo_hlasovani")
        if ch is None:
            continue
        locs = [int(x) for x in _HLASOVANI_CISLO_RE.findall(s.get("text") or "")]
        locs = [x for x in locs if x in known_cisla]
        if locs:
            parsed[s["id"]] = locs
            offsets[int(ch) - locs[0]] += 1
    offset = offsets.most_common(1)[0][0] if offsets else 0

    out: dict[int, list[str]] = defaultdict(list)
    for s in steno:
        ch = s.get("cislo_hlasovani")
        if ch is None:
            continue
        ch = int(ch)
        locs = parsed.get(s["id"])
        if not locs:
            if offsets and (ch - offset) in known_cisla:
                locs = [ch - offset]
            elif not offsets and ch in known_cisla:
                locs = [ch]
            else:
                continue
        for c in locs:
            if s["id"] not in out[c]:
                out[c].append(s["id"])
    for s in steno:
        for c in _HLASOVANI_CISLO_RE.findall(s.get("text") or ""):
            ci = int(c)
            if ci in known_cisla and s["id"] not in out[ci]:
                out[ci].append(s["id"])
    return out


def _steno_podle_bodu(
    steno: list[dict], topics_by_bod: dict[str, list[dict]]
) -> dict[str, list[str]]:
    """Fallback, když `tema` v steno nesedí (Hlídač občas všem záznamům
    nechá téma prvního bodu): segmentace podle hlaviček „1.Vládní návrh …“
    na začátku textu, projevy do další hlavičky patří k danému bodu."""
    out: dict[str, list[str]] = defaultdict(list)
    current: str | None = None
    for s in sorted(steno, key=lambda r: int(r.get("poradi") or 0)):
        text = s.get("text") or ""
        m = _BOD_HEADER_RE.match(text)
        if m:
            current = None
            for t in topics_by_bod.get(m.group(1), []):
                if _tema_match(t["nazev"], text[:400]):
                    current = t["slug"]
                    break
        if current:
            out[current].append(s["id"])
    return out


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

    known_cisla = {int(v["cislo"]) for v in votes if v.get("cislo") is not None}
    steno_by_cislo = _steno_podle_hlasovani(steno, known_cisla)
    steno_poradi = {s["id"]: int(s.get("poradi") or 0) for s in steno}

    topics: list[dict[str, Any]] = []
    seen_slugs: set[str] = set()
    slug_by_key: dict[tuple[str, str], str] = {}
    topics_by_bod: dict[str, list[dict]] = defaultdict(list)

    for (bod, nazev) in sorted(by_key, key=lambda x: (x[0], x[1])):
        slug = _slug(nazev)
        base = slug
        i = 2
        while slug in seen_slugs:
            slug = f"{base}-{i}"
            i += 1
        seen_slugs.add(slug)
        slug_by_key[(bod, nazev)] = slug
        topics_by_bod[bod].append({"slug": slug, "nazev": nazev})

    steno_by_bod = _steno_podle_bodu(steno, topics_by_bod)

    for (bod, nazev), group in sorted(by_key.items(), key=lambda x: (x[0][0], x[0][1])):
        group.sort(key=lambda v: (v.get("datum", ""), v.get("cas", "")))
        last = group[-1]
        datum = vote_jednaci_datum(last)
        cisla = [int(v["cislo"]) for v in group if v.get("cislo") is not None]
        prijato = sum(1 for v in group if v.get("vysledek") == "A")
        zamitnuto = sum(1 for v in group if v.get("vysledek") == "R")

        slug = slug_by_key[(bod, nazev)]

        vote_days = _vote_dates_iso(group)
        ids_cislo: list[str] = []
        for c in cisla:
            ids_cislo.extend(steno_by_cislo.get(c, []))
        cislo_win = _cislo_poradi_window(ids_cislo, steno_poradi)
        ids_tema = [
            s["id"]
            for s in steno
            if _tema_match(nazev, s.get("tema") or "")
            and not _steno_jiny_bod_v_textu(s.get("text") or "", bod)
            and (not vote_days or (s.get("datum") or "")[:10] in vote_days)
            and (cislo_win is None or int(s.get("poradi") or 0) in cislo_win)
        ]

        steno_ids: list[str] = []
        for sid in ids_cislo + ids_tema:
            if sid not in steno_ids:
                steno_ids.append(sid)
        for sid in steno_by_bod.get(slug, []):
            if sid not in steno_ids:
                steno_ids.append(sid)
        steno_ids.sort(key=lambda sid: steno_poradi.get(sid, 0))

        proslo = topic_proslo_from_votes(group)
        if not proslo and steno_ids:
            steno_by_id = {s["id"]: s for s in steno}
            steno_texts = [
                steno_by_id[sid]["text"]
                for sid in steno_ids
                if sid in steno_by_id and (steno_by_id[sid].get("text") or "").strip()
            ]
            if topic_proslo_druhe_cteni_ukonceno(steno_texts):
                proslo = True

        kat = vote_kategorie(nazev)
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
                "tema_svejk": (t := tema_z_nazvu(nazev))[0],
                "tema_vysvetleni": t[1],
            }
        )

    payload = {"obdobi": paths.obdobi, "schuze": paths.schuze, "topics": topics}
    write_json(paths.topics_json, payload)
    return {"topics": len(topics)}
