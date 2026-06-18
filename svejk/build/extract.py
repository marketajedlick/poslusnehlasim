"""Extrakce faktů do facts/by_topic a indexu dnů."""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime
from typing import Any

from svejk.build.io import iter_jsonl, read_json, write_json
from svejk.build.vote_logic import topic_proslo_from_votes, vote_kategorie
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


def _steno_konec_schuze(steno_path) -> str:
    """Čas ukončení ze scénické poznámky ve stenoprotokolu (HH:MM)."""
    if not steno_path.is_file():
        return ""
    pat = re.compile(r"Schůze skončila v (\d{1,2})\.(\d{2})\s*hodin", re.I)
    for rec in iter_jsonl(steno_path):
        m = pat.search(rec.get("text") or "")
        if m:
            return f"{int(m.group(1)):02d}:{m.group(2)}"
    return ""


def _verdikt(proslo: bool, nazev: str, vysvetleni: str) -> str:
    t = (f"{nazev} {vysvetleni}").lower()
    if any(
        w in t
        for w in (
            "odlož",
            "odklad",
            "odsun",
            "odroč",
            "přeruš",
            "pozastav",
            "nestihl",
            "posun",
            "prodlouž",
            "lhůt",
            "úřady nestihly",
        )
    ):
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


def _vote_signaly(votes: list[dict[str, Any]]) -> dict[str, int | bool]:
    proti_vals = [int(v.get("proti") or 0) for v in votes]
    pritomno_vals = [int(v.get("pritomno") or 0) for v in votes if v.get("pritomno")]
    max_proti = max(proti_vals, default=0)
    min_pritomno = min(pritomno_vals, default=200)
    jednomyslne = bool(votes) and all(int(v.get("proti") or 0) == 0 for v in votes)
    return {
        "proti_max": max_proti,
        "pritomno_min": min_pritomno,
        "jednomyslne": jednomyslne,
        "spor": max_proti > 0,
        "prazdny_sal": bool(pritomno_vals) and min_pritomno < 170,
    }


def _priorita(
    koho: list[str],
    fakty: list[dict],
    *,
    signaly: dict[str, int | bool] | None = None,
) -> int:
    if not koho and not fakty:
        return 0
    p = 2 if fakty else 1
    if not koho:
        p = 1 if fakty else 0
    if signaly:
        if signaly.get("spor"):
            p += 1
        if signaly.get("prazdny_sal"):
            p += 1
        if any(f.get("kind") == "scene" for f in fakty):
            p += 1
    return min(p, 3)


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


_PROSLO_VERDIKTY = frozenset({"schvaleno", "zvoleno"})
_ZAMITNUTO_VERDIKTY = frozenset({"zamiteno", "odlozeno"})


def skore_z_verdiktu(slugs: list[str], paths: SchuzePaths) -> tuple[int, int]:
    """Stav zápasu z publikovaných článků: schváleno/zvoleno vs. zamítnuto/odloženo."""
    proslo = zamitnuto = 0
    for slug in slugs:
        fp = paths.facts_by_topic / f"{slug}.json"
        if not fp.is_file():
            continue
        fact = read_json(fp)
        if not fact.get("publikovat"):
            continue
        v = (fact.get("verdikt") or "").strip()
        if v in _PROSLO_VERDIKTY:
            proslo += 1
        elif v in _ZAMITNUTO_VERDIKTY:
            zamitnuto += 1
    return proslo, zamitnuto


def _den_zakon_stats(day_votes: list[dict]) -> tuple[int, int, int]:
    """Počty pro tabuli stavu zápasu: jen zákony, jedno skóre na téma."""
    groups: dict[tuple[str, str], list] = defaultdict(list)
    for v in day_votes:
        if v.get("je_porad_schuze"):
            continue
        nazev = (v.get("nazev") or "").strip()
        if not nazev or vote_kategorie(nazev) != "substantivni":
            continue
        groups[(v.get("bod") or "", nazev)].append(v)
    proslo = zamitnuto = 0
    for group in groups.values():
        if topic_proslo_from_votes(group):
            proslo += 1
        else:
            zamitnuto += 1
    return proslo, zamitnuto, proslo + zamitnuto


def _validate_fact_votes(fact: dict[str, Any], votes_by_cislo: dict[int, dict], schuze: int) -> list[str]:
    """Kontrola citací hlasování a steno_id před zápisem."""
    import re

    warnings: list[str] = []
    prefix = f"2025_{schuze}_"
    for f in fact.get("fakty") or []:
        sid = (f.get("steno_id") or "").strip()
        if sid and f.get("source") == "steno" and sid.startswith("2025_") and not sid.startswith(prefix):
            warnings.append(f"steno_id {sid} není ze schůze s{schuze}")
        cit = f.get("citace") or ""
        for m in re.finditer(
            r"č[ií]slo\s+(\d+)[^0-9]{0,80}?pro\s+(\d+)(?:\s*,?\s*proti\s+(\d+))?",
            cit,
            re.I | re.S,
        ):
            c, pro, proti = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
            rv = votes_by_cislo.get(c)
            if rv and (int(rv.get("pro") or 0) != pro or int(rv.get("proti") or 0) != proti):
                warnings.append(
                    f"#{c} citace {pro}:{proti} vs raw {rv.get('pro')}:{rv.get('proti')}"
                )
    return warnings


_MANUAL_TOPIC_KEYS = (
    "lead",
    "pointa",
    "mean",
    "kuriozita",
    "kuriozita_links",
    "nadpis",
    "publikovat",
    "koho",
    "fakty",
)
_MANUAL_DAY_KEYS = ("dnesni_ucet", "zaver", "vysledek", "topic_slugs")


