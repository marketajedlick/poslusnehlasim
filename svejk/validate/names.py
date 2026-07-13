"""Audit jmen a stran v závorkách podle PSP open data."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from svejk.build.io import read_json
from svejk.config import ROOT
from svejk.paths import SchuzePaths

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

DAY_TEXT_FIELDS = ("dnesni_ucet", "zaver")

ANNOTATED = re.compile(
    r"(?:([A-ZÁČĎÉĚÍŇÓŘŠŤÚÝŽ][^\s(,]+(?:\s+[A-ZÁČĎÉĚÍŇÓŘŠŤÚÝŽ][^\s(,]+)?)\s+)?"
    r"([A-ZÁČĎÉĚÍŇÓŘŠŤÚÝŽ][^\s(,]+)"
    r"\s*\(([^)]+)\)"
)


@dataclass
class PartyIssue:
    level: str  # error | warn
    code: str
    slug: str
    context: str
    message: str


def strip_party(label: str) -> str:
    return re.sub(r"\s*\([^)]*\)\s*$", "", label or "").strip()


def speaker_match(autor: str, jmeno: str) -> bool:
    if not autor or not jmeno:
        return False
    a = re.sub(r"\s*\([^)]*\)", "", autor).strip().lower()
    j = jmeno.lower()
    parts = [p for p in a.split() if len(p) > 1]
    if not parts:
        return False
    return parts[-1] in j or (len(parts) >= 2 and parts[0] in j)


def is_vote_score(party: str) -> bool:
    return bool(re.match(r"^\d+:\d+$", party.strip()))


def party_matches(expected: str, given: str) -> bool:
    given = given.split(",")[0].strip()
    return given == expected or given in expected or expected in given


class PoslanecIndex:
    """Rychlé vyhledávání poslance podle jména (včetně pádů příjmení)."""

    def __init__(self, *, data_dir: Path | None = None) -> None:
        from psp.poslanci import _display_klub, _prijmeni_tvary, load_poslanci

        self._display_klub = _display_klub
        self._by_full: dict[str, object] = {}
        self._by_surname: dict[str, list] = defaultdict(list)

        for p in load_poslanci(data_dir=data_dir or ROOT / "data"):
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


def iter_day_texts(day: dict) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for field in DAY_TEXT_FIELDS:
        raw = (day.get(field) or "").strip()
        if raw:
            out.append((field, raw))
    for i, bullet in enumerate(day.get("vysledek") or []):
        raw = (bullet or "").strip()
        if raw:
            out.append((f"vysledek[{i}]", raw))
    return out


def audit_text(
    text: str,
    *,
    index: PoslanecIndex,
    slug: str = "",
    context: str = "",
) -> list[PartyIssue]:
    issues: list[PartyIssue] = []
    for match in ANNOTATED.finditer(text):
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
                PartyIssue(
                    "error",
                    "wrong_party",
                    slug,
                    context,
                    f"«{label} ({party.split(',')[0].strip()})» má být ({expected})",
                )
            )
    return issues


def audit_topic(
    topic: dict,
    *,
    steno_by_id: dict[str, dict] | None = None,
    index: PoslanecIndex | None = None,
) -> list[PartyIssue]:
    issues: list[PartyIssue] = []
    idx = index or PoslanecIndex()
    steno_by_id = steno_by_id or {}
    slug = topic.get("slug") or "?"

    autor = (topic.get("citace_autor") or "").strip()
    sid = (topic.get("steno_id") or "").strip()
    if autor and sid and sid in steno_by_id:
        steno_name = steno_by_id[sid].get("cele_jmeno") or ""
        name = strip_party(autor)
        if name and steno_name:
            if name.split()[-1].lower() != steno_name.split()[-1].lower():
                issues.append(
                    PartyIssue(
                        "error",
                        "citace_autor_spelling",
                        slug,
                        "citace_autor",
                        f"citace_autor «{name}» vs steno «{steno_name}»",
                    )
                )
            elif not speaker_match(autor, steno_name):
                issues.append(
                    PartyIssue(
                        "warn",
                        "citace_autor_speaker",
                        slug,
                        "citace_autor",
                        f"citace_autor «{autor}» vs steno «{steno_name}»",
                    )
                )

    for ctx, raw in iter_topic_texts(topic):
        issues.extend(audit_text(raw, index=idx, slug=slug, context=ctx))
    return issues


def audit_day(
    day: dict,
    *,
    index: PoslanecIndex | None = None,
) -> list[PartyIssue]:
    idx = index or PoslanecIndex()
    issues: list[PartyIssue] = []
    for ctx, raw in iter_day_texts(day):
        issues.extend(audit_text(raw, index=idx, slug="den", context=ctx))
    return issues


def audit_edition_day(
    paths: SchuzePaths,
    iso: str,
    *,
    index: PoslanecIndex | None = None,
) -> list[PartyIssue]:
    idx = index or PoslanecIndex()
    day_path = paths.facts_by_day / f"{iso}.json"
    if not day_path.is_file():
        return []
    day = read_json(day_path)
    issues = audit_day(day, index=idx)
    steno_by_id: dict[str, dict] = {}
    if paths.steno_jsonl.is_file():
        import json

        for line in paths.steno_jsonl.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                if row.get("id"):
                    steno_by_id[row["id"]] = row
    for slug in day.get("topic_slugs") or []:
        topic_path = paths.facts_by_topic / f"{slug}.json"
        if not topic_path.is_file():
            continue
        topic = read_json(topic_path)
        if topic.get("publikovat") is False:
            continue
        issues.extend(audit_topic(topic, steno_by_id=steno_by_id, index=idx))
    return issues


def summarize_party_issues(issues: list[PartyIssue]) -> dict[str, Any]:
    errors = [i for i in issues if i.level == "error"]
    warns = [i for i in issues if i.level == "warn"]
    by_code: dict[str, int] = defaultdict(int)
    for issue in issues:
        by_code[issue.code] += 1
    items = [
        {
            "level": i.level,
            "code": i.code,
            "slug": i.slug,
            "context": i.context,
            "message": i.message,
        }
        for i in issues
    ]
    return {
        "errors": len(errors),
        "warns": len(warns),
        "by_code": dict(sorted(by_code.items())),
        "items": items,
    }


def format_party_errors(issues: list[PartyIssue], *, limit: int = 12) -> str:
    errors = [i for i in issues if i.level == "error"]
    if not errors:
        return ""
    lines = [f"Chyby stran u jmen ({len(errors)}):"]
    for issue in errors[:limit]:
        ctx = f" [{issue.context}]" if issue.context else ""
        lines.append(f"  {issue.slug}{ctx}: {issue.message}")
    if len(errors) > limit:
        lines.append(f"  … +{len(errors) - limit} dalších")
    return "\n".join(lines)
