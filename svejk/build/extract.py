"""Extrakce faktů do facts/by_topic a indexu dnů."""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime
from typing import Any

from svejk.build.io import iter_jsonl, read_json, write_json
from svejk.listy import (
    KDO_KLIC,
    PREDMET_LIDSKY,
    _format_koho_veta,
    _glosa_je_nedostatecna,
    _predmet_z_nazvu,
    _rozdelit_vety,
    _text_ma_koho,
    _topic_key,
    _veta_je_odhad_dopadu,
    _veta_ma_konkretni_dopad,
)
from svejk.obcansky import glosa_pro_obcana
from svejk.paths import SchuzePaths


def _verdikt(proslo: bool, nazev: str, vysvetleni: str) -> str:
    t = (nazev + " " + vysvetleni).lower()
    if any(w in t for w in ("nestihl", "odlož", "posun digitalizace", "úřady nestihly")):
        return "odlozeno"
    return "schvaleno" if proslo else "zamiteno"


def _lead_predmet(nazev: str) -> str:
    key = _topic_key(nazev)
    if key in PREDMET_LIDSKY:
        return PREDMET_LIDSKY[key]
    p = _predmet_z_nazvu(nazev)
    return p or ""


def _koho_z_glosy(gloss: str) -> list[str]:
    vety = _rozdelit_vety(gloss)
    out: list[str] = []
    for v in vety:
        low = v.lower()
        if not any(k in low for k in KDO_KLIC):
            continue
        if _veta_je_odhad_dopadu(v):
            continue
        if _veta_ma_konkretni_dopad(v) and not low.startswith("týká"):
            continue
        out.append(_format_koho_veta(v) if low.startswith("týká") else v)
    return out[:1]


