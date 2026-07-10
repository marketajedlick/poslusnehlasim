#!/usr/bin/env python3
"""Oprava steno_id, citací a link_phrase ve facts pro publikovaná vydání s24."""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FACTS_DAY = ROOT / "processed/2025-s24/facts/by_day"
FACTS_TOPIC = ROOT / "processed/2025-s24/facts/by_topic"
STENO_PATH = ROOT / "processed/2025-s24/raw/steno.jsonl"

PUBLISHED_DAYS = [
    "2026-06-23",
    "2026-06-24",
    "2026-06-25",
    "2026-06-26",
    "2026-06-30",
    "2026-07-01",
    "2026-07-02",
    "2026-07-03",
]

def norm(s: str) -> str:
    s = (s or "").strip()
    for old, new in (
        ("„", '"'),
        (""", '"'),
        (""", '"'),
        ("«", '"'),
        ("»", '"'),
        ("'", "'"),
        ("'", "'"),
    ):
        s = s.replace(old, new)
    return re.sub(r"\s+", " ", s).lower()


def citace_in_text(cit: str, text: str) -> bool:
    if not cit or not text:
        return False
    ccit = norm(cit).strip('"').strip("'")
    ntext = norm(text)
    if ccit in ntext:
        return True
    if "…" in cit or "..." in cit:
        parts = re.split(r"…|\.\.\.", cit)
        parts = [norm(p).strip('"').strip("'") for p in parts if len(p.strip()) > 8]
        if parts and all(p in ntext for p in parts):
            return True
    for n in (80, 60, 40, 24):
        chunk = ccit[:n].strip()
        if len(chunk) >= 16 and chunk in ntext:
            return True
    return False


def iso_from_cz(datum: str) -> str:
    return datetime.strptime(datum.strip(), "%d.%m.%Y").strftime("%Y-%m-%d")


def date_prefixes(datum_cz: str) -> list[str]:
    d = datetime.strptime(datum_cz.strip(), "%d.%m.%Y")
    out = []
    for delta in (-1, 0, 1):
        out.append((d + timedelta(days=delta)).strftime("%Y-%m-%d"))
    return out


def load_steno() -> tuple[list[dict], dict[str, dict]]:
    rows: list[dict] = []
    by_id: dict[str, dict] = {}
    for line in STENO_PATH.open(encoding="utf-8"):
        r = json.loads(line)
        rows.append(r)
        by_id[r["id"]] = r
    return rows, by_id


def find_steno_ids(
    steno_rows: list[dict],
    cit: str,
    prefixes: list[str] | None,
    *,
    all_days: bool = False,
) -> list[str]:
    hits: list[str] = []
    for r in steno_rows:
        if not all_days and prefixes:
            if not any((r.get("datum") or "").startswith(p) for p in prefixes):
                continue
        if citace_in_text(cit, r.get("text", "")):
            hits.append(r["id"])
    return hits


def sanitize_dashes(s: str) -> str:
    return (s or "").replace("—", ", ").replace("–", ", ")


def excerpt_from_steno(cit: str, text: str, max_words: int = 15) -> str:
    """Vrátí doslovný úryvek ze stena (max ~15 slov)."""
    if citace_in_text(cit, text):
        flat = re.sub(r"\s+", " ", cit.strip())
        if len(flat.split()) <= max_words:
            return sanitize_dashes(flat)
    ntext = text or ""
    needle = norm(cit).strip('"').strip("'")
    for n in (80, 60, 40, 24, 16):
        chunk = needle[:n].strip()
        if len(chunk) < 12:
            continue
        idx = norm(ntext).find(chunk)
        if idx < 0:
            continue
        words = ntext.split()
        acc = ""
        for w in words:
            acc = (acc + " " + w).strip()
            if norm(acc).find(chunk[: min(len(chunk), 24)]) >= 0:
                start_words = acc.split()
                break
        else:
            continue
        start = ntext.find(start_words[0]) if start_words else 0
        tail = ntext[start:]
        out_words = tail.split()[:max_words]
        return sanitize_dashes(" ".join(out_words))
    return sanitize_dashes(cit.strip())


