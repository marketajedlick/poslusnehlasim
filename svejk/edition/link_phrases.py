"""Automatické doplnění link_phrase ve facts (přesun z fix_steno_link_phrases.py)."""

from __future__ import annotations

import json
import re
from typing import Any

from svejk.build.io import read_json, write_json
from svejk.build.steno_sources import (
    StenoPassage,
    _excerpt_around,
    _find_phrase_in_text,
    _speaker_clause,
    link_phrase_for_passage,
)
from svejk.edition.dates import resolve_edition_day
from svejk.edition.state import assert_editable, load_edition
from svejk.paths import SchuzePaths

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


def article_text(data: dict) -> str:
    parts: list[str] = []
    for key in ("lead", "pointa", "pointa_tail", "mean", "kuriozita", "citace_text"):
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


def _norm_ws(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def anchor_phrase(summary: str) -> str:
    s = (summary or "").strip().rstrip(".")
    if not s:
        return ""
    if ": " in s:
        tail = s.split(": ", 1)[1].strip()
        if 10 <= len(tail) <= 72:
            return tail
    words = s.split()
    if len(words) <= 10:
        return s
    return " ".join(words[:10])


def ensure_phrase_in_article(data: dict, phrase: str, summary: str = "") -> bool:
    if _find_phrase_in_text(article_text(data), phrase):
        return True
    phrase = phrase.strip().rstrip(".")
    if not phrase or len(phrase) < 8:
        return False
    body = (data.get("mean") or "").strip()
    sent = summary.strip().rstrip(".") if summary else phrase
    if sent and sent[0].islower():
        sent = sent[0].upper() + sent[1:]
    data["mean"] = f"{body} {sent}." if body else f"{sent}."
    return _find_phrase_in_text(article_text(data), phrase) is not None


def excerpt_needs_fix(full_text: str, citace: str) -> bool:
    if not full_text or not citace:
        return bool(full_text and not citace)
    ex = _norm_ws(_excerpt_around(full_text, citace))
    cit = _norm_ws(citace)
    return not ex or ex == cit or len(ex) <= len(cit) + 15


def fix_citace_from_steno(full_text: str, summary: str, citace: str) -> str | None:
    flat = _norm_ws(full_text)
    if not flat:
        return None
    if citace and not excerpt_needs_fix(full_text, citace):
        return None
    words = re.sub(r"[.:,;!?()]", " ", summary or "").split()
    words = [w for w in words if len(w) > 2]
    for length in range(min(16, len(words)), 3, -1):
        for start in range(0, len(words) - length + 1):
            needle = " ".join(words[start : start + length])
            if len(needle) < 12:
                continue
            pos = flat.lower().find(needle.lower())
            if pos < 0:
                continue
            end = min(len(flat), pos + max(len(needle) + 60, 90))
            chunk = flat[pos:end].strip()
            if len(chunk) > 140:
                chunk = chunk[:140].rsplit(" ", 1)[0]
            if len(chunk) >= 16:
                return chunk
    if citace:
        flat_cit = _norm_ws(citace)
        for n in (min(50, len(flat_cit)), 40, 30, 20):
            if n < 10:
                continue
            pos = flat.lower().find(flat_cit[:n].lower())
            if pos >= 0:
                end = min(len(flat), pos + 120)
                return flat[pos:end].strip()
    return None


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
        full_text = (steno_by_id.get(sid) or {}).get("text") or ""

        new_cit = fix_citace_from_steno(full_text, summary, cit) if sid and full_text else None
        if new_cit and new_cit != cit:
            f["citace"] = new_cit
            cit = new_cit
            changes.append(f"CITACE {slug}[{i}]")

        phrase: str | None = None
        if i in manual:
            phrase = manual[i]
            if not _find_phrase_in_text(article, phrase):
                if not ensure_phrase_in_article(data, phrase):
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
        elif sid:
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

        if not phrase and summary:
            phrase = anchor_phrase(summary)
            if phrase and not ensure_phrase_in_article(data, phrase, summary):
                phrase = None
            else:
                article = article_text(data)
        elif phrase and not _find_phrase_in_text(article, phrase):
            if ensure_phrase_in_article(data, phrase):
                article = article_text(data)
            else:
                phrase = None

        if not phrase:
            continue
        if phrase != existing:
            f["link_phrase"] = phrase
            changes.append(f"SET {slug}[{i}] {phrase!r}")
        elif not existing and phrase:
            f["link_phrase"] = phrase
            changes.append(f"SET {slug}[{i}] {phrase!r}")
    return changes


def run_link_phrases_for_day(
    paths: SchuzePaths,
    den: str,
    *,
    dry_run: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    _, iso, day_path = resolve_edition_day(paths, den)
    doc = load_edition(paths, iso)
    assert_editable(doc, force=force, action="doplňovat link_phrase")
    if not day_path.is_file():
        raise FileNotFoundError(f"Chybí {day_path}")
    day = read_json(day_path)
    if not day.get("steno_zdroje"):
        day["steno_zdroje"] = True
        if not dry_run:
            write_json(day_path, day)
    steno_by_id = load_steno_index(paths)
    all_changes: list[str] = []
    files_changed = 0
    for slug in day.get("topic_slugs") or []:
        tpath = paths.facts_by_topic / f"{slug}.json"
        if not tpath.is_file():
            continue
        data = read_json(tpath)
        if data.get("publikovat") is False:
            continue
        before = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        changes = fix_topic(slug, data, steno_by_id)
        if not changes:
            continue
        all_changes.extend(changes)
        if not dry_run:
            after = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
            if after != before:
                write_json(tpath, data)
                files_changed += 1
    return {
        "iso": iso,
        "changes": len(all_changes),
        "files_changed": files_changed,
        "details": all_changes,
        "dry_run": dry_run,
    }
