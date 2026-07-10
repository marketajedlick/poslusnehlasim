#!/usr/bin/env python3
"""Opraví fakt_speaker_mismatch: předpona řečníka, scene bez steno_id, špatný steno_id."""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_published_steno import citace_in_text, find_correct_ids, steno_by_id  # noqa: E402
from scripts.audit_published_text import cit_in_steno, load_approved  # noqa: E402

FIRST_WORD = re.compile(r"^([A-ZÁČĎÉĚÍŇÓŘŠŤÚÝŽ][a-záčďéěíňóřšťúýž]+)")
PROCEDURAL = re.compile(r"^(Hlasování|Konstatuji|Prosím|Další|Návrh na|Pořad|Volba|Tajnou)\b", re.I)
SCENE_START = re.compile(r"^(Hluk|Potlesk|Bouřlivý|Smích|Poslanec\s+\w+\s+přistupuje)", re.I)
BAD_SPEAKER = re.compile(r"^\d+$")


def speaker_short(cele_jmeno: str) -> str:
    j = re.sub(r"^ČR\s+", "", (cele_jmeno or "").strip())
    if not j or BAD_SPEAKER.match(j):
        return ""
    parts = j.split()
    return parts[-1] if parts else ""


def lcfirst(s: str) -> str:
    return s[0].lower() + s[1:] if s else s


def already_attributed(text: str, cele_jmeno: str) -> bool:
    fw = FIRST_WORD.match(text.strip())
    if not fw:
        return True
    word = fw.group(1)
    cj = cele_jmeno or ""
    if word in cj:
        return True
    short = speaker_short(cj)
    if short and (text.startswith(short + ":") or text.startswith(short + " ")):
        return True
    return False


def pick_speaker_id(cit: str, steno: dict[str, dict], prefer: str = "") -> str | None:
    hits = find_correct_ids(steno, cit)
    if not hits:
        return None
    if prefer:
        for sid in hits:
            if prefer in (steno[sid].get("cele_jmeno") or ""):
                return sid
    return hits[0]


def fix_fact(f: dict, rec: dict, steno: dict[str, dict]) -> str | None:
    ft = (f.get("text") or "").strip()
    cit = (f.get("citace") or "").strip()
    if not ft or not cit:
        return None

    cj = (rec.get("cele_jmeno") or "").strip()
    if not already_attributed(ft, cj) and (f.get("kind") == "scene" or SCENE_START.match(ft)):
        f.pop("steno_id", None)
        f.pop("source", None)
        return "scene_unlink"

    if not speaker_short(cj):
        prefer = FIRST_WORD.match(ft)
        prefer_name = prefer.group(1) if prefer else ""
        alt = pick_speaker_id(cit, steno, prefer_name)
        if alt and alt != f.get("steno_id"):
            f["steno_id"] = alt
            rec = steno[alt]
            cj = rec.get("cele_jmeno") or ""
        if not speaker_short(cj):
            return None

    if already_attributed(ft, cj):
        return None

    short = speaker_short(cj)
    if PROCEDURAL.match(ft):
        f["text"] = f"{short} řekl: {ft}"
        return "prefix_procedural"
    if cit.lower() not in ft.lower() and len(ft) > 24:
        f["text"] = f"{short} uvedl, že {lcfirst(ft)}"
        return "prefix_editorial"
    f["text"] = f"{short}: {ft}"
    return "prefix_colon"


def audit_mismatches(topic: dict, steno: dict[str, dict]) -> list[tuple[int, dict, dict]]:
    out: list[tuple[int, dict, dict]] = []
    for i, f in enumerate(topic.get("fakty") or []):
        if not isinstance(f, dict):
            continue
        cit = (f.get("citace") or "").strip()
        sid = (f.get("steno_id") or "").strip()
        ft = (f.get("text") or "").strip()
        if not cit or not sid or not ft:
            continue
        rec = steno.get(sid)
        if not rec or not cit_in_steno(cit, rec.get("text", "")):
            continue
        cj = rec.get("cele_jmeno") or ""
        m = FIRST_WORD.match(ft)
        if m and m.group(1) not in cj and not already_attributed(ft, cj):
            out.append((i, f, rec))
    return out


def main() -> int:
    dry = "--dry-run" in sys.argv
    files = 0
    fixes = 0
    for ob, sch, iso, key in load_approved():
        base = ROOT / f"processed/{ob}-s{sch}"
        steno_path = base / "raw/steno.jsonl"
        steno = steno_by_id(steno_path)
        for fp in sorted((base / "facts/by_topic").glob("*.json")):
            data = json.loads(fp.read_text(encoding="utf-8"))
            if not data.get("publikovat"):
                continue
            mism = audit_mismatches(data, steno)
            if not mism:
                continue
            ch: list[str] = []
            for i, f, rec in mism:
                kind = fix_fact(f, rec, steno)
                if kind:
                    ch.append(f"[{i}] {kind}")
            if not ch:
                continue
            files += 1
            fixes += len(ch)
            print(fp.stem, ch[:5])
            if not dry:
                fp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"files {files}, fixes {fixes}, dry={dry}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
