"""Generování brief.md/json pro Cursor agenta."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from svejk.build.align import run_align
from svejk.build.extract import (
    _den_zakon_stats,
    _fakty_z_glosy,
    _koho_z_glosy,
    _nadpis_fallback,
    _priorita,
    _verdikt,
    _vote_signaly,
    skore_z_verdiktu,
)
from svejk.build.io import iter_jsonl, read_json, write_json
from svejk.build.steno_text import detekuj_predsedajici, fakty_z_steno_record
from svejk.build.vote_logic import spor_o_porad_schuze
from svejk.edition.dates import resolve_edition_day
from svejk.edition.state import (
    assert_editable,
    compute_input_fingerprint,
    edition_dir,
    load_edition,
    merge_day_skeleton,
    merge_topic_skeleton,
    save_edition,
    steno_incomplete,
)
from svejk.jednaci_den import (
    calendar_isos_for_jednaci_den,
    jednaci_den_minuty,
    vote_belongs_to_jednaci_den,
    vote_chrono_key,
)
from svejk.listy import _glosa_je_nedostatecna
from svejk.obcansky import glosa_pro_obcana
from svejk.paths import SchuzePaths


def _topics_need_align(paths: SchuzePaths) -> bool:
    if not paths.topics_json.is_file():
        return True
    if not paths.votes_jsonl.is_file():
        return False
    return paths.votes_jsonl.stat().st_mtime > paths.topics_json.stat().st_mtime


def _steno_slov(topic: dict, steno_by_id: dict[str, dict]) -> int:
    total = 0
    for sid in topic.get("steno_ids") or []:
        rec = steno_by_id.get(sid)
        if rec:
            total += int(rec.get("pocet_slov") or 0)
    return total


def _score_topic(
    topic: dict,
    *,
    topic_votes: list[dict],
    steno_by_id: dict[str, dict],
    predsed_jmena: set[str],
) -> tuple[int, dict[str, Any], list[dict]]:
    nazev = topic["nazev"]
    proslo = topic.get("proslo", False)
    vysv = topic.get("tema_vysvetleni") or ""
    gloss = glosa_pro_obcana(nazev, vysv, proslo=proslo)
    koho = _koho_z_glosy(gloss) if gloss and not _glosa_je_nedostatecna(gloss) else []
    fakty = _fakty_z_glosy(gloss) if gloss else []
    signaly = _vote_signaly(topic_votes)
    steno_parts: list[dict] = []
    for sid in topic.get("steno_ids") or []:
        rec = steno_by_id.get(sid)
        if rec:
            steno_parts.extend(
                fakty_z_steno_record(rec, predsed_jmena=predsed_jmena, limit=3)
            )
    fakty = steno_parts + [f for f in fakty if f.get("source") != "steno"]
    seen: set[str] = set()
    uniq: list[dict] = []
    for f in fakty:
        key = (f.get("text") or "")[:60].lower()
        if key and key not in seen:
            seen.add(key)
            uniq.append(f)
    fakty = uniq[:4]
    priorita = _priorita(koho, fakty, signaly=signaly)
    steno_slov = _steno_slov(topic, steno_by_id)
    score = priorita * 10
    if signaly.get("spor"):
        score += 15
    if signaly.get("prazdny_sal"):
        score += 5
    if any(f.get("kind") == "scene" for f in fakty):
        score += 8
    if steno_slov >= 1500:
        score += 6
    if steno_slov >= 800:
        score += 3
    if topic.get("kategorie") == "substantivni":
        score += 2
    meta = {
        "priorita": priorita,
        "signaly": signaly,
        "steno_slov": steno_slov,
        "pocet_fakty": len(fakty),
        "proslo": proslo,
        "kategorie": topic.get("kategorie"),
    }
    return score, meta, fakty


def _reject_reason(score: int, meta: dict[str, Any]) -> str:
    if score < 5:
        return "nízká priorita, málo materiálu"
    if meta.get("signaly", {}).get("jednomyslne") and meta.get("steno_slov", 0) < 400:
        return "jednomyslné hlasování, krátká debata"
    if meta.get("kategorie") not in ("substantivni",) and meta.get("steno_slov", 0) < 600:
        return "procedura / slabý steno signál"
    return "mimo top 3 pro den"


def _topics_for_day(
    topics: list[dict],
    datum_unl: str,
    votes_by_cislo: dict[int, dict],
    steno_by_id: dict[str, dict],
    predsed_jmena: set[str],
    *,
    max_articles: int = 3,
) -> tuple[list[dict], list[dict]]:
    ranked: list[tuple[int, dict, dict, list[dict]]] = []
    for topic in topics:
        if (topic.get("datum") or "") != datum_unl:
            continue
        nazev = (topic.get("nazev") or "").strip()
        if not nazev:
            continue
        topic_votes = [
            votes_by_cislo[int(c)]
            for c in (topic.get("vote_cisla") or [])
            if int(c) in votes_by_cislo
        ]
        score, meta, fakty = _score_topic(
            topic,
            topic_votes=topic_votes,
            steno_by_id=steno_by_id,
            predsed_jmena=predsed_jmena,
        )
        if score < 3 and not fakty:
            continue
        ranked.append((score, topic, meta, fakty))
    ranked.sort(key=lambda x: (-x[0], x[1].get("slug", "")))
    recommended = []
    rejected = []
    for i, (score, topic, meta, fakty) in enumerate(ranked):
        entry = {
            "slug": topic["slug"],
            "nazev": topic["nazev"],
            "score": score,
            "meta": meta,
            "fakty": fakty,
            "topic": topic,
        }
        if len(recommended) < max_articles and score >= 5:
            recommended.append(entry)
        else:
            entry["reason"] = _reject_reason(score, meta)
            rejected.append(entry)
    return recommended, rejected


def _write_topic_skeleton(
    paths: SchuzePaths,
    entry: dict[str, Any],
    votes_by_cislo: dict[int, dict],
) -> None:
    topic = entry["topic"]
    fakty = entry["fakty"]
    meta = entry["meta"]
    nazev = topic["nazev"]
    proslo = topic.get("proslo", False)
    vysv = topic.get("tema_vysvetleni") or ""
    gloss = glosa_pro_obcana(nazev, vysv, proslo=proslo)
    koho = _koho_z_glosy(gloss) if gloss and not _glosa_je_nedostatecna(gloss) else []
    topic_votes = [
        votes_by_cislo[int(c)]
        for c in (topic.get("vote_cisla") or [])
        if int(c) in votes_by_cislo
    ]
    signaly = meta.get("signaly") or _vote_signaly(topic_votes)
    fact_path = paths.facts_by_topic / f"{topic['slug']}.json"
    existing = read_json(fact_path) if fact_path.is_file() else {}
    fresh = {
        "slug": topic["slug"],
        "nazev": nazev,
        "datum": topic.get("datum", ""),
        "verdikt": _verdikt(proslo, nazev, vysv),
        "predmet_lidsky": topic.get("tema_svejk") or "",
        "koho": koho,
        "fakty": fakty,
        "publikovat": True,
        "priorita": meta.get("priorita", 2),
        "nadpis": _nadpis_fallback(nazev, proslo),
        "pocet_hlasovani": topic.get("pocet_hlasovani", 0),
        "proslo": proslo,
        "signaly": signaly,
        "steno_slov": meta.get("steno_slov", 0),
    }
    write_json(fact_path, merge_topic_skeleton(existing, fresh))


def _write_day_skeleton(
    paths: SchuzePaths,
    datum_unl: str,
    iso: str,
    slugs: list[str],
) -> None:
    votes = list(iter_jsonl(paths.votes_jsonl))
    day_votes = [v for v in votes if vote_belongs_to_jednaci_den(v, datum_unl)]
    vote_proslo, vote_zamitnuto, pocet_hlas = _den_zakon_stats(day_votes)
    spor_o_porad = spor_o_porad_schuze(day_votes)
    ordered = sorted(day_votes, key=vote_chrono_key)
    end = (ordered[-1].get("cas") or "")[:5] if ordered else ""
    minuty = jednaci_den_minuty(day_votes)
    proslo, zamitnuto = skore_z_verdiktu(slugs, paths)
    if not proslo and not zamitnuto:
        proslo, zamitnuto = vote_proslo, vote_zamitnuto
    d = datetime.strptime(datum_unl, "%d.%m.%Y")
    day_path = paths.facts_by_day / f"{iso}.json"
    existing = read_json(day_path) if day_path.is_file() else {}
    fresh = {
        "datum": datum_unl,
        "den": ["pondělí", "úterý", "středa", "čtvrtek", "pátek", "sobota", "neděle"][
            d.weekday()
        ],
        "topic_slugs": slugs,
        "stats": {
            "pocet_hlas": pocet_hlas,
            "minuty": minuty,
            "end_cas": end,
            "proslo": proslo,
            "zamitnuto": zamitnuto,
            "spor_o_porad": spor_o_porad,
            "dlouha_debata": any(
                read_json(paths.facts_by_topic / f"{s}.json").get("steno_slov", 0) >= 1500
                for s in slugs
                if (paths.facts_by_topic / f"{s}.json").is_file()
            ),
        },
        "steno_zdroje": True,
    }
    write_json(day_path, merge_day_skeleton(existing, fresh))


def _feedback_section(doc: dict[str, Any], limit: int = 8) -> str:
    lines = []
    for item in (doc.get("feedback") or [])[-limit:]:
        note = (item.get("note") or "").strip()
        field = (item.get("field") or "").strip()
        if note:
            prefix = f"[{field}] " if field else ""
            lines.append(f"- {prefix}{note}")
    if not lines:
        return ""
    return "## Co neopakovat (feedback)\n\n" + "\n".join(lines) + "\n\n"


def _render_brief_md(
    *,
    datum_unl: str,
    iso: str,
    recommended: list[dict],
    rejected: list[dict],
    day_stats: dict[str, Any],
    doc: dict[str, Any],
) -> str:
    parts = [
        f"# Brief vydání {datum_unl}",
        "",
        f"ISO: `{iso}` · Schůze: `{doc.get('obdobi')}-s{doc.get('schuze')}`",
        "",
        "Cursor: přečti `.cursor/prompts/edition-draft.md` a doplň `facts/`.",
        "",
        _feedback_section(doc),
        "## Doporučená témata (max 3 články)",
        "",
    ]
    for i, entry in enumerate(recommended, 1):
        m = entry["meta"]
        sig = m.get("signaly") or {}
        parts.append(
            f"### {i}. `{entry['slug']}` — {entry['nazev']}\n"
            f"- skóre: {entry['score']}, steno_slov: {m.get('steno_slov')}, "
            f"proti_max: {sig.get('proti_max')}, proslo: {m.get('proslo')}\n"
        )
        for j, f in enumerate(entry["fakty"][:3], 1):
            cit = (f.get("citace") or f.get("text") or "")[:120]
            sid = f.get("steno_id") or ""
            parts.append(f"  {j}. [{sid}] {cit}")
        parts.append("")
    if rejected:
        parts.append("## Zvažovaná, ale vyřazená")
        parts.append("")
        for entry in rejected[:12]:
            parts.append(
                f"- `{entry['slug']}` — {entry.get('reason', '?')} "
                f"(skóre {entry['score']})"
            )
        parts.append("")
    parts.extend(
        [
            "## Stats dne",
            "",
            f"```json\n{json.dumps(day_stats, ensure_ascii=False, indent=2)}\n```",
            "",
            "## Úkoly pro agenta",
            "",
            "1. `facts/by_topic/<slug>.json`: nadpis, lead, pointa, mean, citace_text, publikovat",
            "2. `facts/by_day/`: dnesni_ucet (2 řádky), zaver (že …), topic_slugs, steno_zdroje",
            "3. `./run-svejk.sh edition link-phrases --schuze N --den D`",
            "4. `./run-svejk.sh edition preview --schuze N --den D`",
            "",
        ]
    )
    return "\n".join(parts)


def run_edition_brief(
    paths: SchuzePaths,
    den: str,
    *,
    allow_incomplete_steno: bool = False,
    force: bool = False,
    max_articles: int = 3,
) -> dict[str, Any]:
    paths.ensure_dirs()
    datum_unl, iso, _ = resolve_edition_day(paths, den)
    doc = load_edition(paths, iso)
    assert_editable(doc, force=force, action="generovat brief")

    if steno_incomplete(paths) and not allow_incomplete_steno:
        raise RuntimeError(
            "Steno download neúplný — dokonči sync/fetch, nebo --allow-incomplete-steno"
        )

    if _topics_need_align(paths):
        run_align(paths)

    aligned = read_json(paths.topics_json)
    topics: list[dict] = aligned.get("topics") or []
    votes_by_cislo: dict[int, dict] = {}
    for v in iter_jsonl(paths.votes_jsonl):
        c = v.get("cislo")
        if c is not None:
            votes_by_cislo[int(c)] = v

    steno_by_id: dict[str, dict] = {}
    steno_all: list[dict] = []
    for s in iter_jsonl(paths.steno_jsonl):
        steno_by_id[s["id"]] = s
        steno_all.append(s)
    predsed_jmena = detekuj_predsedajici(steno_all)

    recommended, rejected = _topics_for_day(
        topics,
        datum_unl,
        votes_by_cislo,
        steno_by_id,
        predsed_jmena,
        max_articles=max_articles,
    )
    slugs = [e["slug"] for e in recommended]
    for entry in recommended:
        _write_topic_skeleton(paths, entry, votes_by_cislo)
    if slugs:
        _write_day_skeleton(paths, datum_unl, iso, slugs)

    votes = list(iter_jsonl(paths.votes_jsonl))
    day_votes = [v for v in votes if vote_belongs_to_jednaci_den(v, datum_unl)]
    vote_proslo, vote_zamitnuto, pocet_hlas = _den_zakon_stats(day_votes)
    day_stats = {
        "pocet_hlas_zakon": pocet_hlas,
        "proslo_vote": vote_proslo,
        "zamitnuto_vote": vote_zamitnuto,
        "spor_o_porad": spor_o_porad_schuze(day_votes),
        "calendar_isos": sorted(calendar_isos_for_jednaci_den(datum_unl)),
    }

    edir = edition_dir(paths, iso)
    edir.mkdir(parents=True, exist_ok=True)
    brief_json = {
        "datum_unl": datum_unl,
        "iso": iso,
        "recommended": [
            {
                "slug": e["slug"],
                "nazev": e["nazev"],
                "score": e["score"],
                "meta": e["meta"],
                "fakty": e["fakty"],
            }
            for e in recommended
        ],
        "rejected": [
            {"slug": e["slug"], "score": e["score"], "reason": e.get("reason")}
            for e in rejected
        ],
        "day_stats": day_stats,
    }
    (edir / "brief.json").write_text(
        json.dumps(brief_json, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (edir / "brief.md").write_text(
        _render_brief_md(
            datum_unl=datum_unl,
            iso=iso,
            recommended=recommended,
            rejected=rejected,
            day_stats=day_stats,
            doc=doc,
        ),
        encoding="utf-8",
    )

    doc["state"] = "draft"
    doc["topic_slugs"] = slugs
    doc["recommended_slugs"] = slugs
    doc["rejected_slugs"] = [e["slug"] for e in rejected]
    doc["inputs"] = compute_input_fingerprint(paths)
    save_edition(paths, iso, doc)

    return {
        "datum_unl": datum_unl,
        "iso": iso,
        "state": doc["state"],
        "recommended": slugs,
        "rejected_count": len(rejected),
        "brief_md": str(edir / "brief.md"),
        "brief_json": str(edir / "brief.json"),
    }
