#!/usr/bin/env python3
"""Srovná link_phrase s textem článku (orphan_link_phrase)."""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from svejk.build.steno_sources import _find_phrase_in_text  # noqa: E402
from svejk.paths import SchuzePaths  # noqa: E402

APPROVED = json.loads((ROOT / "processed/publish-approved.json").read_text())["approved"]

# ponytail: ruční mapa jen pro případy, kde auto nenajde shodu
MANUAL: dict[str, dict[str, str]] = {
    "vl-n-z-o-statnim-rozpoctu-cr-na-rok-2026": {
        "90 proti 68": "90 hlasů proti 68",
        "178 proti 1": "sto sedmdesát osm hlasů pro, jeden proti",
        "142 hlasy pro, nikdo proti": "sto čtyřicet dva hlasy pro, nikdo proti",
    },
    "neduvera-vlade-debata": {
        "Hlasování číslo 2, přítomno 123 poslanců, 115 poslanců hlasovalo pro,": "115 proti 6",
    },
    "navrh-na-zmeny-ve-slozeni-organu-poslanecke-snem": {
        "168 hlasy pro, nikdo proti": "Všechno prošlo",
        "Návrh byl přijat.": "33 hlasů proti",  # první výskyt → vote 72
    },
    "novela-z-o-podpore-bydleni": {
        "126 hlasy pro, nikdo proti": "prošla první kolo",
    },
    "novela-z-o-zivotnim-a-existencnim-minimu": {
        "5 proti 85": "pět hlasů proti senátnímu zamítnutí, osmdesát pět proti",
    },
    "novela-z-o-doplnkovem-penzijnim-sporeni": {
        "119 proti 3": "sto devatenáct hlasů pro",
    },
    "novela-z-o-pojistnem-na-socialni-zabezpeceni": {
        "112 proti 9": "sto dvanáct hlasů pro",
    },
    "navrh-na-zrizeni-vysetrovaci-komise-poslanecke-s": {
        "89 proti 15": "osmdesát devět hlasů pro, patnáct proti",
    },
    "novela-z-o-statni-socialni-podpore": {
        "Hlasování číslo 140, sto dvacet dva hlasů pro, zákon schválen": "schválila technickou novelu",
        "Hlasování číslo 68 a 69, sto hlasů pro při závěrečném": "schválila technickou novelu",
    },
    "vl-n-z-kt-se-meni-nektere-z-v-oblasti-verejnych-": {
        "Finální hlasování číslo 44 v 13:10 padlo šedesát osm proti": "devadesát poslanců proti šedesáti osmi",
    },
    "stanovisko-vladni-koalice-ke-sjezdu-sudetonemeck": {
        "Finální hlasování číslo 4 ve 14:24, sedmdesát tři hlasů pro,": "sedmdesát tři hlasy a nikdo proti",
    },
    "vl-n-z-o-evidenci-trzeb-eu": {
        "Návrhy TOP 09 a ODS na zamítnutí či vrácení spadly": "návrhy na zamítnutí spadly",
    },
}


def parse_key(k: str) -> tuple[int, str]:
    sch, cz = k.split("/", 1)[1].split("/", 1)
    iso = datetime.strptime(cz.strip(), "%d.%m.%Y").strftime("%Y-%m-%d")
    return int(sch), iso


def art(data: dict) -> str:
    parts = []
    for key in ("lead", "pointa", "mean", "kuriozita", "citace_text"):
        val = (data.get(key) or "").strip()
        if val:
            parts.append(re.sub(r"<[^>]+>", " ", val))
    return " ".join(parts)


def score_from_article(data: dict, summary: str) -> str | None:
    a = art(data)
    m = re.search(r"pro (\d+), proti (\d+)", summary or "")
    if m:
        pro, proti = m.group(1), m.group(2)
        for cand in (
            f"{pro} hlasů proti {proti}",
            f"{pro} proti {proti}",
            f"{pro}:{proti}",
        ):
            if _find_phrase_in_text(a, cand):
                return cand
    m = re.search(r"pro (\d+), proti nikdo", summary or "", re.I)
    if m:
        pro = m.group(1)
        for cand in (
            f"{pro} hlasy pro, nikdo proti",
            f"{pro} hlasy pro",
            f"pro {pro}, proti nikdo",
        ):
            if _find_phrase_in_text(a, cand):
                return cand
    for n in range(min(12, len((summary or "").split())), 2, -1):
        chunk = " ".join((summary or "").split()[:n])
        if len(chunk) >= 8 and _find_phrase_in_text(a, chunk):
            return chunk
    return None


def fix_topic(slug: str, data: dict) -> list[str]:
    changes: list[str] = []
    manual = MANUAL.get(slug) or {}
    article = art(data)
    seen_návrh = 0
    for i, f in enumerate(data.get("fakty") or []):
        if not isinstance(f, dict):
            continue
        lp = (f.get("link_phrase") or "").strip()
        if not lp or _find_phrase_in_text(article, lp):
            continue
        summary = (f.get("text") or "").strip()
        new: str | None = None
        if lp in manual:
            cand = manual[lp]
            if lp == "Návrh byl přijat." and slug == "navrh-na-zmeny-ve-slozeni-organu-poslanecke-snem":
                cand = "u ochránce dětí 11" if seen_návrh else "33 hlasů proti"
                seen_návrh += 1
            if _find_phrase_in_text(article, cand):
                new = cand
        if not new:
            new = score_from_article(data, summary)
        if new and new != lp:
            f["link_phrase"] = new
            changes.append(f"{slug}[{i}] {lp[:40]!r} -> {new!r}")
    return changes


def main() -> int:
    dry = "--dry-run" in sys.argv
    total = 0
    for key in APPROVED:
        sch, iso = parse_key(key)
        paths = SchuzePaths.create(2025, sch)
        dayp = paths.facts_by_day / f"{iso}.json"
        if not dayp.is_file():
            continue
        day = json.loads(dayp.read_text())
        if not day.get("steno_zdroje"):
            continue
        for slug in day.get("topic_slugs") or []:
            fp = paths.facts_by_topic / f"{slug}.json"
            if not fp.is_file():
                continue
            data = json.loads(fp.read_text())
            if not data.get("publikovat"):
                continue
            ch = fix_topic(slug, data)
            if not ch:
                continue
            total += 1
            for line in ch:
                print(line)
            if not dry:
                fp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"files {total}, dry={dry}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
