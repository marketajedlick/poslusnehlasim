#!/usr/bin/env python3
"""Auto-oprava steno_id a citací ve všech publikovaných vydáních (kromě ručních patchů s24)."""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta
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


def date_prefixes(datum_cz: str) -> list[str]:
    d = datetime.strptime(datum_cz.strip(), "%d.%m.%Y")
    return [(d + timedelta(days=delta)).strftime("%Y-%m-%d") for delta in (-1, 0, 1)]


def sanitize_dashes(s: str) -> str:
    return (s or "").replace("—", ", ").replace("–", ", ")


def excerpt_from_steno(cit: str, text: str, max_words: int = 15) -> str:
    if citace_in_text(cit, text):
        flat = re.sub(r"\s+", " ", cit.strip())
        if len(flat.split()) <= max_words:
            return sanitize_dashes(flat)
    ntext = text or ""
    needle = norm(cit).strip('"').strip("'")
    for n in (80, 60, 40, 24, 16):
        chunk = needle[:n].strip()
        if len(chunk) < 12:
            continue
        if norm(ntext).find(chunk) < 0:
            continue
        words = ntext.split()
        acc = ""
        start_words: list[str] = []
        for w in words:
            acc = (acc + " " + w).strip()
            if norm(acc).find(chunk[: min(len(chunk), 24)]) >= 0:
                start_words = acc.split()
                break
        if not start_words:
            continue
        start = ntext.find(start_words[0])
        return sanitize_dashes(" ".join(ntext[start:].split()[:max_words]))
    return sanitize_dashes(cit.strip())


def strip_steno_fields(f: dict) -> None:
    f.pop("steno_id", None)
    f.pop("link_phrase", None)
    if f.get("source") == "steno":
        f.pop("source", None)


def load_steno(path: Path) -> tuple[list[dict], dict[str, dict]]:
    rows: list[dict] = []
    by_id: dict[str, dict] = {}
    if not path.is_file():
        return rows, by_id
    for line in path.open(encoding="utf-8"):
        r = json.loads(line)
        rows.append(r)
        by_id[r["id"]] = r
    return rows, by_id


def find_steno_ids(
    steno_rows: list[dict], cit: str, prefixes: list[str] | None, *, all_days: bool = False
) -> list[str]:
    hits: list[str] = []
    for r in steno_rows:
        if not all_days and prefixes:
            if not any((r.get("datum") or "").startswith(p) for p in prefixes):
                continue
        if citace_in_text(cit, r.get("text", "")):
            hits.append(r["id"])
    return hits


def fix_fact(
    f: dict, steno_rows: list[dict], steno_by_id: dict[str, dict], prefixes: list[str]
) -> bool:
    cit = (f.get("citace") or "").strip()
    if not cit:
        if f.get("source") == "steno":
            strip_steno_fields(f)
        return False
    all_days = "Hlasování číslo" in cit or "hlasování číslo" in cit
    hits = find_steno_ids(steno_rows, cit, prefixes, all_days=all_days)
    if not hits:
        hits = find_steno_ids(steno_rows, cit, None, all_days=True)
    sid = (f.get("steno_id") or "").strip()
    if sid and sid in hits and citace_in_text(cit, steno_by_id[sid].get("text", "")):
        f["steno_id"] = sid
        f["source"] = "steno"
        f["citace"] = excerpt_from_steno(cit, steno_by_id[sid].get("text", ""))
        return True
    if hits:
        sid = hits[0]
        f["steno_id"] = sid
        f["source"] = "steno"
        f["citace"] = excerpt_from_steno(cit, steno_by_id[sid].get("text", ""))
        return True
    strip_steno_fields(f)
    return False


def fix_topic(data: dict, steno_rows: list[dict], steno_by_id: dict[str, dict]) -> int:
    datum = data.get("datum") or ""
    if not datum:
        return 0
    prefixes = date_prefixes(datum)
    n = 0
    for f in data.get("fakty") or []:
        if isinstance(f, dict) and fix_fact(f, steno_rows, steno_by_id, prefixes):
            n += 1
    ct = (data.get("citace_text") or "").strip()
    ctsid = (data.get("steno_id") or "").strip()
    if ct and ctsid:
        rec = steno_by_id.get(ctsid)
        if not rec or not citace_in_text(ct, rec.get("text", "")):
            hits = find_steno_ids(steno_rows, ct, prefixes)
            if hits:
                data["steno_id"] = hits[0]
            else:
                data.pop("steno_id", None)
    return n


def parse_key(key: str) -> tuple[int, int, str, str]:
    obdobi_s, schuze_s, datum_cz = key.split("/", 2)
    iso = datetime.strptime(datum_cz.strip(), "%d.%m.%Y").strftime("%Y-%m-%d")
    return int(obdobi_s), int(schuze_s), iso, datum_cz


def main() -> int:
    skip_schuze = {24}
    if "--include-s24" in sys.argv:
        skip_schuze = set()

    approved = json.loads(APPROVED_PATH.read_text(encoding="utf-8")).get("approved") or []
    steno_loaded: dict[int, tuple[list[dict], dict[str, dict]]] = {}
    changed_days: set[tuple[int, int, str]] = set()
    files = 0

    for key in approved:
        obdobi, schuze, iso, datum_cz = parse_key(key)
        if schuze in skip_schuze:
            continue
        base = ROOT / f"processed/{obdobi}-s{schuze}"
        day_path = base / "facts/by_day" / f"{iso}.json"
        if not day_path.is_file():
            continue
        if schuze not in steno_loaded:
            steno_loaded[schuze] = load_steno(base / "raw/steno.jsonl")
        steno_rows, steno_by_id = steno_loaded[schuze]
        day = json.loads(day_path.read_text(encoding="utf-8"))
        topic_dir = base / "facts/by_topic"

        for slug in day.get("topic_slugs") or []:
            tpath = topic_dir / f"{slug}.json"
            if not tpath.is_file():
                continue
            before = tpath.read_text(encoding="utf-8")
            data = json.loads(before)
            if data.get("publikovat") is False:
                continue
            fix_topic(data, steno_rows, steno_by_id)
            after = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
            if after != before:
                tpath.write_text(after, encoding="utf-8")
                changed_days.add((obdobi, schuze, datum_cz))
                files += 1

    print(f"Updated {files} topic files across {len(changed_days)} days")
    for obdobi, schuze, datum_cz in sorted(changed_days, key=lambda x: (x[1], x[2])):
        print(f"  {obdobi}/s{schuze}/{datum_cz}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
