#!/usr/bin/env python3
"""Audit steno_id a citací ve všech publikovaných vydáních (publish-approved.json)."""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APPROVED_PATH = ROOT / "processed/publish-approved.json"


def norm(s: str) -> str:
    s = (s or "").strip()
    for old, new in (("„", '"'), (""", '"'), (""", '"')):
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


def parse_approved_key(key: str) -> tuple[int, int, str]:
    """2025/24/23.06.2026 -> (obdobi, schuze, iso_date)"""
    obdobi_s, schuze_s, datum_cz = key.split("/", 2)
    iso = datetime.strptime(datum_cz.strip(), "%d.%m.%Y").strftime("%Y-%m-%d")
    return int(obdobi_s), int(schuze_s), iso


def load_approved() -> list[tuple[int, int, str, str]]:
    data = json.loads(APPROVED_PATH.read_text(encoding="utf-8"))
    out: list[tuple[int, int, str, str]] = []
    for key in data.get("approved") or []:
        obdobi, schuze, iso = parse_approved_key(key)
        out.append((obdobi, schuze, iso, key))
    return out


STENO_CACHE: dict[Path, dict[str, dict]] = {}


def steno_by_id(steno_path: Path) -> dict[str, dict]:
    if steno_path not in STENO_CACHE:
        by_id: dict[str, dict] = {}
        if steno_path.is_file():
            for line in steno_path.open(encoding="utf-8"):
                r = json.loads(line)
                by_id[r["id"]] = r
        STENO_CACHE[steno_path] = by_id
    return STENO_CACHE[steno_path]


def find_correct_ids(steno_rows: dict[str, dict], cit: str) -> list[str]:
    hits: list[str] = []
    for sid, rec in steno_rows.items():
        if citace_in_text(cit, rec.get("text", "")):
            hits.append(sid)
    return hits


def main() -> int:
    approved = load_approved()
    issues: list[str] = []
    counts = defaultdict(int)
    missing_day = 0
    missing_steno_file = 0
    topics_checked = 0
    facts_checked = 0

    by_schuze: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for obdobi, schuze, iso, key in approved:
        base = ROOT / f"processed/{obdobi}-s{schuze}"
        day_path = base / "facts/by_day" / f"{iso}.json"
        steno_path = base / "raw/steno.jsonl"
        if not day_path.is_file():
            missing_day += 1
            issues.append(f"MISSING_DAY {key} ({day_path.name})")
            continue
        day = json.loads(day_path.read_text(encoding="utf-8"))
        if not steno_path.is_file():
            missing_steno_file += 1
            continue
        steno = steno_by_id(steno_path)
        topic_dir = base / "facts/by_topic"

        for slug in day.get("topic_slugs") or []:
            tpath = topic_dir / f"{slug}.json"
            if not tpath.is_file():
                issues.append(f"MISSING_TOPIC {key} {slug}")
                counts["missing_topic"] += 1
                by_schuze[schuze]["missing_topic"] += 1
                continue
            topic = json.loads(tpath.read_text(encoding="utf-8"))
            if topic.get("publikovat") is False:
                continue
            topics_checked += 1
            for i, f in enumerate(topic.get("fakty") or []):
                if not isinstance(f, dict):
                    continue
                cit = (f.get("citace") or "").strip()
                if not cit:
                    continue
                facts_checked += 1
                sid = (f.get("steno_id") or "").strip()
                src = f.get("source") or ""

                if src == "steno" and not sid:
                    issues.append(f"MISSING_ID {key} {slug}[{i}]")
                    counts["missing_id"] += 1
                    by_schuze[schuze]["missing_id"] += 1
                    continue

                if not sid:
                    # citace bez steno_id: ověř, jestli vůbec existuje ve stenu
                    hits = find_correct_ids(steno, cit)
                    if hits and len(cit) > 30:
                        issues.append(
                            f"ORPHAN_CITACE {key} {slug}[{i}] -> {hits[0]} ({steno[hits[0]].get('cele_jmeno')})"
                        )
                        counts["orphan_citace"] += 1
                        by_schuze[schuze]["orphan_citace"] += 1
                    continue

                rec = steno.get(sid)
                if not rec:
                    issues.append(f"UNKNOWN_ID {key} {slug}[{i}] {sid}")
                    counts["unknown_id"] += 1
                    by_schuze[schuze]["unknown_id"] += 1
                    continue

                if not citace_in_text(cit, rec.get("text", "")):
                    hits = find_correct_ids(steno, cit)
                    correct = hits[0] if hits else "?"
                    speaker = rec.get("cele_jmeno") or "?"
                    correct_sp = steno.get(correct, {}).get("cele_jmeno", "?") if correct != "?" else "?"
                    issues.append(
                        f"BAD_CITACE {key} {slug}[{i}] {sid}({speaker}) -> {correct}({correct_sp})"
                    )
                    counts["bad_citace"] += 1
                    by_schuze[schuze]["bad_citace"] += 1

    print(f"Approved days: {len(approved)}")
    print(f"Topics checked: {topics_checked}, facts with citace: {facts_checked}")
    print(f"Missing day files: {missing_day}, missing steno.jsonl: {missing_steno_file}")
    print()
    print("Issues by type:")
    for k in sorted(counts):
        print(f"  {k}: {counts[k]}")
    print()
    if by_schuze:
        print("By schuze (bad_citace + unknown_id + missing_id):")
        for schuze in sorted(by_schuze):
            d = by_schuze[schuze]
            total = d.get("bad_citace", 0) + d.get("unknown_id", 0) + d.get("missing_id", 0)
            if total:
                print(f"  s{schuze}: bad={d.get('bad_citace',0)} unknown={d.get('unknown_id',0)} missing_id={d.get('missing_id',0)}")

    if issues:
        print(f"\nFirst 60 issues ({len(issues)} total):")
        for line in issues[:60]:
            print(line)
        if len(issues) > 60:
            print(f"... and {len(issues) - 60} more")

    bad = counts["bad_citace"] + counts["unknown_id"] + counts["missing_id"]
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