def _topic_manually_edited(existing: dict[str, Any]) -> bool:
    if any(existing.get(k) for k in ("lead", "pointa", "mean")):
        return True
    if existing.get("fakty") and any(
        f.get("source") in ("votes", "manual") for f in existing.get("fakty") or []
    ):
        return True
    nadpis = (existing.get("nadpis") or "").strip()
    if nadpis and nadpis not in ("Prošlo to", "Prošlo"):
        return True
    return False


def _merge_manual_fact(existing: dict[str, Any], fresh: dict[str, Any]) -> dict[str, Any]:
    if not existing:
        return fresh
    if not _topic_manually_edited(existing):
        return fresh
    out = dict(fresh)
    for key in _MANUAL_TOPIC_KEYS:
        if key in existing and existing[key] not in (None, "", []):
            out[key] = existing[key]
    return out


def _merge_manual_day(existing: dict[str, Any], fresh: dict[str, Any]) -> dict[str, Any]:
    if not existing:
        return fresh
    if not any(existing.get(k) for k in ("dnesni_ucet", "zaver", "vysledek")):
        return fresh
    out = dict(fresh)
    for key in _MANUAL_DAY_KEYS:
        if key in existing and existing[key] not in (None, "", []):
            out[key] = existing[key]
    return out


def run_extract(paths: SchuzePaths) -> dict[str, Any]:
    paths.ensure_dirs()
    aligned = read_json(paths.topics_json)
    topics: list[dict] = aligned.get("topics", [])

    steno_by_id: dict[str, dict] = {}
    steno_all: list[dict] = []
    for s in iter_jsonl(paths.steno_jsonl):
        steno_by_id[s["id"]] = s
        steno_all.append(s)

    from svejk.build.steno_text import detekuj_predsedajici, fakty_z_steno_record

    predsed_jmena = detekuj_predsedajici(steno_all)
    votes_by_cislo: dict[int, dict] = {}
    for v in iter_jsonl(paths.votes_jsonl):
        c = v.get("cislo")
        if c is not None:
            votes_by_cislo[int(c)] = v

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

        topic_votes = [
            votes_by_cislo[int(c)]
            for c in (topic.get("vote_cisla") or [])
            if int(c) in votes_by_cislo
        ]
        signaly = _vote_signaly(topic_votes)

        steno_parts: list[dict] = []
        steno_slov = 0
        for sid in topic.get("steno_ids") or []:
            rec = steno_by_id.get(sid)
            if rec:
                steno_slov += int(rec.get("pocet_slov") or 0)
                steno_parts.extend(
                    fakty_z_steno_record(rec, predsed_jmena=predsed_jmena, limit=3)
                )
        # steno má přednost před obecnou glosou
        fakty = steno_parts + [f for f in fakty if f.get("source") != "steno"]

        seen_f: set[str] = set()
        uniq_f: list[dict] = []
        for f in fakty:
            key = (f.get("text") or "")[:60].lower()
            if key and key not in seen_f:
                seen_f.add(key)
                uniq_f.append(f)
        fakty = uniq_f[:4]

        priorita = _priorita(koho, fakty, signaly=signaly)
        publikovat = priorita > 0 and not (
            gloss and _glosa_je_nedostatecna(gloss) and not koho
        )

        fact_path = paths.facts_by_topic / f"{topic['slug']}.json"
        existing_fact = read_json(fact_path) if fact_path.is_file() else {}
        fact = _merge_manual_fact(
            existing_fact,
            {
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
                "signaly": signaly,
                "steno_slov": steno_slov,
            },
        )
        write_json(fact_path, fact)
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
        vote_proslo, vote_zamitnuto, pocet_hlas = _den_zakon_stats(day_votes)
        times = [v.get("cas", "") for v in day_votes if v.get("cas")]
        start = times[0][:5] if times else ""
        end = _steno_konec_schuze(paths.steno_jsonl) or (times[-1][:5] if times else "")
        minuty = 0
        if start and end:
            sh, sm = int(start[:2]), int(start[3:5])
            eh, em = int(end[:2]), int(end[3:5])
            minuty = max(0, (eh * 60 + em) - (sh * 60 + sm))

        slugs = by_day_topics.get(datum, [])
        proslo, zamitnuto = skore_z_verdiktu(slugs, paths)
        if not proslo and not zamitnuto:
            proslo, zamitnuto = vote_proslo, vote_zamitnuto
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
        day_path = paths.facts_by_day / f"{d.strftime('%Y-%m-%d')}.json"
        existing_day = read_json(day_path) if day_path.is_file() else {}
        day_doc = _merge_manual_day(
            existing_day,
            {
                "datum": datum,
                "den": ["pondělí", "úterý", "středa", "čtvrtek", "pátek", "sobota", "neděle"][d.weekday()],
                "topic_slugs": [x["slug"] for x in slug_meta],
                "stats": {
                    "pocet_hlas": pocet_hlas,
                    "minuty": minuty,
                    "end_cas": end,
                    "proslo": proslo,
                    "zamitnuto": zamitnuto,
                    "dlouha_debata": any(
                        read_json(paths.facts_by_topic / f"{slug}.json").get("steno_slov", 0) >= 1500
                        for slug in slugs
                        if (paths.facts_by_topic / f"{slug}.json").is_file()
                    ),
                },
            },
        )
        write_json(day_path, day_doc)

    validation: list[str] = []
    for fp in paths.facts_by_topic.glob("*.json"):
        if fp.name == "_example.json":
            continue
        fact = read_json(fp)
        if not fact.get("publikovat"):
            continue
        for w in _validate_fact_votes(fact, votes_by_cislo, paths.schuze):
            validation.append(f"{fact.get('slug')}: {w}")

    return {
        "topics_written": written,
        "with_concrete_facts": with_facts,
        "days": len(days),
        "validation_warnings": validation,
    }