def strip_steno_fields(f: dict) -> None:
    f.pop("steno_id", None)
    f.pop("link_phrase", None)
    if f.get("source") == "steno":
        f.pop("source", None)


def article_text_from_topic(data: dict) -> str:
    parts: list[str] = []
    for key in ("lead", "pointa", "mean", "kuriozita", "citace_text"):
        v = (data.get(key) or "").strip()
        if v:
            parts.append(v)
    return " ".join(parts)


def refresh_link_phrase(data: dict, steno_by_id: dict[str, dict]) -> None:
    from svejk.build.steno_sources import StenoPassage, link_phrase_for_passage

    article = article_text_from_topic(data)
    if not article:
        return
    for f in data.get("fakty") or []:
        if not isinstance(f, dict):
            continue
        sid = (f.get("steno_id") or "").strip()
        cit = (f.get("citace") or "").strip()
        if not sid or not cit:
            continue
        rec = steno_by_id.get(sid) or {}
        passage = StenoPassage(
            steno_id=sid,
            anchor=f"steno-{sid}",
            speaker=rec.get("cele_jmeno") or "",
            poradi=rec.get("poradi"),
            topic_slug=data.get("slug") or "",
            topic_title=(data.get("nadpis") or "").strip(),
            article_num=1,
            summary=(f.get("text") or "").strip(),
            citace=cit,
            excerpt=cit,
            psp_url="",
            source="steno",
            nav_label="",
            link_phrase="",
        )
        phrase = link_phrase_for_passage(passage, article)
        if phrase:
            f["link_phrase"] = phrase
        else:
            f.pop("link_phrase", None)


def fix_fact(f: dict, steno_rows: list[dict], steno_by_id: dict[str, dict], prefixes: list[str]) -> bool:
    """Vrátí True pokud fact má platné steno. Upraví f in-place."""
    cit = (f.get("citace") or "").strip()
    if not cit:
        if f.get("source") == "steno":
            strip_steno_fields(f)
        return False

    all_days = "Hlasování číslo" in cit or "hlasování číslo" in cit
    hits = find_steno_ids(steno_rows, cit, prefixes, all_days=all_days)
    sid = (f.get("steno_id") or "").strip()
    if sid and sid in hits and citace_in_text(cit, steno_by_id[sid].get("text", "")):
        f["steno_id"] = sid
        f["source"] = "steno"
        f["citace"] = excerpt_from_steno(cit, steno_by_id[sid].get("text", ""))
        return True
    if hits:
        sid = hits[0]
        f["steno_id"] = sid
        f["source"] = "steno"
        f["citace"] = excerpt_from_steno(cit, steno_by_id[sid].get("text", ""))
        return True
    strip_steno_fields(f)
    return False


def fix_topic_auto(data: dict, steno_rows: list[dict], steno_by_id: dict[str, dict]) -> int:
    datum = data.get("datum") or ""
    if not datum:
        return 0
    prefixes = date_prefixes(datum)
    fixed = 0
    for f in data.get("fakty") or []:
        if not isinstance(f, dict):
            continue
        if fix_fact(f, steno_rows, steno_by_id, prefixes):
            fixed += 1
    refresh_link_phrase(data, steno_by_id)
    ct = (data.get("citace_text") or "").strip()
    ctsid = (data.get("steno_id") or "").strip()
    if ct and ctsid:
        rec = steno_by_id.get(ctsid)
        if not rec or not citace_in_text(ct, rec.get("text", "")):
            hits = find_steno_ids(steno_rows, ct, prefixes, all_days=False)
            if hits:
                data["steno_id"] = hits[0]
            else:
                data.pop("steno_id", None)
    return fixed


# --- ruční opravy tam, kde auto nestačí ---


