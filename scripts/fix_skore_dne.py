#!/usr/bin/env python3
"""Sjednotí stats.proslo / stats.zamitnuto ve facts/by_day s verdikty článků."""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APPROVED_PATH = ROOT / "processed/publish-approved.json"

sys.path.insert(0, str(ROOT))
from svejk.build.extract import skore_z_verdiktu  # noqa: E402
from svejk.paths import SchuzePaths  # noqa: E402


def parse_key(key: str) -> tuple[int, int, str]:
    ob, sch, cz = key.split("/", 2)
    return int(ob), int(sch), datetime.strptime(cz.strip(), "%d.%m.%Y").strftime("%Y-%m-%d")


def main() -> int:
    dry = "--dry-run" in sys.argv
    approved = json.loads(APPROVED_PATH.read_text(encoding="utf-8")).get("approved") or []
    changed = 0

    for key in approved:
        ob, sch, iso = parse_key(key)
        paths = SchuzePaths.create(ob, sch)
        day_path = paths.facts_by_day / f"{iso}.json"
        if not day_path.is_file():
            continue
        day = json.loads(day_path.read_text(encoding="utf-8"))
        if day.get("skore_manual"):
            continue
        slugs = day.get("topic_slugs") or []
        sp, sz = skore_z_verdiktu(slugs, paths)
        stats = dict(day.get("stats") or {})
        dp = int(stats.get("proslo") or day.get("proslo") or 0)
        dz = int(stats.get("zamitnuto") or day.get("zamitnuto") or 0)
        if sp == dp and sz == dz:
            continue
        stats["proslo"] = sp
        stats["zamitnuto"] = sz
        day["stats"] = stats
        day["proslo"] = sp
        day["zamitnuto"] = sz
        print(f"{key}: {dp}:{dz} -> {sp}:{sz}")
        if not dry:
            day_path.write_text(
                json.dumps(day, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        changed += 1

    print(f"{'would fix' if dry else 'fixed'} {changed} days")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
