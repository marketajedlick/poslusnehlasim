#!/usr/bin/env python3
"""Doplní link_phrase ve facts tam, kde steno stránka postrádá „Přesné znění z článku“."""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APPROVED_PATH = ROOT / "processed/publish-approved.json"
REPORT_PATH = ROOT / "grammer_check/steno-link-phrase-report.json"

sys.path.insert(0, str(ROOT))

from svejk.build.steno_sources import (  # noqa: E402
    StenoPassage,
    _find_phrase_in_text,
    _speaker_clause,
    collect_steno_sources,
    link_phrase_for_passage,
)
from svejk.paths import SchuzePaths  # noqa: E402

# ponytail: ruční záplaty jen tam, kde auto nenajde frázi v článku
MANUAL: dict[str, dict[int, str]] = {
    "novela-z-o-jednacim-radu-ps": {
        5: "počet faktických poznámek zůstává neomezený",
        6: "3 proti 84",
        7: "šestadvaceti pozměňovacích návrzích",
        8: "sjetina zaznamenala jeho hlas obráceně",
        9: "stejný problém o dvě hlasování dál",
        10: "110 ku 12",
    },
}


def parse_key(key: str) -> tuple[int, int, str, str]:
    obdobi_s, schuze_s, datum_cz = key.split("/", 2)
    iso = datetime.strptime(datum_cz.strip(), "%d.%m.%Y").strftime("%Y-%m-%d")
    return int(obdobi_s), int(schuze_s), iso, datum_cz.strip()


def article_text(data: dict) -> str:
    parts: list[str] = []
    for key in ("lead", "pointa", "mean", "kuriozita", "citace_text"):
        val = (data.get(key) or "").strip()
        if val:
            parts.append(val)
    return " ".join(parts)


def party_clause(speaker: str, article: str) -> str | None:
    surname = (speaker or "").split()[-1] if speaker else ""
    if len(surname) < 3:
        return None
    pat = re.compile(
        rf"\b{re.escape(surname)}\s*\([^)]+\)[^,.]*",
        re.IGNORECASE,
    )
    matches = [m.group(0).strip() for m in pat.finditer(article)]
    if not matches:
        return None
    return max(matches, key=len)


def summary_phrases(summary: str) -> list[str]:
    words = (summary or "").split()
    out: list[str] = []
    for length in range(min(14, len(words)), 2, -1):
        for start in range(len(words) - length + 1):
            phrase = " ".join(words[start : start + length])
            if len(phrase) >= 8:
                out.append(phrase)
    return out


def suggest_link_phrase(
    *,
    article: str,
    summary: str,
    citace: str,
    speaker: str,
    steno_id: str,
    steno_by_id: dict[str, dict],
    existing: str,
) -> str | None:
    if existing and _find_phrase_in_text(article, existing):
        return existing

    rec = steno_by_id.get(steno_id) or {}
    passage = StenoPassage(
        steno_id=steno_id,
        anchor=f"steno-{steno_id}",
        speaker=speaker or rec.get("cele_jmeno") or "",
        poradi=rec.get("poradi"),
        topic_slug="",
        topic_title="",
        article_num=1,
        summary=summary,
        citace=citace,
        excerpt=citace,
        psp_url="",
        source="steno",
        link_phrase=existing,
    )
    for fn in (
        lambda: link_phrase_for_passage(passage, article),
        lambda: party_clause(speaker or rec.get("cele_jmeno") or "", article),
        lambda: _speaker_clause(speaker or rec.get("cele_jmeno") or "", article),
    ):
        hit = fn()
        if hit and _find_phrase_in_text(article, hit):
            return hit

    for phrase in summary_phrases(summary):
        if _find_phrase_in_text(article, phrase):
            return phrase

    flat = re.sub(r"\s+", " ", (citace or "").strip())
    for n in (min(50, len(flat)), 40, 30, 20):
        if n < 10:
            continue
        chunk = flat[:n].strip()
        if chunk and _find_phrase_in_text(article, chunk):
            return chunk
    return None


def load_steno_index(paths: SchuzePaths) -> dict[str, dict]:
    p = paths.steno_jsonl
    if not p.is_file():
        refs = paths.aligned / "steno_refs.json"
        if refs.is_file():
            return json.loads(refs.read_text(encoding="utf-8"))
        return {}
    out: dict[str, dict] = {}
    for line in p.open(encoding="utf-8"):
        r = json.loads(line)
        if r.get("id"):
            out[r["id"]] = r
    return out