def patch_zpravy_budoucnosti(data: dict) -> None:
    mapping = {
        "2025_24_00007": "2025_24_00006",
        "2025_24_00037": "2025_24_00036",
        "2025_24_00009": "2025_24_00008",
        "2025_24_00011": "2025_24_00010",
        "2025_24_00033": "2025_24_00032",
    }
    for f in data.get("fakty") or []:
        old = f.get("steno_id")
        if old in mapping:
            f["steno_id"] = mapping[old]
    # Bartoš sport: citace není doslovná ve stenu, ponechat bez steno
    drop_phrases = {
        "sestřihy tiskových konferencí pana premiéra Babiše",
        "Děkujeme především našim vládním politikům",
    }
    data["fakty"] = [
        f
        for f in data.get("fakty") or []
        if f.get("link_phrase") not in drop_phrases
    ]


def patch_palacova_pohadka(data: dict, steno_by_id: dict[str, dict]) -> None:
    keep: list[dict] = []
    for f in data.get("fakty") or []:
        lp = f.get("link_phrase") or ""
        if lp in {
            "42 korun za metr čtvereční",
            "premiér Babiš ani o jejích rozhodnutích neví",
            "destrukci veřejnopránních médií",
        } or "panovník Andreje Babiše" in (f.get("citace") or ""):
            continue
        keep.append(f)
    for f in keep:
        if "panovník ve velkém paláci" in (f.get("link_phrase") or ""):
            f["steno_id"] = "2025_24_00016"
            f["citace"] = (
                "Byl jeden takový panovník, který žil ve velkém paláci, ale obyčejní lidé se do tohohle paláce nikdy nedostanou."
            )
        if "levný byt na zámeckém panství" in (f.get("link_phrase") or ""):
            f["steno_id"] = "2025_24_00016"
            f["citace"] = "Jeden dvořan měl třeba levný byt na zámeckém panství."
        if "palácová vláda nesnáší" in (f.get("link_phrase") or ""):
            f["steno_id"] = "2025_24_00018"
            f["citace"] = "co nemá ráda ta palácová vláda, o které tady mluvím?"
    data["fakty"] = keep
    data["citace_text"] = (
        "Byl jeden takový panovník, který žil ve velkém paláci, ale obyčejní lidé se do tohohle paláce nikdy nedostanou. "
        "On měl kolem sebe dvořany, kteří byli věrní a za tu věrnost byli pravidelně a hodně a dobře odměňováni."
    )


def patch_debata_rakusan(data: dict) -> None:
    data["fakty"] = [
        {
            "text": "Rakušan: mise u OSN bez podpisu prezidenta.",
            "source": "steno",
            "steno_id": "2025_24_01221",
            "citace": "Jako mise u OSN v New Yorku, to je myslím docela hezká pozice v diplomatické službě. Tak od teď už bez podpisu prezidenta.",
            "link_phrase": "bez podpisu prezidenta",
        },
        {
            "text": "Rakušan: msta, která se bojí denního světla.",
            "source": "steno",
            "steno_id": "2025_24_01221",
            "citace": "Tohle je msta, která se bojí denního světla, to, co tady předvádíte.",
            "link_phrase": "msta, která se bojí denního světla",
        },
        {
            "text": "Rakušan: diplomatické mise jako trafika.",
            "source": "steno",
            "steno_id": "2025_24_01221",
            "citace": "Diplomatické mise u těch mezinárodních organizací, to je myslím si, hezká trafička.",
            "link_phrase": "mise u OSN v New Yorku",
        },
    ]
    data["lead"] = (
        "Rakušan (STAN) řešil zákon o zahraniční službě a roli prezidenta. "
        "Pozměňovací návrh A7 mění pravidla pro mise u mezinárodních organizací tak, "
        "aby nepotřebovaly podpis prezidenta. Rakušan (STAN) to nazval pomstou."
    )
    data["citace_text"] = "Tohle je msta, která se bojí denního světla, to, co tady předvádíte."


