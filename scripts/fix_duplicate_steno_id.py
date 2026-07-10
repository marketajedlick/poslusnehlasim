#!/usr/bin/env python3
"""Opraví duplicate_steno_id: stejná nebo pozdravová citace → unikátní úryvek ze stena."""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_published_steno import citace_in_text, find_correct_ids, steno_by_id  # noqa: E402
from scripts.fix_published_citace import (  # noqa: E402
    GREETING_RE,
    find_excerpt,
    is_vote_summary,
    strip_steno_fields,
)

APPROVED_PATH = ROOT / "processed/publish-approved.json"
GREETING_ONLY = re.compile(
    r"^(děkuj|děkuju|vážen|dobrý den|pane předsed|kolegové|přeji|přeji vám)\b",
    re.I,
)
ANCHOR_SKIP = re.compile(r"^(Hlasování|Konstatuji)\b", re.I)


def parse_key(k: str) -> tuple[int, int, str, str]:
    ob, sch, cz = k.split("/", 2)
    iso = datetime.strptime(cz.strip(), "%d.%m.%Y").strftime("%Y-%m-%d")
    return int(ob), int(sch), iso, cz.strip()


def anchor_from_fact(f: dict) -> str:
    text = (f.get("text") or "").strip()
    for prefix in (
        r"^[^:]+:\s*",
        r"^[^:]+:\s*řekl:\s*",
        r"^[^:]+:\s*uvedl,\s*že\s*",
        r"^[^:]+:\s*uvedl:\s*",
    ):
        text = re.sub(prefix, "", text, count=1, flags=re.I)
    lp = (f.get("link_phrase") or "").strip()
    cit = (f.get("citace") or "").strip()
    for cand in (text, lp, cit):
        if cand and len(cand) >= 12 and not ANCHOR_SKIP.match(cand):
            return cand
    return text or lp or cit


def weak_citace(cit: str) -> bool:
    c = (cit or "").strip()
    if not c:
        return True
    if is_vote_summary(c):
        return True
    if len(c) < 40 and GREETING_ONLY.match(c):
        return True
    return bool(GREETING_RE.search(c) and len(c) < 55)


def pick_excerpt(anchor: str, steno: dict[str, dict], prefer_sid: str) -> tuple[str, str] | None:
    if prefer_sid and prefer_sid in steno:
        hit = find_excerpt(anchor, steno[prefer_sid].get("text", ""))
        if hit:
            return prefer_sid, hit
    for sid, rec in steno.items():
        hit = find_excerpt(anchor, rec.get("text", ""))
        if hit:
            return sid, hit
    cit = anchor
    for sid in find_correct_ids(steno, cit):
        rec = steno[sid]
        hit = find_excerpt(anchor, rec.get("text", "")) or cit
        if citace_in_text(hit, rec.get("text", "")):
            return sid, hit
    return None


def group_needs_fix(refs: list[dict]) -> bool:
    cits = [r["fact"].get("citace", "").strip() for r in refs]
    if any(cits.count(c) > 1 for c in set(cits) if c):
        return True
    return any(weak_citace(c) for c in cits)


def fix_group(refs: list[dict], steno: dict[str, dict]) -> list[str]:
    changes: list[str] = []
    used_cits: set[str] = set()
    for r in sorted(refs, key=lambda x: (x["slug"], x["i"])):
        f = r["fact"]
        cit = (f.get("citace") or "").strip()
        sid = (f.get("steno_id") or "").strip()
        if not group_needs_fix(refs):
            continue
        dup = cit in used_cits if cit else False
        if not dup and not weak_citace(cit) and citace_in_text(cit, steno.get(sid, {}).get("text", "")):
            used_cits.add(cit)
            continue
        anchor = anchor_from_fact(f)
        picked = pick_excerpt(anchor, steno, sid)
        if picked:
            new_sid, new_cit = picked
            new_cit = new_cit.strip()
            if new_cit and (new_cit != cit or new_sid != sid) and new_cit not in used_cits:
                f["steno_id"] = new_sid
                f["citace"] = new_cit
                f["source"] = "steno"
                used_cits.add(new_cit)
                changes.append(f"{r['slug']}[{r['i']}] excerpt")
                continue
        if dup or weak_citace(cit):
            strip_steno_fields(f)
            changes.append(f"{r['slug']}[{r['i']}] strip")
    return changes


def main() -> int:
    dry = "--dry-run" in sys.argv
    approved = json.loads(APPROVED_PATH.read_text(encoding="utf-8")).get("approved") or []
    files = 0
    changes: list[str] = []

    for key in approved:
        ob, sch, iso, _ = parse_key(key)
        base = ROOT / f"processed/{ob}-s{sch}"
        steno = steno_by_id(base / "raw/steno.jsonl")
        day = json.loads((base / "facts/by_day" / f"{iso}.json").read_text())
        by_sid: dict[str, list[dict]] = defaultdict(list)
        topics: dict[str, dict] = {}

        for slug in day.get("topic_slugs") or []:
            fp = base / "facts/by_topic" / f"{slug}.json"
            if not fp.is_file():
                continue
            topic = json.loads(fp.read_text())
            if not topic.get("publikovat"):
                continue
            topics[slug] = topic
            for i, f in enumerate(topic.get("fakty") or []):
                if not isinstance(f, dict):
                    continue
                sid = (f.get("steno_id") or "").strip()
                if sid:
                    by_sid[sid].append({"slug": slug, "i": i, "fact": f})

        day_changes: list[str] = []
        for sid, refs in by_sid.items():
            if len(refs) < 2 or not group_needs_fix(refs):
                continue
            day_changes.extend(fix_group(refs, steno))

        if not day_changes:
            continue
        files += 1
        changes.extend(f"{key}: {c}" for c in day_changes)
        if not dry:
            for slug, topic in topics.items():
                fp = base / "facts/by_topic" / f"{slug}.json"
                fp.write_text(
                    json.dumps(topic, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )

    print(f"files {files}, changes {len(changes)}, dry={dry}")
    for line in changes[:50]:
        print(line)
    if len(changes) > 50:
        print(f"... +{len(changes) - 50}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
