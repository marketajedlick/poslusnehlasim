#!/usr/bin/env python3
"""Review textu a nadpisů publikovaných článků proti stenozáznamu."""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APPROVED_PATH = ROOT / "processed/publish-approved.json"

TEXT_FIELDS = ("nadpis", "lead", "lead_tail", "pointa", "mean", "kuriozita", "citace_text")

QUOTE_RE = re.compile(
    r"[„\"]([^\"”]{12,}?)[\"”]"
    r"|"
    r"„([^\"]{12,}?)\""
)


def norm(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = re.sub(r"\s+", " ", s).strip()
    for old, new in (("„", '"'), (""", '"'), (""", '"')):
        s = s.replace(old, new)
    return s.lower()


def cit_in_steno(cit: str, text: str) -> bool:
    if not cit or not text:
        return False
    cc = norm(cit).strip('"').strip("'")
    nt = norm(text)
    if cc in nt:
        return True
    for n in (100, 80, 60, 40, 24):
        ch = cc[:n].strip()
        if len(ch) >= 14 and ch in nt:
            return True
    return False


def speaker_match(autor: str, jmeno: str) -> bool:
    if not autor or not jmeno:
        return False
    a = norm(autor).split("(")[0].strip()
    j = norm(jmeno)
    parts = [p for p in a.split() if len(p) > 2]
    if not parts:
        return False
    prijmeni = parts[-1]
    return prijmeni in j


def day_prefixes(datum_cz: str) -> list[str]:
    d = datetime.strptime(datum_cz.strip(), "%d.%m.%Y")
    return [d.strftime("%Y-%m-%d")]


def steno_for_day(steno_by_id: dict[str, dict], prefixes: list[str]) -> list[dict]:
    return [
        r
        for r in steno_by_id.values()
        if any((r.get("datum") or "").startswith(p) for p in prefixes)
    ]


def find_in_steno(
    needle: str,
    steno_all: list[dict],
    *,
    day_only: list[dict] | None = None,
) -> list[tuple[str, str]]:
    hits: list[tuple[str, str]] = []
    for pool in (day_only or [], steno_all):
        if not pool:
            continue
        for r in pool:
            if cit_in_steno(needle, r.get("text", "")):
                hits.append((r["id"], r.get("cele_jmeno") or ""))
        if hits:
            break
    return hits


def extract_quotes(text: str) -> list[str]:
    if not text:
        return []
    out: list[str] = []
    for m in QUOTE_RE.finditer(text):
        q = (m.group(1) or m.group(2) or "").strip()
        if len(q) >= 12:
            out.append(q)
    return out


def parse_key(key: str) -> tuple[int, int, str, str]:
    ob, sc, dz = key.split("/", 2)
    iso = datetime.strptime(dz.strip(), "%d.%m.%Y").strftime("%Y-%m-%d")
    return int(ob), int(sc), iso, dz


def load_approved() -> list[tuple[int, int, str, str]]:
    data = json.loads(APPROVED_PATH.read_text(encoding="utf-8"))
    return [parse_key(k) for k in data.get("approved") or []]


STENO_CACHE: dict[int, dict[str, dict]] = {}


def load_steno(schuze: int, base: Path) -> dict[str, dict]:
    if schuze not in STENO_CACHE:
        by_id: dict[str, dict] = {}
        p = base / "raw/steno.jsonl"
        if p.is_file():
            for line in p.open(encoding="utf-8"):
                r = json.loads(line)
                by_id[r["id"]] = r
        STENO_CACHE[schuze] = by_id
    return STENO_CACHE[schuze]


@dataclass
class Issue:
    level: str  # error | warn
    code: str
    key: str
    slug: str
    message: str


def audit_topic(
    topic: dict,
    *,
    key: str,
    steno_by_id: dict[str, dict],
) -> list[Issue]:
    issues: list[Issue] = []
    slug = topic.get("slug") or "?"
    datum = topic.get("datum") or ""
    prefixes = day_prefixes(datum) if datum else []
    steno_all = list(steno_by_id.values())
    day_rows = steno_for_day(steno_by_id, prefixes) if prefixes else steno_all

    # citace_text + autor
    ct = (topic.get("citace_text") or "").strip()
    autor = (topic.get("citace_autor") or "").strip()
    if ct:
        hits = find_in_steno(ct, steno_all, day_only=day_rows)
        if not hits:
            issues.append(
                Issue(
                    "error",
                    "citace_text_not_in_steno",
                    key,
                    slug,
                    f"citace_text není ve stenu dne: «{ct[:70]}…»",
                )
            )
        elif autor:
            speakers = {h[1] for h in hits}
            if not any(speaker_match(autor, s) for s in speakers):
                issues.append(
                    Issue(
                        "warn",
                        "citace_autor_mismatch",
                        key,
                        slug,
                        f"citace_autor «{autor}» vs steno {sorted(speakers)[:2]}",
                    )
                )

    # uvozovky v textu článku
    for field in TEXT_FIELDS:
        if field == "citace_text":
            continue
        raw = (topic.get(field) or "").strip()
        if not raw:
            continue
        for q in extract_quotes(raw):
            if cit_in_steno(q, ct):
                continue
            hits = find_in_steno(q, steno_all, day_only=day_rows)
            if not hits:
                issues.append(
                    Issue(
                        "error",
                        "quote_not_in_steno",
                        key,
                        slug,
                        f"{field}: citace není ve stenu «{q[:65]}…»",
                    )
                )

    # fakty s citací bez opory
    for i, f in enumerate(topic.get("fakty") or []):
        if not isinstance(f, dict):
            continue
        cit = (f.get("citace") or "").strip()
        if not cit:
            continue
        sid = (f.get("steno_id") or "").strip()
        if sid:
            rec = steno_by_id.get(sid)
            if rec and cit_in_steno(cit, rec.get("text", "")):
                # text faktu vs řečník
                ft = (f.get("text") or "").strip()
                if ft and rec.get("cele_jmeno"):
                    m = re.search(r"^([A-ZÁČĎÉĚÍŇÓŘŠŤÚÝŽ][a-záčďéěíňóřšťúýž]+)", ft)
                    if m and m.group(1) not in (rec.get("cele_jmeno") or ""):
                        issues.append(
                            Issue(
                                "warn",
                                "fakt_speaker_mismatch",
                                key,
                                slug,
                                f"fakty[{i}]: text začíná «{m.group(1)}», steno má «{rec.get('cele_jmeno')}»",
                            )
                        )
                continue
        hits = find_in_steno(cit, steno_all, day_only=day_rows)
        if not hits:
            issues.append(
                Issue(
                    "error",
                    "fakt_citace_not_in_steno",
                    key,
                    slug,
                    f"fakty[{i}].citace není ve stenu: «{cit[:60]}…»",
                )
            )

    # nadpis: klíčová slova (min 5 znaků) by měla mít oporu ve stenu dne
    nadpis = (topic.get("nadpis") or "").replace("\n", " ").strip()
    if nadpis and day_rows and not (topic.get("lead") or "").strip():
        words = [
            w
            for w in re.findall(r"[A-Za-zÁČĎÉĚÍŇÓŘŠŤÚÝŽáčďéěíňóřšťúýž]{5,}", nadpis)
            if w.lower() not in {"sněmovna", "novela", "debata", "vláda", "zákon", "návrh", "schůze"}
        ]
        rare = [w for w in words if len(w) >= 6][:3]
        if rare:
            day_text = " ".join(norm(r.get("text", "")) for r in day_rows)
            missing = [w for w in rare if norm(w) not in day_text]
            if len(missing) == len(rare) and len(rare) >= 2:
                issues.append(
                    Issue(
                        "warn",
                        "nadpis_off_topic",
                        key,
                        slug,
                        f"nadpis «{nadpis[:50]}» – klíčová slova {missing} nejsou ve stenu dne",
                    )
                )

    return issues


def main() -> int:
    approved = load_approved()
    all_issues: list[Issue] = []
    by_code: dict[str, int] = defaultdict(int)

    for obdobi, schuze, iso, key in approved:
        base = ROOT / f"processed/{obdobi}-s{schuze}"
        day_path = base / "facts/by_day" / f"{iso}.json"
        if not day_path.is_file():
            continue
        steno_by_id = load_steno(schuze, base)
        if not steno_by_id:
            continue
        day = json.loads(day_path.read_text(encoding="utf-8"))
        for slug in day.get("topic_slugs") or []:
            tpath = base / "facts/by_topic" / f"{slug}.json"
            if not tpath.is_file():
                continue
            topic = json.loads(tpath.read_text(encoding="utf-8"))
            if topic.get("publikovat") is False:
                continue
            for iss in audit_topic(topic, key=key, steno_by_id=steno_by_id):
                all_issues.append(iss)
                by_code[iss.code] += 1

    errors = [i for i in all_issues if i.level == "error"]
    warns = [i for i in all_issues if i.level == "warn"]

    print(f"Text review: {len(approved)} dní, {len(errors)} chyb, {len(warns)} varování\n")
    print("Podle typu:")
    for code, n in sorted(by_code.items(), key=lambda x: -x[1]):
        print(f"  {code}: {n}")

    if errors:
        print(f"\n── CHYBY ({len(errors)}) ──")
        for i in errors[:40]:
            print(f"  [{i.key}] {i.slug}: {i.message}")
        if len(errors) > 40:
            print(f"  … +{len(errors) - 40} dalších")

    if warns:
        print(f"\n── VAROVÁNÍ ({len(warns)}) ──")
        for i in warns[:25]:
            print(f"  [{i.key}] {i.slug}: {i.message}")
        if len(warns) > 25:
            print(f"  … +{len(warns) - 25} dalších")

    # uložit report
    out = ROOT / "processed/text-review-report.txt"
    lines = [f"errors={len(errors)} warns={len(warns)}\n"]
    for i in all_issues:
        lines.append(f"{i.level}\t{i.code}\t{i.key}\t{i.slug}\t{i.message}\n")
    out.write_text("".join(lines), encoding="utf-8")
    print(f"\nReport: {out}")

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
