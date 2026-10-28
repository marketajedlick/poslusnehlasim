#!/usr/bin/env python3
"""Odstraní surové kotvy ze mean/pointa a přesměruje link_phrase do existujícího textu článku."""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APPROVED_PATH = ROOT / "processed/publish-approved.json"
REPORT_PATH = ROOT / "grammer_check/steno-append-cleanup.json"

sys.path.insert(0, str(ROOT))

from svejk.build.steno_sources import _find_phrase_in_text, collect_steno_sources  # noqa: E402
from svejk.paths import SchuzePaths  # noqa: E402

_LC_TAIL = re.compile(
    r"^(.*?)(?:\.\s+|\n\n)([a-záčďéěíňóřšťúůýž][^.!?]*(?:[.!?][^.!?]*)*)\.?\s*$",
    re.DOTALL,
)


def parse_key(key: str) -> tuple[int, int, str, str]:
    obdobi_s, schuze_s, datum_cz = key.split("/", 2)
    iso = datetime.strptime(datum_cz.strip(), "%d.%m.%Y").strftime("%Y-%m-%d")
    return int(obdobi_s), int(schuze_s), iso, datum_cz.strip()


def article_text(data: dict) -> str:
    parts: list[str] = []
    for key in ("lead", "pointa", "mean", "kuriozita", "citace_text"):
        val = (data.get(key) or "").strip()
        if val:
            parts.append(re.sub(r"<[^>]+>", " ", val))
    return " ".join(parts)


def strip_trailing(body: str, phrase: str) -> str | None:
    p = phrase.strip().rstrip(".")
    if not p or p not in body:
        return None
    for suffix in (f" {p}.", f". {p}.", f" {p}", f". {p}"):
        if body.endswith(suffix):
            return body[: -len(suffix)].rstrip()
    return None


def best_link_in(text: str, phrase: str, summary: str) -> str | None:
    if _find_phrase_in_text(text, phrase):
        return phrase
    for cand in (phrase, summary.strip().rstrip(".")):
        if not cand:
            continue
        hit = _find_phrase_in_text(text, cand)
        if hit:
            return hit
    words = phrase.split()
    for n in range(min(len(words), 12), 2, -1):
        chunk = " ".join(words[:n])
        if len(chunk) >= 8 and _find_phrase_in_text(text, chunk):
            return chunk
    return None


def phrases_ok(data: dict) -> bool:
    art = article_text(data)
    for f in data.get("fakty") or []:
        if not isinstance(f, dict):
            continue
        lp = (f.get("link_phrase") or "").strip()
        if lp and not _find_phrase_in_text(art, lp):
            return False
    return True


def relocate_links(data: dict, slug: str, changes: list[str]) -> None:
    art = article_text(data)
    for f in data.get("fakty") or []:
        if not isinstance(f, dict):
            continue
        lp = (f.get("link_phrase") or "").strip()
        if not lp or _find_phrase_in_text(art, lp):
            continue
        alt = best_link_in(art, lp, f.get("text") or "")
        if alt:
            f["link_phrase"] = alt
            changes.append(f"LINK {slug} {alt!r}")


def strip_phrase_appends(data: dict, slug: str, changes: list[str]) -> None:
    phrases = [
        (f.get("link_phrase") or "").strip()
        for f in data.get("fakty") or []
        if isinstance(f, dict)
    ]
    phrases = sorted({p for p in phrases if len(p) >= 8}, key=len, reverse=True)
    for field in ("pointa", "mean"):
        body = (data.get(field) or "").strip()
        if not body:
            continue
        for phrase in phrases:
            while True:
                new_body = strip_trailing(body, phrase)
                if not new_body or new_body == body:
                    break
                trial = dict(data)
                trial[field] = new_body
                if not phrases_ok(trial):
                    break
                data[field] = new_body
                body = new_body
                changes.append(f"STRIP {slug}/{field} {phrase[:45]!r}")


