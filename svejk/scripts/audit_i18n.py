#!/usr/bin/env python3
"""Kontrola anglických překladů: locale JSON, facts en bloky, glosář."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from svejk.build.facts_i18n import day_needs_translation, has_en_translation, topic_needs_translation
from svejk.glossary import GLOSSARY_EN
from svejk.paths import SchuzePaths, processed_root


def _flatten_keys(d: dict, prefix: str = "") -> set[str]:
    keys: set[str] = set()
    for k, v in d.items():
        p = f"{prefix}.{k}" if prefix else k
        keys.add(p)
        if isinstance(v, dict):
            keys.update(_flatten_keys(v, p))
    return keys


def _empty_en_keys(cs: dict, en: dict, prefix: str = "") -> list[str]:
    out: list[str] = []
    for k, v_cs in cs.items():
        p = f"{prefix}.{k}" if prefix else k
        if k not in en:
            continue
        v_en = en[k]
        if isinstance(v_cs, str) and isinstance(v_en, str) and v_cs.strip() and not v_en.strip():
            if p != "glossary_page.notice":
                out.append(p)
        elif isinstance(v_cs, dict) and isinstance(v_en, dict):
            out.extend(_empty_en_keys(v_cs, v_en, p))
    return out


def _load_approved_keys() -> list[str]:
    path = processed_root() / "publish-approved.json"
    if not path.is_file():
        return []
    return list(json.loads(path.read_text()).get("approved") or [])


def _approved_topic_paths(obdobi: int) -> set[Path]:
    topics: set[Path] = set()
    for key in _load_approved_keys():
        ob, schuze_s, datum = key.split("/", 2)
        paths = SchuzePaths.create(int(ob), int(schuze_s))
        when = datetime.strptime(datum, "%d.%m.%Y")
        day_path = paths.facts_by_day / f"{when.strftime('%Y-%m-%d')}.json"
        if not day_path.is_file():
            continue
        day = json.loads(day_path.read_text(encoding="utf-8"))
        for slug in day.get("topic_slugs") or []:
            tp = paths.facts_by_topic / f"{slug}.json"
            if tp.is_file():
                topics.add(tp)
    return topics


def audit_locale() -> list[str]:
    cs = json.loads((ROOT / "svejk/locale/cs.json").read_text(encoding="utf-8"))
    en = json.loads((ROOT / "svejk/locale/en.json").read_text(encoding="utf-8"))
    issues: list[str] = []
    missing = sorted(_flatten_keys(cs) - _flatten_keys(en))
    extra = sorted(_flatten_keys(en) - _flatten_keys(cs))
    empty = _empty_en_keys(cs, en)
    if missing:
        issues.append(f"locale: chybí v en.json: {', '.join(missing)}")
    if extra:
        issues.append(f"locale: navíc v en.json: {', '.join(extra)}")
    if empty:
        issues.append(f"locale: prázdné v en.json: {', '.join(empty)}")
    return issues


def audit_approved_facts(obdobi: int) -> list[str]:
    issues: list[str] = []
    approved_topics = _approved_topic_paths(obdobi)
    for key in _load_approved_keys():
        ob, schuze_s, datum = key.split("/", 2)
        paths = SchuzePaths.create(int(ob), int(schuze_s))
        when = datetime.strptime(datum, "%d.%m.%Y")
        day_path = paths.facts_by_day / f"{when.strftime('%Y-%m-%d')}.json"
        if day_path.is_file():
            day = json.loads(day_path.read_text(encoding="utf-8"))
            if day_needs_translation(day):
                issues.append(f"day bez en: {day_path.relative_to(ROOT)}")
    for tp in sorted(approved_topics):
        fact = json.loads(tp.read_text(encoding="utf-8"))
        if topic_needs_translation(fact):
            issues.append(f"topic bez en: {tp.relative_to(ROOT)}")
        elif has_en_translation(fact):
            en_fakty = (fact.get("en") or {}).get("fakty") or []
            cs_fakty = fact.get("fakty") or []
            for i, row in enumerate(cs_fakty):
                if not isinstance(row, dict):
                    continue
                citace = (row.get("citace") or "").strip()
                if not citace:
                    continue
                en_cit = ""
                if i < len(en_fakty) and isinstance(en_fakty[i], dict):
                    en_cit = (en_fakty[i].get("citace") or "").strip()
                if not en_cit:
                    issues.append(f"citace bez en: {tp.relative_to(ROOT)} #{i + 1}")
    return issues


def audit_glossary() -> list[str]:
    issues: list[str] = []
    if len(GLOSSARY_EN) < 150:
        issues.append(
            f"glossary: GLOSSARY_EN má jen {len(GLOSSARY_EN)} položek "
            f"(očekáváno 150+, český glosář má víc variant frází)"
        )
    return issues


def run_audit(obdobi: int = 2025) -> list[str]:
    return audit_locale() + audit_approved_facts(obdobi) + audit_glossary()


def main() -> int:
    p = argparse.ArgumentParser(description="Audit anglických překladů webu.")
    p.add_argument("--obdobi", type=int, default=2025)
    args = p.parse_args()

    issues = run_audit(args.obdobi)
    if issues:
        for line in issues:
            print(line)
        print(json.dumps({"ok": False, "issues": len(issues)}, ensure_ascii=False))
        return 1
    print(json.dumps({"ok": True, "issues": 0}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
