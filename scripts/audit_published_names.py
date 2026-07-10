#!/usr/bin/env python3
"""Audit jmen a stran v publikovaných článcích (facts/)."""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APPROVED_PATH = ROOT / "processed/publish-approved.json"
REPORT_PATH = ROOT / "processed/name-audit-report.txt"

TEXT_FIELDS = (
    "nadpis",
    "lead",
    "lead_tail",
    "pointa",
    "mean",
    "kuriozita",
    "citace_text",
    "citace_autor",
)

# Jméno nebo celé jméno + strana v závorce (ne skóre hlasování).
ANNOTATED = re.compile(
    r"(?:([A-ZÁČĎÉĚÍŇÓŘŠŤÚÝŽ][^\s(,]+(?:\s+[A-ZÁČĎÉĚÍŇÓŘŠŤÚÝŽ][^\s(,]+)?)\s+)?"
    r"([A-ZÁČĎÉĚÍŇÓŘŠŤÚÝŽ][^\s(,]+)"
    r"\s*\(([^)]+)\)"
)


@dataclass
class Issue:
    level: str  # error | warn
    code: str
    key: str
    slug: str
    message: str


def parse_key(key: str) -> tuple[int, int, str, str]:
    ob, sc, dz = key.split("/", 2)
    iso = datetime.strptime(dz.strip(), "%d.%m.%Y").strftime("%Y-%m-%d")
    return int(ob), int(sc), iso, dz.strip()


def load_keys(*, include_hidden: bool) -> list[str]:
    data = json.loads(APPROVED_PATH.read_text(encoding="utf-8"))
    keys = list(data.get("approved") or [])
    if include_hidden:
        keys.extend(data.get("hidden") or [])
    return keys


def load_steno(schuze: int, base: Path) -> dict[str, dict]:
    by_id: dict[str, dict] = {}
    path = base / "raw/steno.jsonl"
    if not path.is_file():
        return by_id
    for line in path.open(encoding="utf-8"):
        row = json.loads(line)
        by_id[row["id"]] = row
    return by_id


def speaker_match(autor: str, jmeno: str) -> bool:
    if not autor or not jmeno:
        return False
    a = re.sub(r"\s*\([^)]*\)", "", autor).strip().lower()
    j = jmeno.lower()
    parts = [p for p in a.split() if len(p) > 1]
    if not parts:
        return False
    return parts[-1] in j or (len(parts) >= 2 and parts[0] in j)


def strip_party(label: str) -> str:
    return re.sub(r"\s*\([^)]*\)\s*$", "", label or "").strip()


class PoslanecIndex:
    """Rychlé vyhledávání poslance podle jména (včetně pádů příjmení)."""

    def __init__(self) -> None:
        sys.path.insert(0, str(ROOT))
        from psp.poslanci import _display_klub, _prijmeni_tvary, load_poslanci

        self._display_klub = _display_klub
        self._by_full: dict[str, object] = {}
        self._by_surname: dict[str, list] = defaultdict(list)

        for p in load_poslanci(data_dir=ROOT / "data"):
            fn = f"{p.jmeno} {p.prijmeni}".lower()
            self._by_full[fn] = p
            self._by_surname[p.prijmeni.lower()].append(p)
            for tvar in _prijmeni_tvary(p.prijmeni, p.pohlavi):
                self._by_surname[tvar.lower()].append(p)

    def resolve(self, name: str):
        name = name.strip()
        if not name:
            return None
        parts = name.split()
        if len(parts) >= 2:
            p = self._by_full.get(f"{parts[0]} {parts[-1]}".lower())
            if p:
                return p
            for cand in self._by_surname.get(parts[-1].lower(), []):
                if cand.jmeno.lower() == parts[0].lower():
                    return cand
            return None
        cands = list({id(x): x for x in self._by_surname.get(name.lower(), [])}.values())
        return cands[0] if len(cands) == 1 else None

    def expected_party(self, poslanec) -> str:
        return self._display_klub(poslanec)


def is_vote_score(party: str) -> bool:
    return bool(re.match(r"^\d+:\d+$", party.strip()))


def party_matches(expected: str, given: str) -> bool:
    given = given.split(",")[0].strip()
    return given == expected or given in expected or expected in given


