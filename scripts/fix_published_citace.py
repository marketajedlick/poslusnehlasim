#!/usr/bin/env python3
"""Oprava faktů s neplatnou citací: hlasování bez stena, řeč doslovně nebo bez citace."""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APPROVED_PATH = ROOT / "processed/publish-approved.json"

VOTE_CIT_RE = re.compile(
    r"^(Hlasování|hlasování|V hlasování|\d+ hlasování)",
    re.IGNORECASE,
)


def norm(s: str) -> str:
    s = (s or "").strip()
    for old, new in (("„", '"'), (""", '"'), (""", '"')):
        s = s.replace(old, new)
    return re.sub(r"\s+", " ", s).lower()


def norm_relaxed(s: str) -> str:
    return re.sub(r"[^\w\s]", "", norm(s))


def sanitize_dashes(s: str) -> str:
    return (s or "").replace("—", ", ").replace("–", ", ")


def is_vote_summary(cit: str) -> bool:
    c = (cit or "").strip()
    if not c:
        return False
    if VOTE_CIT_RE.search(c):
        return True
    if c.startswith("(") and c.endswith(")") and "potlesk" in c.lower():
        return True
    return False


def words_relaxed(s: str) -> list[str]:
    return [w for w in norm_relaxed(s).split() if len(w) >= 2]


def find_word_span(cit: str, text: str) -> tuple[int, int] | None:
    """Najde pozici nejdelší shody slov z citace v textu stena."""
    cw = words_relaxed(cit)
    if len(cw) < 3:
        return None
    tw = re.findall(r"\S+", text)
    tw_norm = [norm_relaxed(w) for w in tw]
    best: tuple[int, int, int] | None = None
    for length in range(min(len(cw), 24), 2, -1):
        for start in range(len(cw) - length + 1):
            chunk = cw[start : start + length]
            for i in range(len(tw_norm) - length + 1):
                if tw_norm[i : i + length] == chunk:
                    if best is None or length > best[2]:
                        best = (i, i + length, length)
        if best:
            break
    if not best:
        return None
    i, j, _ = best
    start_char = sum(len(tw[k]) + 1 for k in range(i))
    end_char = sum(len(tw[k]) + 1 for k in range(j)) - 1
    return start_char, end_char


def excerpt_from_span(text: str, span: tuple[int, int], max_words: int = 28) -> str:
    start, end = span
    chunk = text[start : end + 1].strip()
    # rozšířit do konce věty nebo max_words
    tail = text[end + 1 :]
    m = re.search(r"[.!?]\s", tail)
    if m and len(chunk.split()) < max_words:
        chunk = (chunk + tail[: m.end()]).strip()
    words = chunk.split()
    if len(words) > max_words:
        chunk = " ".join(words[:max_words])
    return sanitize_dashes(re.sub(r"\s+", " ", chunk))


def citace_in_text(cit: str, text: str) -> bool:
    if not cit or not text:
        return False
    if norm(cit).strip('"') in norm(text):
        return True
    nr = norm_relaxed(cit)
    if len(nr) >= 12 and nr in norm_relaxed(text):
        return True
    for n in (80, 60, 40, 24):
        ch = nr[:n].strip()
        if len(ch) >= 14 and ch in norm_relaxed(text):
            return True
    return False


def find_excerpt(cit: str, text: str) -> str | None:
    if citace_in_text(cit, text):
        span = find_word_span(cit, text)
        if span:
            return excerpt_from_span(text, span)
        flat = re.sub(r"\s+", " ", cit.strip())
        return sanitize_dashes(flat)
    span = find_word_span(cit, text)
    if span and span[1] - span[0] >= 3:
        return excerpt_from_span(text, span)
    return None


def strip_steno_fields(f: dict) -> None:
    f.pop("steno_id", None)
    f.pop("link_phrase", None)
    if f.get("source") == "steno":
        f.pop("source", None)


