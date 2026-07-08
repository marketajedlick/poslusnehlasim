#!/usr/bin/env python3
"""Fix steno_id and citace for 2. 7. 2026 fact files (schůze 24)."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FACTS = ROOT / "processed/2025-s24/facts/by_topic"

ID_MAP: dict[str, dict[str, str]] = {
    "interpelace-mrazova-bydleni-02-07.json": {
        "2025_24_01456": "2025_24_01573",
        "2025_24_01462": "2025_24_01579",
        "2025_24_01473": "2025_24_01590",
        "2025_24_01460": "2025_24_01577",
        "2025_24_01472": "2025_24_01589",
    },
    "interpelace-babis-odpovedi-02-07.json": {
        "2025_24_01589": "2025_24_01704",
        "2025_24_01577": "2025_24_01692",
        "2025_24_01605": "2025_24_01720",
    },
    "interpelace-babis-ipo-letiste-02-07.json": {
        "2025_24_01621": "2025_24_01736",
    },
    "interpelace-kovacik-povodi-02-07.json": {
        "2025_24_01700": "2025_24_01815",
        "2025_24_01702": "2025_24_01817",
        "2025_24_01706": "2025_24_01821",
    },
    "novela-z-o-obalech.json": {
        "2025_24_01478": "2025_24_01600",
        "2025_24_01479": "2025_24_01596",
        "2025_24_01493": "2025_24_01609",
        "2025_24_01515": "2025_24_01631",
        "2025_24_01523": "2025_24_01639",
        "2025_24_01527": "2025_24_01643",
        "2025_24_01525": "2025_24_01643",
        "2025_24_01529": "2025_24_01645",
        "2025_24_01511": "2025_24_01627",
        "2025_24_01538": "2025_24_01654",
    },
    "novela-z-o-podnikani-na-kapitalovem-trhu-eu.json": {
        "2025_24_01540": "2025_24_01655",
        "2025_24_01551": "2025_24_01666",
        "2025_24_01553": "2025_24_01668",
    },
}


def remap_ids(data: dict, mapping: dict[str, str]) -> None:
    for fact in data.get("fakty", []):
        old = fact.get("steno_id")
        if old in mapping:
            fact["steno_id"] = mapping[old]


def fix_mrazova(data: dict) -> None:
    remap_ids(data, ID_MAP["interpelace-mrazova-bydleni-02-07.json"])
    for fact in data["fakty"]:
        if fact.get("link_phrase") == "mluvila dvě tisíce šest set šestnáct slov":
            fact["steno_id"] = "2025_24_01579"
            fact["citace"] = (
                "hovořili o té probíhající krizi bydlení, do které teď bohužel ještě zasahují četné kauzy ministryně pro místní rozvoj"
            )
        if fact.get("link_phrase") == "dvě tisíce osm set osmdesát osm":
            fact["steno_id"] = "2025_24_01590"
            fact["citace"] = (
                "ve věci strategická komunikace státu a důvody jejího zrušení vládou vedenou Andrej Babišem k 1. 1. 2026"
            )
        if fact.get("link_phrase") == "dokud nepřijde Babiš":
            fact["steno_id"] = "2025_24_01587"
            fact["citace"] = "navrhuji přerušení do přítomnosti premiéra této země"
    data["fakty"] = [f for f in data["fakty"] if f.get("link_phrase") != "Graf bytů"]


def fix_babis_odpovedi(data: dict) -> None:
    drop_phrases = {
        "bytové výstavby přímo v sále",
        "rok 2018, třicet tři tisíc bytů",
        "čtyřicet čtyři tisíc devět set devadesát dva v roce 2021",
        "Vy máte v DNA to udavačství",
        "udavačství v DNA",
        "Evropská komise a parlamenty nestačí zpracovávat jejich udání",
        "Ukazuje do sálu graf",
        "graf bytů",
    }
    data["fakty"] = [f for f in data["fakty"] if f.get("link_phrase") not in drop_phrases]
    remap_ids(data, ID_MAP["interpelace-babis-odpovedi-02-07.json"])
    for fact in data["fakty"]:
        if fact.get("link_phrase") == "dvě celé čtyři miliardy na chlebíčcích":
            fact["citace"] = (
                "prodrbali jste 2,4 miliardy na chlebíčcích, jako předsednictví a nic z toho nebylo, nic z toho nebylo"
            )
            fact["text"] = "Babiš: předchozí vláda prodrbala 2,4 miliardy na chlebíčcích."
    data["nadpis"] = "132 stran průšvihů"
    data["lead"] = (
        "Babiš proti Pirátům: „Vy mluvíte o bydlení? Vy, kteří jste to zničili?“ "
        "Listuje 132stránkovým materiálem jejich přešlapů a průšvihů: „Nebudu to číst,“ říká a jen ho listuje před kamerou. "
        "Doporučil Pirátům dva roky pryč, vyzval předchozí vládu ke kanálům a vyčítal 2,4 miliardy na chlebíčcích."
    )
    data["pointa"] = (
        "Lipavský (Piráti) ráno mluvil skoro tři tisíce slov u písemných interpelací, "
        "odpoledne Babiš (ANO) doporučil Pirátům dva roky pryč, vyzval předchozí vládu ke kanálům "
        "a vyčítal 2,4 miliardy na chlebíčcích."
    )
    data["citace_text"] = "Vy mluvíte o bydlení? Vy, kteří jste to zničili?"


def fix_obaly(data: dict) -> None:
    remap_ids(data, ID_MAP["novela-z-o-obalech.json"])
    for fact in data["fakty"]:
        if fact.get("citace") == "(Silný hluk v sále.)":
            fact["citace"] = "(Stále silný hluk v sále.)"
        if fact.get("link_phrase") == "omylem odměna TAČR":
            fact["citace"] = (
                "abychom dnes po bodu 150, což je ten TA ČR, zařadili v pořadí body 90, 37, 23, 27, 28 a 39."
            )
        if fact.get("link_phrase") == "Zákon o obalech":
            fact["citace"] = "sněmovní tisk 193/ – prvé čtení"


def main() -> None:
    handlers = {
        "interpelace-mrazova-bydleni-02-07.json": fix_mrazova,
        "interpelace-babis-odpovedi-02-07.json": fix_babis_odpovedi,
        "interpelace-babis-ipo-letiste-02-07.json": lambda d: remap_ids(d, ID_MAP["interpelace-babis-ipo-letiste-02-07.json"]),
        "interpelace-kovacik-povodi-02-07.json": lambda d: remap_ids(d, ID_MAP["interpelace-kovacik-povodi-02-07.json"]),
        "novela-z-o-obalech.json": fix_obaly,
        "novela-z-o-podnikani-na-kapitalovem-trhu-eu.json": lambda d: remap_ids(
            d, ID_MAP["novela-z-o-podnikani-na-kapitalovem-trhu-eu.json"]
        ),
    }
    for name, handler in handlers.items():
        path = FACTS / name
        data = json.loads(path.read_text(encoding="utf-8"))
        handler(data)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"fixed {name}")


if __name__ == "__main__":
    main()
