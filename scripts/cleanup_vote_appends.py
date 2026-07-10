#!/usr/bin/env python3
"""Cleanup hlasovacích appendů: pass 1 ořízne konce, pass 2 vestavěné bloky v pointa/mean."""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from svejk.build.steno_sources import _find_phrase_in_text, collect_steno_sources  # noqa: E402
from svejk.paths import SchuzePaths  # noqa: E402

APPROVED = json.loads((ROOT / "processed/publish-approved.json").read_text())["approved"]
VOTE_LP = re.compile(r"^(Hlasování|V hlasování|Konstatuji|Předtím hlasování)", re.I)
SCORE_IN_LEAD = re.compile(
    r"\d+\s+hlas(?:y|ů)?(?:\s+pro)?,?\s+(?:nikdo\s+proti|\d+\s+proti)|"
    r"\d+\s+proti\s+\d+|\d+:\d+",
    re.I,
)
VOTE_INLINE = re.compile(
    r"(?:\s*Předtím)?\s*Hlasování číslo\s+\d[^.!?]*(?:[.!?]|$)",
    re.I,
)
VOTE_INLINE2 = re.compile(r"\s*V hlasování číslo\s+\d[^.!?]*[.!?]", re.I)
VOTE_KONSTAT = re.compile(r"\s*Konstatuji, že v hlasování[^.!?]*[.!?]", re.I)
JUNK_INLINE = [
    re.compile(r"\s*S návrhem zákona\.?", re.I),
    re.compile(r"\s*Návrh byl přijat\.?", re.I),
    re.compile(r"\s*Návrh byl přikázán(?:\s+garančnímu výboru)?\.?", re.I),
    re.compile(r"\s*Poslanec\s+[^.!?]+ přistupuje k řečništi\.?", re.I),
    re.compile(r"\s*Prosím, aby se slova ujal[^.!?]*\.?", re.I),
    re.compile(r"\s*Já bych si ještě ráda dovolila[^.!?]*,\.?", re.I),
]
BROKEN_NE_NA = re.compile(r", ne na\.\s*")
PRO_MEAN = re.compile(r"\s*pro mean\.?$", re.I)


def parse_key(k: str):
    ob, sch, cz = k.split("/", 2)
    iso = datetime.strptime(cz.strip(), "%d.%m.%Y").strftime("%Y-%m-%d")
    return int(sch), iso


def art(data: dict) -> str:
    parts = []
    for k in ("lead", "pointa", "mean", "citace_text"):
        v = (data.get(k) or "").strip()
        if v:
            parts.append(re.sub(r"<[^>]+>", " ", v))
    return " ".join(parts)


def strip_end(body: str, phrase: str) -> str | None:
    p = phrase.strip().rstrip(".")
    for suf in (f" {p}.", f". {p}.", f" {p}", f". {p}"):
        if body.endswith(suf):
            return body[: -len(suf)].rstrip()
    return None


def score_alt(data: dict) -> str | None:
    lead = (data.get("lead") or "")
    m = SCORE_IN_LEAD.search(lead)
    return m.group(0) if m else None


def scrub_fragment_tails(body: str) -> str:
    body = re.sub(r"\.\s+Ten\.\s*$", ".", body)
    body = re.sub(r"\s+super EKO-KOM[^.]*\.\s*super EKO-KOM[^.]*\.\s*134 proti 1\.?\s*$", "", body)
    body = re.sub(r"\.?\s+Hlasování číslo[^.!?]*[.!?]?\s*$", "", body)
    body = re.sub(r"\.?\s+V hlasování číslo[^.!?]*[.!?]?\s*$", "", body)
    body = re.sub(r"\.?\s+Konstatuji, že v hlasování[^.!?]*[.!?]?\s*$", "", body)
    return body.strip()


def scrub_inline(body: str) -> str:
    prev = None
    while prev != body:
        prev = body
        body = VOTE_INLINE.sub("", body)
        body = VOTE_INLINE2.sub("", body)
        body = VOTE_KONSTAT.sub("", body)
        for pat in JUNK_INLINE:
            body = pat.sub("", body)
    body = BROKEN_NE_NA.sub(". ", body)
    body = re.sub(r"\s+", " ", body).strip()
    body = re.sub(r"\.\s*\.+", ".", body)
    return body.strip()