def fix_fact(f: dict, steno_rows: list[dict], steno_by_id: dict[str, dict]) -> str | None:
    """Vrátí typ změny nebo None."""
    cit = (f.get("citace") or "").strip()
    if not cit:
        if f.get("source") == "steno" and not f.get("steno_id"):
            strip_steno_fields(f)
            return "orphan_source"
        return None

    if is_vote_summary(cit):
        f.pop("citace", None)
        strip_steno_fields(f)
        return "vote_strip"

    sid = (f.get("steno_id") or "").strip()
    if sid and sid in steno_by_id:
        text = steno_by_id[sid].get("text", "")
        excerpt = find_excerpt(cit, text)
        if excerpt:
            f["citace"] = excerpt
            f["source"] = "steno"
            f["steno_id"] = sid
            return "fix_sid"
        f.pop("citace", None)
        if not (f.get("link_phrase") or "").strip():
            strip_steno_fields(f)
        return "drop_bad_sid"

    for r in steno_rows:
        excerpt = find_excerpt(cit, r.get("text", ""))
        if excerpt:
            f["steno_id"] = r["id"]
            f["citace"] = excerpt
            f["source"] = "steno"
            return "fix_search"
        # u velmi volné shody stačí 5+ slov
        span = find_word_span(cit, r.get("text", ""))
        if span and span[1] - span[0] >= 5:
            f["steno_id"] = r["id"]
            f["citace"] = excerpt_from_span(r["text"], span)
            f["source"] = "steno"
            return "fix_search"

    f.pop("citace", None)
    strip_steno_fields(f)
    return "drop_parafraze"


def fix_citace_text(data: dict, steno_rows: list[dict], steno_by_id: dict[str, dict]) -> str | None:
    ct = (data.get("citace_text") or "").strip()
    if not ct:
        return None
    sid = (data.get("steno_id") or "").strip()
    if sid and sid in steno_by_id:
        text = steno_by_id[sid].get("text", "")
        excerpt = find_excerpt(ct, text)
        if excerpt and excerpt != ct:
            data["citace_text"] = excerpt
            return "citace_text_fix"
        if citace_in_text(ct, text):
            return None
    for r in steno_rows:
        excerpt = find_excerpt(ct, r.get("text", ""))
        if excerpt:
            data["steno_id"] = r["id"]
            data["citace_text"] = excerpt
            return "citace_text_fix"
    return None


def parse_key(key: str) -> tuple[int, int, str, str]:
    ob, sc, dz = key.split("/", 2)
    iso = datetime.strptime(dz.strip(), "%d.%m.%Y").strftime("%Y-%m-%d")
    return int(ob), int(sc), iso, dz


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


def main() -> int:
    dry = "--dry-run" in sys.argv
    approved = json.loads(APPROVED_PATH.read_text(encoding="utf-8")).get("approved") or []
    steno_loaded: dict[int, tuple[list[dict], dict[str, dict]]] = {}
    stats: dict[str, int] = {}
    changed_files = 0
    changed_days: set[tuple[int, int, str]] = set()

    for key in approved:
        obdobi, schuze, iso, datum_cz = parse_key(key)
        base = ROOT / f"processed/{obdobi}-s{schuze}"
        day_path = base / "facts/by_day" / f"{iso}.json"
        if not day_path.is_file():
            continue
        if schuze not in steno_loaded:
            steno_loaded[schuze] = load_steno(base / "raw/steno.jsonl")
        steno_rows, steno_by_id = steno_loaded[schuze]
        day = json.loads(day_path.read_text(encoding="utf-8"))

        for slug in day.get("topic_slugs") or []:
            tpath = base / "facts/by_topic" / f"{slug}.json"
            if not tpath.is_file():
                continue
            before = tpath.read_text(encoding="utf-8")
            data = json.loads(before)
            if data.get("publikovat") is False:
                continue
            touched = False
            for f in data.get("fakty") or []:
                if not isinstance(f, dict):
                    continue
                action = fix_fact(f, steno_rows, steno_by_id)
                if action:
                    stats[action] = stats.get(action, 0) + 1
                    touched = True
            action = fix_citace_text(data, steno_rows, steno_by_id)
            if action:
                stats[action] = stats.get(action, 0) + 1
                touched = True
            if not touched:
                continue
            after = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
            if after == before:
                continue
            changed_files += 1
            changed_days.add((obdobi, schuze, datum_cz))
            if not dry:
                tpath.write_text(after, encoding="utf-8")

    print(f"{'DRY ' if dry else ''}Updated {changed_files} files, {len(changed_days)} days")
    for k, v in sorted(stats.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")
    for obdobi, schuze, datum_cz in sorted(changed_days, key=lambda x: (x[1], x[2])):
        print(f"  {obdobi}/s{schuze}/{datum_cz}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