def strip_lowercase_tails(data: dict, slug: str, changes: list[str]) -> None:
    phrases = {
        (f.get("link_phrase") or "").strip().rstrip(".")
        for f in data.get("fakty") or []
        if isinstance(f, dict)
    }
    phrases = {p for p in phrases if len(p) >= 8}
    for field in ("pointa", "mean"):
        body = (data.get(field) or "").strip()
        if not body:
            continue
        while True:
            m = _LC_TAIL.match(body)
            if not m:
                break
            head, tail = m.group(1).strip(), m.group(2).strip().rstrip(".")
            if len(tail) < 8:
                break
            if not any(tail == p or tail.startswith(p) or p.startswith(tail) for p in phrases):
                break
            trial = dict(data)
            trial[field] = head + ("." if head and not head.endswith(".") else "")
            if not phrases_ok(trial):
                break
            data[field] = trial[field]
            body = data[field]
            changes.append(f"STRIP_LC {slug}/{field} {tail[:45]!r}")


def strip_vote_and_duplicate_tails(data: dict, slug: str, changes: list[str]) -> None:
    for field in ("pointa", "mean"):
        body = (data.get(field) or "").strip()
        if not body:
            continue
        for f in data.get("fakty") or []:
            if not isinstance(f, dict):
                continue
            lp = (f.get("link_phrase") or "").strip()
            if len(lp) < 8:
                continue
            for cut in (lp, lp[: min(len(lp), 60)], lp[: min(len(lp), 45)]):
                new_body = strip_trailing(body, cut)
                if not new_body or new_body == body:
                    continue
                trial = dict(data)
                trial[field] = new_body
                relocate_links(trial, slug, [])
                if phrases_ok(trial):
                    data[field] = new_body
                    body = new_body
                    changes.append(f"STRIP_TAIL {slug}/{field} {cut[:45]!r}")
                    break


def cleanup_topic(slug: str, data: dict) -> list[str]:
    changes: list[str] = []
    strip_phrase_appends(data, slug, changes)
    strip_vote_and_duplicate_tails(data, slug, changes)
    strip_lowercase_tails(data, slug, changes)
    relocate_links(data, slug, changes)
    return changes


def audit_steno_left() -> int:
    remaining = 0
    approved = json.loads(APPROVED_PATH.read_text(encoding="utf-8")).get("approved") or []
    for key in approved:
        ob, sch, iso, cz = parse_key(key)
        paths = SchuzePaths.create(ob, sch)
        day_path = paths.facts_by_day / f"{iso}.json"
        if not day_path.is_file():
            continue
        day = json.loads(day_path.read_text(encoding="utf-8"))
        if not day.get("steno_zdroje"):
            continue
        for block in collect_steno_sources(paths, cz):
            for p in block.passages:
                if p.anchor.startswith("vote-"):
                    continue
                if not (p.article_phrase or "").strip():
                    remaining += 1
    return remaining


def main() -> int:
    dry = "--dry-run" in sys.argv
    approved = json.loads(APPROVED_PATH.read_text(encoding="utf-8")).get("approved") or []
    all_changes: list[str] = []
    files_changed = 0

    for key in approved:
        ob, sch, iso, _ = parse_key(key)
        paths = SchuzePaths.create(ob, sch)
        day_path = paths.facts_by_day / f"{iso}.json"
        if not day_path.is_file():
            continue
        day = json.loads(day_path.read_text(encoding="utf-8"))
        if not day.get("steno_zdroje"):
            continue
        for slug in day.get("topic_slugs") or []:
            fp = paths.facts_by_topic / f"{slug}.json"
            if not fp.is_file():
                continue
            before = fp.read_text(encoding="utf-8")
            data = json.loads(before)
            if not data.get("publikovat"):
                continue
            changes = cleanup_topic(slug, data)
            if not changes:
                continue
            all_changes.extend(changes)
            if not dry:
                after = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
                if after != before:
                    fp.write_text(after, encoding="utf-8")
                    files_changed += 1

    if not dry:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(
            json.dumps({"changes": all_changes}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Files changed: {files_changed}, changes: {len(all_changes)}, steno_incomplete: {audit_steno_left()}")
    else:
        print(f"DRY changes: {len(all_changes)}")
    for line in all_changes[:60]:
        print(line)
    if len(all_changes) > 60:
        print(f"... and {len(all_changes) - 60} more")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
