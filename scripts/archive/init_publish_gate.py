#!/usr/bin/env python3
"""Jednorázově: publish-approved.json + snapshoty z produkce pro držená vydání."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from svejk.build.nav import list_obdobi_editions
from svejk.build.publish import edition_key, fetch_production_snapshot
from svejk.paths import processed_root

HELD = ["2025/22/11.06.2026", "2025/23/11.06.2026"]


def main() -> int:
    approved = []
    for e in list_obdobi_editions(2025):
        key = edition_key(e.obdobi, e.schuze, e.datum_unl)
        if key not in HELD:
            approved.append(key)

    data = {
        "comment": (
            "approved = sestavit z lokálních facts. "
            "held = zatím jen z publish-snapshots/ (produkce), ne z lokálních dat. "
            "Nové vydání = po doladění přidat klíč do approved."
        ),
        "held": HELD,
        "approved": approved,
    }
    path = processed_root() / "publish-approved.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(approved)} approved editions to {path}")

    for key in HELD:
        dest = fetch_production_snapshot(key, overwrite=True)
        print(f"Snapshot: {dest} ({dest.stat().st_size} B)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
