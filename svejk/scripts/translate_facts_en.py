#!/usr/bin/env python3
"""Doplní blok ``en`` do facts JSON pro schválená vydání."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from fix_en_terminology import apply_en_terminology
from svejk.build.facts_i18n import day_needs_translation, topic_needs_translation
from svejk.paths import SchuzePaths, processed_root

try:
    from svejk.build.io import read_json
except ImportError:
    def read_json(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

try:
    from deep_translator import GoogleTranslator
except ImportError:
    GoogleTranslator = None  # type: ignore[misc, assignment]

_TRANSLATOR = None
_DELAY = 0.15


def _translator() -> "GoogleTranslator":
    global _TRANSLATOR
    if GoogleTranslator is None:
        raise SystemExit("Nainstaluj: pip install deep-translator")
    if _TRANSLATOR is None:
        _TRANSLATOR = GoogleTranslator(source="cs", target="en")
    return _TRANSLATOR


def _translate(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return t
    if len(t) > 4500:
        parts: list[str] = []
        chunk = ""
        for para in t.split("\n"):
            candidate = f"{chunk}\n{para}".strip() if chunk else para
            if len(candidate) > 4000:
                if chunk:
                    parts.append(_translate(chunk))
                chunk = para
            else:
                chunk = candidate
        if chunk:
            parts.append(_translator().translate(chunk))
        time.sleep(_DELAY)
        return "\n".join(parts)
    out = _translator().translate(t)
    time.sleep(_DELAY)
    return out


def _translate_list(items: list[str]) -> list[str]:
    return [_translate(x) for x in items if (x or "").strip()]


def _translate_fakty(fakty: list[dict], *, citace_only: bool = False) -> list[dict]:
    out: list[dict] = []
    for row in fakty:
        if not isinstance(row, dict):
            continue
        en_row: dict = {}
        if not citace_only and (row.get("text") or "").strip():
            en_row["text"] = _translate(str(row["text"]))
        citace = (row.get("citace") or "").strip()
        if citace:
            en_row["citace"] = _translate(str(row["citace"]))
        if en_row:
            out.append(en_row)
    return out


def _backfill_topic_citace(fact: dict) -> dict | None:
    """Doplní/přepíše en.fakty[].citace z českých fakty."""
    cs_fakty = fact.get("fakty") or []
    if not cs_fakty:
        return None
    en = dict(fact.get("en") or {})
    en_fakty = list(en.get("fakty") or [])
    changed = False
    for i, row in enumerate(cs_fakty):
        if not isinstance(row, dict):
            continue
        citace = (row.get("citace") or "").strip()
        if not citace:
            continue
        while len(en_fakty) <= i:
            en_fakty.append({})
        en_row = dict(en_fakty[i]) if isinstance(en_fakty[i], dict) else {}
        translated = apply_en_terminology(_translate(citace))
        if en_row.get("citace") != translated:
            en_row["citace"] = translated
            en_fakty[i] = en_row
            changed = True
    if not changed:
        return None
    en["fakty"] = en_fakty
    return en


def _translate_links(links: list[dict], *, label_key: str) -> list[dict]:
    out: list[dict] = []
    for entry in links:
        if not isinstance(entry, dict):
            continue
        label = (entry.get(label_key) or "").strip()
        page = (entry.get("page") or "").strip()
        if not label or not page:
            continue
        out.append({label_key: _translate(label), "page": page})
    return out


def translate_topic(fact: dict) -> dict:
    en: dict = {}
    for key in ("nadpis", "lead", "pointa", "mean", "kuriozita", "predmet_lidsky"):
        val = (fact.get(key) or "").strip()
        if val:
            en[key] = _translate(val)
    koho = fact.get("koho") or []
    if koho:
        en["koho"] = _translate_list([str(x) for x in koho])
    fakty = fact.get("fakty") or []
    if fakty:
        en["fakty"] = _translate_fakty(fakty)
    if fact.get("mean_links"):
        en["mean_links"] = _translate_links(fact["mean_links"], label_key="phrase")
    if fact.get("kuriozita_links"):
        en["kuriozita_links"] = _translate_links(
            fact["kuriozita_links"], label_key="label"
        )
    return apply_en_terminology(en)


def translate_day(day: dict) -> dict:
    en: dict = {}
    for key in ("dnesni_ucet", "zaver", "result_note"):
        val = (day.get(key) or "").strip()
        if val:
            en[key] = _translate(val)
    vysledek = day.get("vysledek") or []
    if vysledek:
        en["vysledek"] = _translate_list([str(x) for x in vysledek])
    den = (day.get("den") or "").strip()
    if den:
        mapping = {
            "pondělí": "Monday",
            "úterý": "Tuesday",
            "středa": "Wednesday",
            "čtvrtek": "Thursday",
            "pátek": "Friday",
            "sobota": "Saturday",
            "neděle": "Sunday",
        }
        en["den"] = mapping.get(den.lower(), den)
    return apply_en_terminology(en)


def _write_json(path: Path, data: dict) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _load_approved_keys(obdobi: int) -> list[str]:
    path = processed_root() / "publish-approved.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return list(data.get("approved") or [])


def _edition_from_key(key: str):
    from datetime import datetime

    obdobi_s, schuze_s, datum = key.split("/", 2)
    return int(obdobi_s), int(schuze_s), datum, datetime.strptime(datum, "%d.%m.%Y")


def _all_published_paths(obdobi: int) -> tuple[set[Path], set[Path]]:
    day_paths: set[Path] = set()
    topic_paths: set[Path] = set()
    root = processed_root()
    for ob_dir in sorted(root.glob(f"{obdobi}-s*")):
        facts = ob_dir / "facts"
        if not facts.is_dir():
            continue
        for dp in (facts / "by_day").glob("*.json"):
            day = read_json(dp)
            if day.get("dnesni_ucet") or day.get("zaver"):
                day_paths.add(dp)
        for tp in (facts / "by_topic").glob("*.json"):
            fact = read_json(tp)
            if fact.get("publikovat"):
                topic_paths.add(tp)
    return day_paths, topic_paths


_HLASOVANI_PREFIXES = ("hlasovani-neprosli", "hlasovani-prosli", "hlasovani-zvoleni")


def _approved_hlasovani_paths(obdobi: int) -> set[Path]:
    paths_out: set[Path] = set()
    for key in _load_approved_keys(obdobi):
        ob, schuze_s, datum = key.split("/", 2)
        paths = SchuzePaths.create(int(ob), int(schuze_s))
        when = _edition_from_key(key)[3]
        date_s = when.strftime("%Y-%m-%d")
        for prefix in _HLASOVANI_PREFIXES:
            hp = paths.facts / f"{prefix}-{date_s}.json"
            if hp.is_file():
                paths_out.add(hp)
    return paths_out


def _translate_varovani_citace(val: str) -> str:
    return apply_en_terminology(_translate(val))


def translate_hlasovani(data: dict) -> dict:
    en_rows: list[dict] = []
    for row in data.get("radky") or []:
        if not isinstance(row, dict):
            continue
        jmeno = (row.get("jmeno") or "").strip()
        var = row.get("varovani") or {}
        if not jmeno or not isinstance(var, dict):
            continue
        en_var: dict = {}
        shrnuti = (var.get("shrnuti") or "").strip()
        citace = var.get("citace")
        if shrnuti:
            en_var["shrnuti"] = _translate_varovani_citace(shrnuti)
        if citace:
            if isinstance(citace, list):
                en_var["citace"] = [
                    _translate_varovani_citace(str(c)) for c in citace if str(c).strip()
                ]
            elif isinstance(citace, str) and citace.strip():
                en_var["citace"] = _translate_varovani_citace(citace)
        if en_var:
            en_rows.append({"jmeno": jmeno, "varovani": en_var})
    return {"radky": en_rows}


def _backfill_hlasovani_citace(data: dict) -> dict | None:
    en = dict(data.get("en") or {})
    en_by_name: dict[str, dict] = {}
    for row in en.get("radky") or []:
        if isinstance(row, dict) and (row.get("jmeno") or "").strip():
            en_by_name[str(row["jmeno"]).strip()] = dict(row)
    changed = False
    for row in data.get("radky") or []:
        if not isinstance(row, dict):
            continue
        jmeno = (row.get("jmeno") or "").strip()
        var = row.get("varovani") or {}
        if not jmeno or not isinstance(var, dict):
            continue
        citace = var.get("citace")
        if not citace:
            continue
        en_row = en_by_name.setdefault(jmeno, {"jmeno": jmeno, "varovani": {}})
        en_var = dict(en_row.get("varovani") or {})
        if isinstance(citace, list):
            translated = [
                _translate_varovani_citace(str(c)) for c in citace if str(c).strip()
            ]
            if en_var.get("citace") != translated:
                en_var["citace"] = translated
                changed = True
        elif isinstance(citace, str) and citace.strip():
            translated = _translate_varovani_citace(citace)
            if en_var.get("citace") != translated:
                en_var["citace"] = translated
                changed = True
        en_row["varovani"] = en_var
        en_by_name[jmeno] = en_row
    if not changed:
        return None
    en["radky"] = list(en_by_name.values())
    return en


def _approved_paths(obdobi: int) -> tuple[set[Path], set[Path]]:
    day_paths: set[Path] = set()
    topic_paths: set[Path] = set()
    for key in _load_approved_keys(obdobi):
        ob, schuze, datum, when = _edition_from_key(key)
        paths = SchuzePaths.create(ob, schuze)
        day_path = paths.facts_by_day / f"{when.strftime('%Y-%m-%d')}.json"
        if day_path.is_file():
            day_paths.add(day_path)
            day = read_json(day_path)
            for slug in day.get("topic_slugs") or []:
                tp = paths.facts_by_topic / f"{slug}.json"
                if tp.is_file():
                    topic_paths.add(tp)
    return day_paths, topic_paths


def run(
    obdobi: int,
    *,
    force: bool = False,
    dry_run: bool = False,
    citace_only: bool = False,
    all_published: bool = False,
    hlasovani: bool = False,
) -> dict[str, int]:
    if hlasovani or citace_only:
        hlasovani_paths = _approved_hlasovani_paths(obdobi)
        stats = {"hlasovani": 0, "topics_citace": 0, "skipped": 0}
        for hp in sorted(hlasovani_paths):
            data = read_json(hp)
            if citace_only and not hlasovani:
                new_en = _backfill_hlasovani_citace(data)
            elif force or not data.get("en"):
                new_en = translate_hlasovani(data)
            else:
                new_en = _backfill_hlasovani_citace(data)
            if new_en is None:
                stats["skipped"] += 1
                continue
            if dry_run:
                print(f"hlasovani: {hp.relative_to(processed_root())}")
                stats["hlasovani"] += 1
                continue
            data["en"] = new_en
            _write_json(hp, data)
            stats["hlasovani"] += 1
            print(f"✓ hlasovani {hp.name}")
        if citace_only:
            if all_published:
                _, topic_paths = _all_published_paths(obdobi)
            else:
                _, topic_paths = _approved_paths(obdobi)
            for tp in sorted(topic_paths):
                fact = read_json(tp)
                if not fact.get("en"):
                    stats["skipped"] += 1
                    continue
                new_en = _backfill_topic_citace(fact)
                if new_en is None:
                    stats["skipped"] += 1
                    continue
                if dry_run:
                    print(f"citace: {tp.relative_to(processed_root())}")
                    stats["topics_citace"] += 1
                    continue
                fact["en"] = new_en
                _write_json(tp, fact)
                stats["topics_citace"] += 1
                print(f"✓ citace {tp.name}")
        return stats

    if all_published:
        day_paths, topic_paths = _all_published_paths(obdobi)
    else:
        day_paths, topic_paths = _approved_paths(obdobi)
    stats = {"topics": 0, "days": 0, "skipped": 0}

    for tp in sorted(topic_paths):
        fact = read_json(tp)
        if not force and not topic_needs_translation(fact):
            stats["skipped"] += 1
            continue
        if dry_run:
            print(f"topic: {tp.relative_to(processed_root())}")
            stats["topics"] += 1
            continue
        fact["en"] = translate_topic(fact)
        _write_json(tp, fact)
        stats["topics"] += 1
        print(f"✓ topic {tp.name}")

    for dp in sorted(day_paths):
        day = read_json(dp)
        if not force and not day_needs_translation(day):
            stats["skipped"] += 1
            continue
        if dry_run:
            print(f"day: {dp.relative_to(processed_root())}")
            stats["days"] += 1
            continue
        day["en"] = translate_day(day)
        _write_json(dp, day)
        stats["days"] += 1
        print(f"✓ day {dp.name}")

    return stats


def main() -> int:
    p = argparse.ArgumentParser(description="Přeloží schválená vydání do bloku en v facts JSON.")
    p.add_argument("--obdobi", type=int, default=2025)
    p.add_argument("--force", action="store_true", help="Přepsat existující en bloky")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument(
        "--citace-only",
        action="store_true",
        help="Přeložit jen citace ve faktech a varovani (bez přepisu ostatního en)",
    )
    p.add_argument(
        "--all-published",
        action="store_true",
        help="Všechna publikovaná témata/dny, ne jen schválená vydání",
    )
    p.add_argument(
        "--hlasovani",
        action="store_true",
        help="Přeložit hlasovani-*.json (vyznamenání tabulky)",
    )
    args = p.parse_args()
    stats = run(
        args.obdobi,
        force=args.force,
        dry_run=args.dry_run,
        citace_only=args.citace_only,
        all_published=args.all_published,
        hlasovani=args.hlasovani,
    )
    print(json.dumps(stats, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