def fix_broken_ne_na(data: dict, body: str) -> str:
    if ", ne na" not in body and "ne na." not in body:
        return body
    for f in data.get("fakty") or []:
        if not isinstance(f, dict):
            continue
        ft = (f.get("text") or "").strip()
        lp = (f.get("link_phrase") or "").strip()
        if "ne na" in ft and lp and lp in body:
            return body.replace(lp.rstrip("."), ft.rstrip("."))
        if ft.startswith("Novela zavádí cílení") and "ne na." in body:
            return body.replace("ne na.", "ne na kohokoli.")
    return body


def is_doc_title(ft: str) -> bool:
    if len(ft) < 50:
        return False
    markers = (
        "Správní rady",
        "náhradníků",
        "Poslanecké sněmovny",
        "Vládní návrh",
        "usnesení",
        "pojišťovny České republiky",
    )
    return any(m in ft for m in markers)


def strip_fact_title_fragments(data: dict, body: str) -> str:
    for f in data.get("fakty") or []:
        if not isinstance(f, dict):
            continue
        ft = (f.get("text") or "").strip()
        if not is_doc_title(ft):
            continue
        for n in range(min(len(ft), 90), 25, -1):
            frag = ft[:n].rstrip()
            if body.endswith(frag) or f". {frag}." in body or body.endswith(f"{frag}."):
                body = body.replace(f". {frag}.", ".").replace(f"{frag}.", ".").replace(frag, "")
                body = re.sub(r"\s+", " ", body).strip()
                break
    return body


def scrub_pro_mean_facts(data: dict, changes: list[str]) -> None:
    fakty = data.get("fakty") or []
    kept: list[dict] = []
    for f in fakty:
        if not isinstance(f, dict):
            kept.append(f)
            continue
        text = (f.get("text") or "").strip()
        if not PRO_MEAN.search(text):
            kept.append(f)
            continue
        lp = (f.get("link_phrase") or "").strip()
        dup = any(
            other is not f
            and isinstance(other, dict)
            and (other.get("link_phrase") or "").strip() == lp
            and not PRO_MEAN.search((other.get("text") or ""))
            for other in fakty
        )
        if dup:
            changes.append(f"DROP pro mean {text[:35]!r}")
            continue
        cit = (f.get("citace") or "").strip()
        if cit:
            who = text.split(" o ")[0].strip() if " o " in text else text.split(" pro mean")[0].strip()
            f["text"] = f"{who} řekl: {cit[:120].rstrip('.,')}"
            if PRO_MEAN.search((f.get("link_phrase") or "")):
                alt = best_alt(data, f.get("link_phrase") or "", f["text"])
                if alt:
                    f["link_phrase"] = alt
            changes.append(f"FIX pro mean {who!r}")
            kept.append(f)
        else:
            changes.append(f"DROP pro mean orphan {text[:35]!r}")
    data["fakty"] = kept


def scrub_pass2(data: dict, changes: list[str]) -> None:
    for field in ("pointa", "mean"):
        body = (data.get(field) or "").strip()
        if not body:
            continue
        new = scrub_inline(body)
        new = fix_broken_ne_na(data, new)
        new = strip_fact_title_fragments(data, new)
        if new != body:
            data[field] = new
            changes.append(f"INLINE {field}")
    scrub_pro_mean_facts(data, changes)
    for f in data.get("fakty") or []:
        if not isinstance(f, dict):
            continue
        lp = (f.get("link_phrase") or "").strip()
        if lp and VOTE_LP.match(lp):
            alt = vote_link_alt(data, f.get("text") or "") or vote_score_from_fact(f.get("text") or "")
            if alt:
                f["link_phrase"] = alt
                changes.append(f"VOTE_LP {alt!r}")


def vote_score_from_fact(summary: str) -> str | None:
    m = re.search(r"pro\s+(\d+|nikdo),?\s*proti\s*(\d+|nikdo)?", summary, re.I)
    if not m:
        return None
    pro, proti = m.group(1).lower(), (m.group(2) or "nikdo").lower()
    if proti in ("nikdo", "0", ""):
        return f"{pro} hlasy pro, nikdo proti" if pro.isdigit() else None
    if pro.isdigit() and proti.isdigit():
        return f"{pro} proti {proti}"
    return None