def iter_topic_texts(topic: dict) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for field in TEXT_FIELDS:
        raw = (topic.get(field) or "").strip()
        if raw:
            out.append((field, raw))
    for i, fact in enumerate(topic.get("fakty") or []):
        if isinstance(fact, dict):
            raw = (fact.get("text") or "").strip()
            if raw:
                out.append((f"fakty[{i}]", raw))
    return out


def audit_topic(
    topic: dict,
    *,
    key: str,
    steno_by_id: dict[str, dict],
    index: PoslanecIndex,
) -> list[Issue]:
    issues: list[Issue] = []
    slug = topic.get("slug") or "?"

    autor = (topic.get("citace_autor") or "").strip()
    sid = (topic.get("steno_id") or "").strip()
    if autor and sid and sid in steno_by_id:
        steno_name = steno_by_id[sid].get("cele_jmeno") or ""
        name = strip_party(autor)
        if name and steno_name:
            if name.split()[-1].lower() != steno_name.split()[-1].lower():
                issues.append(
                    Issue(
                        "error",
                        "citace_autor_spelling",
                        key,
                        slug,
                        f"citace_autor «{name}» vs steno «{steno_name}»",
                    )
                )
            elif not speaker_match(autor, steno_name):
                issues.append(
                    Issue(
                        "warn",
                        "citace_autor_speaker",
                        key,
                        slug,
                        f"citace_autor «{autor}» vs steno «{steno_name}»",
                    )
                )

    for ctx, raw in iter_topic_texts(topic):
        for match in ANNOTATED.finditer(raw):
            jmeno, prijmeni, party = match.group(1), match.group(2), match.group(3)
            if is_vote_score(party):
                continue
            label = f"{jmeno} {prijmeni}".strip() if jmeno else prijmeni
            poslanec = index.resolve(label)
            if not poslanec:
                continue
            expected = index.expected_party(poslanec)
            if not party_matches(expected, party):
                issues.append(
                    Issue(
                        "error",
                        "wrong_party",
                        key,
                        slug,
                        f"«{label} ({party.split(',')[0].strip()})» má být ({expected}) [{ctx}]",
                    )
                )

    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit jmen a stran v publikovaných článcích.")
    parser.add_argument(
        "--include-hidden",
        action="store_true",
        help="zahrnout i dny z publish-approved.json → hidden",
    )
    args = parser.parse_args()

    keys = load_keys(include_hidden=args.include_hidden)
    index = PoslanecIndex()
    all_issues: list[Issue] = []
    by_code: dict[str, int] = defaultdict(int)

    for key in keys:
        ob, schuze, iso, _ = parse_key(key)
        base = ROOT / f"processed/{ob}-s{schuze}"
        day_path = base / "facts/by_day" / f"{iso}.json"
        if not day_path.is_file():
            continue
        steno_by_id = load_steno(schuze, base)
        day = json.loads(day_path.read_text(encoding="utf-8"))
        for slug in day.get("topic_slugs") or []:
            topic_path = base / "facts/by_topic" / f"{slug}.json"
            if not topic_path.is_file():
                continue
            topic = json.loads(topic_path.read_text(encoding="utf-8"))
            if topic.get("publikovat") is False:
                continue
            for issue in audit_topic(
                topic, key=key, steno_by_id=steno_by_id, index=index
            ):
                all_issues.append(issue)
                by_code[issue.code] += 1

    errors = [i for i in all_issues if i.level == "error"]
    warns = [i for i in all_issues if i.level == "warn"]

    print(f"Name audit: {len(keys)} dní, {len(errors)} chyb, {len(warns)} varování\n")
    print("Podle typu:")
    for code, count in sorted(by_code.items(), key=lambda x: -x[1]):
        print(f"  {code}: {count}")

    if errors:
        print(f"\n── CHYBY ({len(errors)}) ──")
        for issue in errors:
            print(f"  [{issue.key}] {issue.slug}: {issue.message}")

    if warns:
        print(f"\n── VAROVÁNÍ ({len(warns)}) ──")
        for issue in warns[:25]:
            print(f"  [{issue.key}] {issue.slug}: {issue.message}")
        if len(warns) > 25:
            print(f"  … +{len(warns) - 25} dalších")

    lines = [f"errors={len(errors)} warns={len(warns)}\n"]
    for issue in all_issues:
        lines.append(
            f"{issue.level}\t{issue.code}\t{issue.key}\t{issue.slug}\t{issue.message}\n"
        )
    REPORT_PATH.write_text("".join(lines), encoding="utf-8")
    print(f"\nReport: {REPORT_PATH}")

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