def fix_topic(slug: str, data: dict, steno_by_id: dict[str, dict]) -> list[str]:
    article = article_text(data)
    changes: list[str] = []
    manual = MANUAL.get(slug) or {}
    for i, f in enumerate(data.get("fakty") or []):
        if not isinstance(f, dict):
            continue
        summary = (f.get("text") or "").strip()
        cit = (f.get("citace") or "").strip()
        sid = (f.get("steno_id") or "").strip()
        speaker = (steno_by_id.get(sid) or {}).get("cele_jmeno") or ""
        existing = (f.get("link_phrase") or "").strip()

        phrase: str | None = None
        if i in manual:
            phrase = manual[i]
            if not _find_phrase_in_text(article, phrase):
                extra = summary.rstrip(".")
                pointa = (data.get("pointa") or "").strip()
                if phrase not in pointa and extra and extra not in pointa:
                    data["pointa"] = f"{pointa} {extra}." if pointa else f"{extra}."
                    article = article_text(data)
                if not _find_phrase_in_text(article, phrase):
                    changes.append(f"MANUAL_MISS {slug}[{i}] {phrase!r}")
                    continue
        elif existing and _find_phrase_in_text(article, existing):
            phrase = existing
        elif sid and cit:
            phrase = suggest_link_phrase(
                article=article,
                summary=summary,
                citace=cit,
                speaker=speaker,
                steno_id=sid,
                steno_by_id=steno_by_id,
                existing=existing,
            )
        elif summary:
            for cand in summary_phrases(summary):
                if _find_phrase_in_text(article, cand):
                    phrase = cand
                    break

        if not phrase:
            continue
        if phrase != existing:
            f["link_phrase"] = phrase
            changes.append(f"SET {slug}[{i}] {phrase!r}")
    return changes


def audit_remaining() -> list[dict]:
    from svejk.build.steno_sources import collect_steno_sources

    remaining: list[dict] = []
    approved = json.loads(APPROVED_PATH.read_text(encoding="utf-8")).get("approved") or []
    for key in approved:
        obdobi, schuze, iso, datum_unl = parse_key(key)
        paths = SchuzePaths.create(obdobi, schuze)
        day_path = paths.facts_by_day / f"{iso}.json"
        if not day_path.is_file():
            continue
        day = json.loads(day_path.read_text(encoding="utf-8"))
        if not day.get("steno_zdroje"):
            continue
        for block in collect_steno_sources(paths, datum_unl):
            for p in block.passages:
                if p.anchor.startswith("vote-"):
                    miss = []
                    if not (p.article_phrase or "").strip():
                        miss.append("article_phrase")
                    if not (p.summary or "").strip():
                        miss.append("summary")
                    if miss:
                        remaining.append(
                            {
                                "day": key,
                                "slug": block.slug,
                                "anchor": p.anchor,
                                "speaker": p.speaker,
                                "missing": miss,
                                "summary": p.summary[:120],
                            }
                        )
                    continue
                miss = []
                if not (p.article_phrase or "").strip():
                    miss.append("article_phrase")
                if not (p.summary or "").strip():
                    miss.append("summary")
                if not (p.citace or "").strip():
                    miss.append("citace")
                if not (p.excerpt or "").strip() or p.excerpt.strip() == (p.citace or "").strip():
                    miss.append("excerpt")
                if not (p.speaker or "").strip():
                    miss.append("speaker")
                if p.poradi is None:
                    miss.append("poradi")
                if not (p.psp_url or "").strip():
                    miss.append("psp_url")
                if miss:
                    remaining.append(
                        {
                            "day": key,
                            "slug": block.slug,
                            "anchor": p.anchor,
                            "speaker": p.speaker,
                            "missing": miss,
                            "summary": p.summary[:120],
                            "link_phrase": p.link_phrase,
                        }
                    )
    return remaining


def main() -> int:
    dry = "--dry-run" in sys.argv
    only_s24 = "--s24" in sys.argv
    approved = json.loads(APPROVED_PATH.read_text(encoding="utf-8")).get("approved") or []
    steno_cache: dict[int, dict[str, dict]] = {}
    all_changes: list[str] = []
    files_changed = 0

    for key in approved:
        obdobi, schuze, iso, _ = parse_key(key)
        if only_s24 and schuze != 24:
            continue
        paths = SchuzePaths.create(obdobi, schuze)
        day_path = paths.facts_by_day / f"{iso}.json"
        if not day_path.is_file():
            continue
        day = json.loads(day_path.read_text(encoding="utf-8"))
        if not day.get("steno_zdroje"):
            continue
        if schuze not in steno_cache:
            steno_cache[schuze] = load_steno_index(paths)
        steno_by_id = steno_cache[schuze]
        topic_dir = paths.facts_by_topic
        for slug in day.get("topic_slugs") or []:
            tpath = topic_dir / f"{slug}.json"
            if not tpath.is_file():
                continue
            before = tpath.read_text(encoding="utf-8")
            data = json.loads(before)
            if data.get("publikovat") is False:
                continue
            changes = fix_topic(slug, data, steno_by_id)
            if not changes:
                continue
            all_changes.extend(changes)
            if not dry:
                after = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
                if after != before:
                    tpath.write_text(after, encoding="utf-8")
                    files_changed += 1

    remaining = audit_remaining() if not dry else []
    if not dry:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(
            json.dumps({"changes": all_changes, "remaining": remaining}, ensure_ascii=False, indent=2)
            + "\n",
            encoding="utf-8",
        )

    print(f"{'DRY ' if dry else ''}Changes: {len(all_changes)}, files: {files_changed}")
    for line in all_changes[:40]:
        print(line)
    if len(all_changes) > 40:
        print(f"... and {len(all_changes) - 40} more")
    if not dry:
        steno_left = [r for r in remaining if not r["anchor"].startswith("vote-")]
        vote_left = [r for r in remaining if r["anchor"].startswith("vote-")]
        print(f"\nRemaining incomplete: steno={len(steno_left)} vote={len(vote_left)}")
        print(f"Report: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