def fix_topic(data: dict) -> list[str]:
    changes: list[str] = []
    for field in ("pointa", "mean"):
        body = (data.get(field) or "").strip()
        if not body:
            continue
        new = scrub_fragment_tails(body)
        if new != body:
            data[field] = new
            body = new
            changes.append(f"SCRUB {field}")
        for f in data.get("fakty") or []:
            if not isinstance(f, dict):
                continue
            lp = (f.get("link_phrase") or "").strip()
            if not lp:
                continue
            if VOTE_LP.match(lp) or lp.startswith("V hlasování"):
                cut = strip_end(body, lp)
                if cut:
                    alt = vote_link_alt(data, f.get("text") or "") or best_alt(data, lp, f.get("text") or "")
                    if alt:
                        f["link_phrase"] = alt
                        data[field] = cut
                        body = cut
                        changes.append(f"VOTE {lp[:40]!r} -> {alt!r}")
            elif strip_end(body, lp):
                cut = strip_end(body, lp)
                if cut and _still_ok(data, field, cut, lp):
                    data[field] = cut
                    body = cut
                    changes.append(f"TAIL {lp[:40]!r}")
    relocate_all(data, changes)
    scrub_pass2(data, changes)
    relocate_all(data, changes)
    return changes


def vote_link_alt(data: dict, summary: str) -> str | None:
    alt = score_alt(data)
    if alt:
        return alt
    a = art(data)
    words = (summary or "").split()
    for n in range(min(10, len(words)), 2, -1):
        chunk = " ".join(words[:n])
        if len(chunk) >= 8 and _find_phrase_in_text(a, chunk):
            return chunk
    return None


def best_alt(data: dict, lp: str, summary: str) -> str | None:
    if VOTE_LP.match(lp):
        return vote_link_alt(data, summary)
    a = art(data)
    for cand in (summary, lp):
        words = (cand or "").split()
        for n in range(min(10, len(words)), 2, -1):
            chunk = " ".join(words[:n])
            if len(chunk) >= 8 and _find_phrase_in_text(a, chunk):
                return chunk
    return None


def _still_ok(data: dict, field: str, new_body: str, removed_lp: str) -> bool:
    trial = dict(data)
    trial[field] = new_body
    for f in trial.get("fakty") or []:
        if isinstance(f, dict) and (f.get("link_phrase") or "").strip() == removed_lp:
            alt = best_alt(trial, removed_lp, f.get("text") or "")
            if not alt:
                return False
            f["link_phrase"] = alt
    return all(
        not (f.get("link_phrase") or "").strip()
        or _find_phrase_in_text(art(trial), (f.get("link_phrase") or "").strip())
        for f in trial.get("fakty") or []
        if isinstance(f, dict)
    )


def relocate_all(data: dict, changes: list[str]) -> None:
    a = art(data)
    for f in data.get("fakty") or []:
        if not isinstance(f, dict):
            continue
        lp = (f.get("link_phrase") or "").strip()
        if lp and not _find_phrase_in_text(a, lp):
            alt = best_alt(data, lp, f.get("text") or "")
            if alt:
                f["link_phrase"] = alt
                changes.append(f"LINK {alt!r}")


def main():
    dry = "--dry-run" in sys.argv
    n = 0
    for key in APPROVED:
        sch, iso = parse_key(key)
        paths = SchuzePaths.create(2025, sch)
        dayp = paths.facts_by_day / f"{iso}.json"
        if not dayp.is_file():
            continue
        day = json.loads(dayp.read_text())
        if not day.get("steno_zdroje"):
            continue
        for slug in day.get("topic_slugs") or []:
            fp = paths.facts_by_topic / f"{slug}.json"
            data = json.loads(fp.read_text())
            if not data.get("publikovat"):
                continue
            ch = fix_topic(data)
            if not ch:
                continue
            n += 1
            print(slug, ch[:4])
            if not dry:
                fp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("files", n)


if __name__ == "__main__":
    main()
