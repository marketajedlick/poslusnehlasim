#!/usr/bin/env python3
"""Audit jmen a stran v publikovaných článcích (facts/)."""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APPROVED_PATH = ROOT / "processed/publish-approved.json"
REPORT_PATH = ROOT / "processed/name-audit-report.txt"


def parse_key(key: str) -> tuple[int, int, str, str]:
    ob, sc, dz = key.split("/", 2)
    iso = datetime.strptime(dz.strip(), "%d.%m.%Y").strftime("%Y-%m-%d")
    return int(ob), int(sc), iso, dz.strip()


def load_keys(*, include_hidden: bool) -> list[str]:
    data = json.loads(APPROVED_PATH.read_text(encoding="utf-8"))
    keys = list(data.get("approved") or [])
    if include_hidden:
        keys.extend(data.get("hidden") or [])
    return keys


def load_steno(schuze: int, base: Path) -> dict[str, dict]:
    by_id: dict[str, dict] = {}
    path = base / "raw/steno.jsonl"
    if not path.is_file():
        return by_id
    for line in path.open(encoding="utf-8"):
        row = json.loads(line)
        by_id[row["id"]] = row
    return by_id


def main() -> int:
    sys.path.insert(0, str(ROOT))
    from svejk.validate.names import PoslanecIndex, audit_day, audit_topic

    parser = argparse.ArgumentParser(description="Audit jmen a stran v publikovaných článcích.")
    parser.add_argument(
        "--include-hidden",
        action="store_true",
        help="zahrnout i dny z publish-approved.json → hidden",
    )
    args = parser.parse_args()

    keys = load_keys(include_hidden=args.include_hidden)
    index = PoslanecIndex()
    all_issues = []
    by_code: dict[str, int] = defaultdict(int)

    for key in keys:
        ob, schuze, iso, _ = parse_key(key)
        base = ROOT / f"processed/{ob}-s{schuze}"
        day_path = base / "facts/by_day" / f"{iso}.json"
        if not day_path.is_file():
            continue
        steno_by_id = load_steno(schuze, base)
        day = json.loads(day_path.read_text(encoding="utf-8"))
        for issue in audit_day(day, index=index):
            all_issues.append((issue, key))
            by_code[issue.code] += 1
        for slug in day.get("topic_slugs") or []:
            topic_path = base / "facts/by_topic" / f"{slug}.json"
            if not topic_path.is_file():
                continue
            topic = json.loads(topic_path.read_text(encoding="utf-8"))
            if topic.get("publikovat") is False:
                continue
            for issue in audit_topic(topic, steno_by_id=steno_by_id, index=index):
                all_issues.append((issue, key))
                by_code[issue.code] += 1

    errors = [pair for pair in all_issues if pair[0].level == "error"]
    warns = [pair for pair in all_issues if pair[0].level == "warn"]

    print(f"Name audit: {len(keys)} dní, {len(errors)} chyb, {len(warns)} varování\n")
    print("Podle typu:")
    for code, count in sorted(by_code.items(), key=lambda x: -x[1]):
        print(f"  {code}: {count}")

    if errors:
        print(f"\n── CHYBY ({len(errors)}) ──")
        for issue, key in errors:
            print(f"  [{key}] {issue.slug}: {issue.message}")

    if warns:
        print(f"\n── VAROVÁNÍ ({len(warns)}) ──")
        for issue, key in warns[:25]:
            print(f"  [{key}] {issue.slug}: {issue.message}")
        if len(warns) > 25:
            print(f"  … +{len(warns) - 25} dalších")

    lines = [f"errors={len(errors)} warns={len(warns)}\n"]
    for issue, key in all_issues:
        lines.append(
            f"{issue.level}\t{issue.code}\t{key}\t{issue.slug}\t{issue.message}\n"
        )
    REPORT_PATH.write_text("".join(lines), encoding="utf-8")
    print(f"\nReport: {REPORT_PATH}")

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