def patch_novela_zvirata(data: dict) -> None:
    data["fakty"] = [
        {
            "text": "Hladík: máme kočku jménem Vločka.",
            "source": "steno",
            "steno_id": "2025_24_01149",
            "citace": "Já sám, moje rodina chová kočku, konkrétně má jméno Vločka, a jsem ze zemědělské, ze sedlácké rodiny.",
            "link_phrase": "domácí kočku Vločku",
        },
        {
            "text": "Hladík: návrh je nevalně zpracovaný.",
            "source": "steno",
            "steno_id": "2025_24_01149",
            "citace": "který si dovolím označit za nevalně zpracovaný",
            "link_phrase": "nevalně zpracovaný",
        },
        {
            "text": "Hanzlíková: dolní sazby ze šesti měsíců na rok.",
            "source": "steno",
            "steno_id": "2025_24_01039",
            "citace": "dosavadní trestní sazba je šest měsíců až čtyři léta, navrhovaná trestní sazba jeden rok až čtyři léta",
            "link_phrase": "ze šesti měsíců na rok",
        },
        {
            "text": "Hanzlíková: nová skutková podstata usmrcení psa nebo kočky.",
            "source": "steno",
            "steno_id": "2025_24_01039",
            "citace": "usmrcení psa nebo kočky ze zavrženíhodného důvodu i v případech, kdy usmrcení není prováděno surovým nebo trýznivým způsobem",
            "link_phrase": "ze zavrženíhodné pohnutky",
        },
        {
            "text": "Hanzlíková: jinak jde zpravidla jen o přestupek.",
            "source": "steno",
            "steno_id": "2025_24_01039",
            "citace": "zpravidla se jedná pouze o přestupek",
            "link_phrase": "trestný čin nebo přestupek",
        },
    ]
    data["lead"] = (
        "Ve středu hlasovala Sněmovna o novele trestního zákona na ochranu zvířat:\n\n"
        "<ul class=\"listy-ul\">\n"
        "<li>vyšší minimální tresty za týrání zvířat, typicky ze šesti měsíců na rok</li>\n"
        "<li>nový trestný čin za usmrcení psa nebo kočky ze zavrženíhodné pohnutky</li>\n"
        "<li>debata, jestli jde o trestný čin nebo přestupek, a proč jen kočky a psi</li>\n"
        "</ul>\n\n"
        "Ministr Hladík (KDU-ČSL) před hlasováním připomněl domácí kočku Vločku, "
        "pak ale stejný návrh označil za nevalně zpracovaný."
    )


PATCHERS: dict[str, object] = {
    "zpravy-z-budoucnosti-23-06": patch_zpravy_budoucnosti,
    "palacova-pohadka-23-06": patch_palacova_pohadka,
    "debata-rakusan-nato-zahranicni-sluzba-01-07": patch_debata_rakusan,
    "novela-z-na-ochranu-zvirat-proti-tyrani": patch_novela_zvirata,
}


def published_slugs() -> set[str]:
    slugs: set[str] = set()
    for day in PUBLISHED_DAYS:
        data = json.loads((FACTS_DAY / f"{day}.json").read_text(encoding="utf-8"))
        for s in data.get("topic_slugs") or []:
            slugs.add(s)
    return slugs


def main() -> int:
    sys.path.insert(0, str(ROOT))
    steno_rows, steno_by_id = load_steno()
    slugs = published_slugs()
    changed = 0

    for slug in sorted(slugs):
        path = FACTS_TOPIC / f"{slug}.json"
        if not path.is_file():
            print(f"SKIP missing {slug}")
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("publikovat") is False:
            continue
        fix_topic_auto(data, steno_rows, steno_by_id)
        patcher = PATCHERS.get(slug)
        if patcher:
            if slug == "palacova-pohadka-23-06":
                patcher(data, steno_by_id)  # type: ignore[operator]
            else:
                patcher(data)  # type: ignore[operator]
            refresh_link_phrase(data, steno_by_id)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        changed += 1
        print(f"fixed {slug}")

    fix_0702 = ROOT / "scripts/fix_steno_2026_07_02.py"
    if fix_0702.is_file():
        import importlib.util

        spec = importlib.util.spec_from_file_location("fix_0702", fix_0702)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.main()
        print("applied fix_steno_2026_07_02")

    print(f"Done: {changed} topic files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