def _fakty_z_glosy(gloss: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for v in _rozdelit_vety(gloss):
        if _veta_je_odhad_dopadu(v):
            continue
        if _veta_ma_konkretni_dopad(v):
            out.append({"text": v.strip(), "source": "manual", "note": "z glosy / TEMA_PRAVIDLA"})
    return out[:3]


def _fakty_z_steno(steno_text: str, steno_id: str) -> list[dict[str, Any]]:
    """Regex: částky, data, povinnosti."""
    out: list[dict[str, Any]] = []
    if not steno_text or steno_text.strip().lower() == "neautorizováno!":
        return out

    patterns = [
        (
            r"(\d{1,2}\s*\d{3})\s*(?:korun|Kč)",
            "částka",
        ),
        (
            r"od\s+(?:1\.\s*)?ledna(?:\s+\d{4})?",
            "datum",
        ),
        (
            r"k\s+1\.\s*\d{1,2}\.\s*\d{4}",
            "datum",
        ),
        (
            r"(?:klesne|sníží|zvýší|zůstane)\s+[^.]{10,80}\.",
            "změna",
        ),
    ]
    seen: set[str] = set()
    for pat, _kind in patterns:
        for m in re.finditer(pat, steno_text, re.I):
            start = max(0, m.start() - 40)
            end = min(len(steno_text), m.end() + 80)
            citace = steno_text[start:end].strip()
            citace = re.sub(r"\s+", " ", citace)[:200]
            veta = re.sub(r"\s+", " ", steno_text[max(0, m.start() - 60) : m.end() + 60]).strip()
            if len(veta) > 20 and veta not in seen:
                seen.add(veta)
                out.append(
                    {
                        "text": veta[:300],
                        "source": "steno",
                        "steno_id": steno_id,
                        "citace": citace,
                    }
                )
    return out[:2]


def _priorita(koho: list[str], fakty: list[dict]) -> int:
    if not koho:
        return 0
    if fakty:
        return 2
    return 1


def _nadpis_fallback(nazev: str, proslo: bool) -> str:
    from svejk.listy import _nadpis_bodu
    from svejk.timeline import BlokDne

    b = BlokDne(
        cas_od="12:00",
        cas_do="",
        typ="law",
        svejk="",
        nazev=nazev,
        proslo=proslo,
    )
    return _nadpis_bodu(b)


def run_extract(paths: SchuzePaths) -> dict[str, Any]:
    paths.ensure_dirs()
    aligned = read_json(paths.topics_json)
    topics: list[dict] = aligned.get("topics", [])

    steno_by_id: dict[str, dict] = {}
    for s in iter_jsonl(paths.steno_jsonl):
        steno_by_id[s["id"]] = s

    written = 0
    with_facts = 0
    by_day_topics: dict[str, list[str]] = defaultdict(list)

    for topic in topics:
        if topic.get("kategorie") != "substantivni":
            continue

        nazev = topic["nazev"]
        proslo = topic.get("proslo", False)
        vysv = topic.get("tema_vysvetleni") or ""
        gloss = glosa_pro_obcana(nazev, vysv, proslo=proslo)

        koho = _koho_z_glosy(gloss) if gloss and not _glosa_je_nedostatecna(gloss) else []
        fakty = _fakty_z_glosy(gloss) if gloss else []

        for sid in topic.get("steno_ids") or []:
            rec = steno_by_id.get(sid)
            if rec:
                fakty.extend(_fakty_z_steno(rec.get("text") or "", sid))

        # dedupe fakty by text prefix
        seen_f: set[str] = set()
        uniq_f: list[dict] = []
        for f in fakty:
            key = f["text"][:60].lower()
            if key not in seen_f:
                seen_f.add(key)
                uniq_f.append(f)
        fakty = uniq_f[:4]

        priorita = _priorita(koho, fakty)
        publikovat = priorita > 0 and not (
            gloss and _glosa_je_nedostatecna(gloss) and not koho
        )

        fact = {
            "slug": topic["slug"],
            "nazev": nazev,
            "datum": topic.get("datum", ""),
            "verdikt": _verdikt(proslo, nazev, vysv),
            "predmet_lidsky": _lead_predmet(nazev),
            "koho": koho,
            "fakty": fakty,
            "publikovat": publikovat,
            "priorita": priorita,
            "nadpis": _nadpis_fallback(nazev, proslo),
            "pocet_hlasovani": topic.get("pocet_hlasovani", 0),
            "proslo": proslo,
        }
        write_json(paths.facts_by_topic / f"{topic['slug']}.json", fact)
        written += 1
        if fakty:
            with_facts += 1

        datum = topic.get("datum", "")
        if datum and publikovat:
            by_day_topics[datum].append(topic["slug"])

    # statistiky dne z votes
    votes = list(iter_jsonl(paths.votes_jsonl))
    days = sorted({v["datum"] for v in votes if v.get("datum")})
    for datum in days:
        day_votes = [v for v in votes if v.get("datum") == datum]
        zakony = [
            v
            for v in day_votes
            if not v.get("je_porad_schuze") and (v.get("nazev") or "").strip()
        ]
        proslo = sum(1 for v in zakony if v.get("vysledek") == "A")
        zamitnuto = sum(1 for v in zakony if v.get("vysledek") == "R")
        pocet_hlas = sum(
            1 for v in day_votes if v.get("je_porad_schuze") or (v.get("nazev") or "").strip()
        )
        times = [v.get("cas", "") for v in day_votes if v.get("cas")]
        start = times[0][:5] if times else ""
        end = times[-1][:5] if times else ""
        minuty = 0
        if start and end:
            sh, sm = int(start[:2]), int(start[3:5])
            eh, em = int(end[:2]), int(end[3:5])
            minuty = max(0, (eh * 60 + em) - (sh * 60 + sm))

        slugs = by_day_topics.get(datum, [])
        slug_meta = []
        for slug in slugs:
            fp = paths.facts_by_topic / f"{slug}.json"
            if fp.is_file():
                f = read_json(fp)
                slug_meta.append(
                    {"slug": slug, "priorita": f.get("priorita", 0), "pocet_hlasovani": f.get("pocet_hlasovani", 0)}
                )
        slug_meta.sort(key=lambda x: (-x["priorita"], -x["pocet_hlasovani"]))

        d = datetime.strptime(datum, "%d.%m.%Y")
        write_json(
            paths.facts_by_day / f"{d.strftime('%Y-%m-%d')}.json",
            {
                "datum": datum,
                "den": ["pondělí", "úterý", "středa", "čtvrtek", "pátek", "sobota", "neděle"][d.weekday()],
                "topic_slugs": [x["slug"] for x in slug_meta],
                "stats": {
                    "pocet_hlas": pocet_hlas or len(zakony),
                    "minuty": minuty,
                    "end_cas": end,
                    "proslo": proslo,
                    "zamitnuto": zamitnuto,
                    "dlouha_debata": False,
                },
            },
        )

    return {"topics_written": written, "with_concrete_facts": with_facts, "days": len(days)}
