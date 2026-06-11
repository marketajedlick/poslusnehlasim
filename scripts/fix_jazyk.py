#!/usr/bin/env python3
"""Jednorázové jazykové opravy ve facts/*.json (editorial pole)."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FACTS = ROOT / "processed"

EDITORIAL_KEYS = frozenset(
    {"lead", "pointa", "mean", "zaver", "dnesni_ucet", "nadpis", "predmet_lidsky"}
)

SNEMOVNA_LOWERCASE = re.compile(
    r"\b("
    r"do sněmovny|ve sněmovně|o sněmovně|"
    r"souhlasu sněmovny|bez souhlasu sněmovny|"
    r"místopředsedkyní sněmovny|orgán[^.]{0,40}sněmovny|"
    r"postoji sněmovny|předseda sněmovny|"
    r"složení orgánů sněmovny|nové sněmovny|malá sněmovna"
    r")\b",
    re.I,
)


def _capitalize_snemovna(text: str) -> str:
    protected: dict[str, str] = {}

    def protect(m: re.Match[str]) -> str:
        key = f"__SN_{len(protected)}__"
        protected[key] = m.group(0)
        return key

    tmp = SNEMOVNA_LOWERCASE.sub(protect, text)
    tmp = re.sub(r"\bsněmovna\b", "Sněmovna", tmp)
    for key, value in protected.items():
        tmp = tmp.replace(key, value)
    return tmp


def _unify_terminology(text: str) -> str:
    replacements = [
        ("ve finálním kole", "v závěrečném hlasování"),
        ("Ve finálním kole", "V závěrečném hlasování"),
        ("finálním hlasování", "závěrečném hlasování"),
        ("finální hlasování", "závěrečné hlasování"),
        ("Finální hlasování", "Závěrečné hlasování"),
        ("finální kolo", "závěrečné hlasování"),
        ("Finální kolo", "Závěrečné hlasování"),
        ("ve finále", "v závěrečném hlasování"),
        ("Ve finále", "V závěrečném hlasování"),
        ("druhé a finální kolo", "druhé kolo a závěrečné hlasování"),
        ("druhé a závěrečné hlasování", "druhé kolo a závěrečné hlasování"),
    ]
    for old, new in replacements:
        text = text.replace(old, new)
    return text


def _fix_text(key: str, text: str, path: Path) -> str:
    text = _unify_terminology(text)
    text = _capitalize_snemovna(text)

    if path.name == "novela-z-o-cenach-2.json" and key == "pointa":
        text = text.replace(
            "Jakob mluvil o zrychlené projednávání jako zkratce",
            "Jakob mluvil o zrychleném projednávání jako o zkratce",
        )
    if path.name == "novela-z-o-cenach-debata-1-cteni.json" and key == "lead":
        text = text.replace(
            "Vláda tlačila zkrácená debata v zrychlené projednávání",
            "Vláda tlačila na zrychlené projednávání",
        )
    if path.name == "novela-z-o-cenach.json" and key == "lead":
        text = text.replace(
            "Večer čtrnácté schůze schválili",
            "Večer na čtrnácté schůzi schválili",
        )
    if path.name == "n-z-kterym-se-zrusuje-nominacni-zakon.json" and key == "pointa":
        text = text.replace(
            "Koalice chtěla zákon zrušit zčistajasna",
            "Koalice chtěla zákon zrušit rovnou",
        )
    if path.name == "sudetonemecky-sjezd-debata.json":
        if key == "mean":
            text = text.replace("přípravu usnesení", "debata nad usnesením")
        if key == "nadpis":
            text = "O Brně se hádali do noci"
    if path.name == "stanovisko-vladni-koalice-ke-sjezdu-sudetonemeck.json":
        if key == "nadpis":
            text = "Sjezd v Brně došel až do noci"
        if key == "lead":
            text = text.replace(
                "Ve středu v noci sněmovna schválila",
                "Pozdě v noci Sněmovna schválila",
            ).replace(
                "Ve středu v noci Sněmovna schválila",
                "Pozdě v noci Sněmovna schválila",
            )
    if path.name == "novela-z-stavebni-zakon.json":
        if key == "lead":
            text = text.replace(
                "Ve středu večer sněmovna schválila",
                "Večer Sněmovna schválila",
            ).replace(
                "Ve středu večer Sněmovna schválila",
                "Večer Sněmovna schválila",
            )
        if key == "pointa":
            text = text.replace("Ve středu večer prošlo", "Večer prošlo")
    if path.name == "novela-z-o-statni-socialni-podpore.json" and key == "lead":
        text = text.replace(
            "Sněmovna ve středu večer schválila",
            "Večer Sněmovna schválila",
        )
    if path.name == "novela-z-o-socialnich-sluzbach.json" and key == "lead":
        text = text.replace(
            "Ve středu v deset hodin večer schválili",
            "Kolem desáté večer schválili",
        )
    if path.name == "novela-z-o-zivotnim-a-existencnim-minimu.json" and key == "nadpis":
        text = "Minimum neprošlo"
    if path.name == "novela-z-o-zdrav-prostr-a-diagnostickych-zdrav-p.json" and key == "nadpis":
        text = "Zkumavky budou pod dohledem"
    if path.name == "2026-05-06.json" and key == "zaver":
        text = text.replace(
            "že ve středu v noci sněmovna odsoudila",
            "že pozdě v noci Sněmovna odsoudila",
        ).replace(
            "že ve středu v noci Sněmovna odsoudila",
            "že pozdě v noci Sněmovna odsoudila",
        )
    return text


def _walk(obj, path: Path, key: str | None = None):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk(v, path, k)
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, str) and key == "vysledek":
                yield ("vysledek", item)
            else:
                yield from _walk(item, path, key)
    elif isinstance(obj, str) and key in EDITORIAL_KEYS:
        yield (key, obj)


def main() -> None:
    changed = 0
    for json_path in sorted(FACTS.glob("**/facts/**/*.json")):
        data = json.loads(json_path.read_text(encoding="utf-8"))
        dirty = False

        def apply(key: str, value: str) -> str:
            nonlocal dirty
            fixed = _fix_text(key, value, json_path)
            if fixed != value:
                dirty = True
            return fixed

        for field in EDITORIAL_KEYS:
            if field in data and isinstance(data[field], str):
                data[field] = apply(field, data[field])

        if isinstance(data.get("vysledek"), list):
            data["vysledek"] = [apply("vysledek", line) for line in data["vysledek"]]

        if isinstance(data.get("koho"), list):
            data["koho"] = [
                apply("koho", line) if isinstance(line, str) else line for line in data["koho"]
            ]

        if dirty:
            json_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            changed += 1
            print(json_path.relative_to(ROOT))

    print(f"Upraveno {changed} souborů.")


if __name__ == "__main__":
    main()
