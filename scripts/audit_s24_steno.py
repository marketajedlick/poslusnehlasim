#!/usr/bin/env python3
"""Audit steno_id a citací v publikovaných topic souborech s24."""
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
    for n in (80, 60, 40, 24):
        chunk = ccit[:n].strip()
        if len(chunk) >= 16 and chunk in ntext:
            return True
    return False


def date_prefixes(datum_cz: str) -> list[str]:
    d = datetime.strptime(datum_cz.strip(), "%d.%m.%Y")
    return [(d + timedelta(days=delta)).strftime("%Y-%m-%d") for delta in (-1, 0, 1)]


def main() -> int:
    steno_by_id: dict[str, dict] = {}
    steno_rows: list[dict] = []
    for line in STENO_PATH.open(encoding="utf-8"):
        r = json.loads(line)
        steno_rows.append(r)
        steno_by_id[r["id"]] = r

    slugs: set[str] = set()
    for day in PUBLISHED_DAYS:
        data = json.loads((FACTS_DAY / f"{day}.json").read_text(encoding="utf-8"))
        slugs.update(data.get("topic_slugs") or [])

    bad_steno = 0
    bad_citace = 0
    missing_lp = 0

    for slug in sorted(slugs):
        path = FACTS_TOPIC / f"{slug}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        prefixes = date_prefixes(data.get("datum") or "01.01.2026")
        article = " ".join(
            (data.get(k) or "")
            for k in ("lead", "pointa", "mean", "citace_text")
        )
        for i, f in enumerate(data.get("fakty") or []):
            if not isinstance(f, dict):
                continue
            cit = (f.get("citace") or "").strip()
            sid = (f.get("steno_id") or "").strip()
            if not cit:
                continue
            if f.get("source") == "steno" and not sid:
                print(f"MISSING_ID {slug}[{i}]")
                bad_steno += 1
                continue
            if sid:
                rec = steno_by_id.get(sid)
                if not rec:
                    print(f"UNKNOWN_ID {slug}[{i}] {sid}")
                    bad_steno += 1
                elif not citace_in_text(cit, rec.get("text", "")):
                    print(f"BAD_CITACE {slug}[{i}] {sid} {rec.get('cele_jmeno')}")
                    bad_citace += 1
            elif f.get("source") == "steno":
                print(f"STENO_NO_ID {slug}[{i}]")
                bad_steno += 1
            lp = (f.get("link_phrase") or "").strip()
            if sid and lp and lp not in article:
                missing_lp += 1

    print(
        f"\nSummary: topics={len(slugs)} bad_steno={bad_steno} bad_citace={bad_citace} missing_link_phrase={missing_lp}"
    )
    return 1 if bad_steno or bad_citace else 0


if __name__ == "__main__":
    raise SystemExit(main())
