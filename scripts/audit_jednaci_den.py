#!/usr/bin/env python3
"""Audit dopadu jednacího dne na publikovaná vydání (jen čtení, nic nemění)."""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APPROVED_PATH = ROOT / "processed/publish-approved.json"

sys.path.insert(0, str(ROOT))

from svejk.build.io import iter_jsonl, read_json  # noqa: E402
from svejk.jednaci_den import je_noc_po_pulnoci, vote_jednaci_datum  # noqa: E402
from svejk.paths import SchuzePaths  # noqa: E402


def parse_key(key: str) -> tuple[int, int, str, str]:
    ob, sch, cz = key.split("/", 2)
    iso = datetime.strptime(cz.strip(), "%d.%m.%Y").strftime("%Y-%m-%d")
    return int(ob), int(sch), iso, cz.strip()


def _calendar_datum(v: dict) -> str:
    return (v.get("datum") or "").strip()


def midnight_votes_on_calendar_day(votes: list[dict], jednaci_unl: str) -> list[dict]:
    """Hlasování v 00:00–05:59, které pod novým pravidlem patří k jednaci_unl."""
    out: list[dict] = []
    for v in votes:
        if vote_jednaci_datum(v) != jednaci_unl:
            continue
        if je_noc_po_pulnoci(v.get("cas") or ""):
            if _calendar_datum(v) != jednaci_unl:
                out.append(v)
    return out


def midnight_votes_leaving_day(votes: list[dict], jednaci_unl: str) -> list[dict]:
    """Hlasování s kalendářním jednaci_unl, které po půlnoci odejde na předchozí den."""
    out: list[dict] = []
    for v in votes:
        if _calendar_datum(v) != jednaci_unl:
            continue
        if je_noc_po_pulnoci(v.get("cas") or ""):
            out.append(v)
    return out


def expected_published_slugs(paths: SchuzePaths, jednaci_unl: str) -> set[str]:
    """Témata, která by po re-extract patřila k jednacímu dni (bez zápisu)."""
    if not paths.topics_json.is_file():
        return set()
    topics = read_json(paths.topics_json).get("topics") or []
    votes_by_cislo: dict[int, dict] = {}
    for v in iter_jsonl(paths.votes_jsonl):
        c = v.get("cislo")
        if c is not None:
            votes_by_cislo[int(c)] = v

    out: set[str] = set()
    for t in topics:
        slug = t.get("slug")
        if not slug:
            continue
        fp = paths.facts_by_topic / f"{slug}.json"
        if not fp.is_file() or not read_json(fp).get("publikovat"):
            continue
        cisla = [int(c) for c in (t.get("vote_cisla") or []) if int(c) in votes_by_cislo]
        if not cisla:
            continue
        group = sorted(
            (votes_by_cislo[c] for c in cisla),
            key=lambda v: (v.get("datum", ""), v.get("cas", "")),
        )
        if vote_jednaci_datum(group[-1]) == jednaci_unl:
            out.add(slug)
    return out


def main() -> int:
    approved = json.loads(APPROVED_PATH.read_text(encoding="utf-8")).get("approved") or []
    if not approved:
        print("Žádná approved vydání v publish-approved.json")
        return 0

    issues: list[str] = []
    info: list[str] = []
    ok = 0

    print(f"Audit jednacího dne — {len(approved)} schválených vydání\n")

    for key in approved:
        ob, sch, iso, cz = parse_key(key)
        paths = SchuzePaths.create(ob, sch)
        day_path = paths.facts_by_day / f"{iso}.json"
        votes_path = paths.votes_jsonl

        if not day_path.is_file():
            issues.append(f"{key}: chybí facts/by_day/{iso}.json")
            continue
        if not votes_path.is_file():
            issues.append(f"{key}: chybí raw/votes.jsonl")
            continue

        day = read_json(day_path)
        votes = list(iter_jsonl(votes_path))
        current_slugs = set(day.get("topic_slugs") or [])

        incoming = midnight_votes_on_calendar_day(votes, cz)
        outgoing = midnight_votes_leaving_day(votes, cz)

        # Témata po re-extract (simulace z hlasování, ne ze stale topics.datum)
        new_slugs = expected_published_slugs(paths, cz)

        added = new_slugs - current_slugs
        removed = current_slugs - new_slugs
        manual = bool(
            day.get("dnesni_ucet") or day.get("zaver") or day.get("vysledek")
        )

        if not incoming and not outgoing and not added and not removed:
            ok += 1
            continue

        lines = [f"## {key} ({day.get('den', '?')})"]
        if manual:
            lines.append("  ⚠ ruční text: dnesni_ucet / zaver / vysledek")

        if incoming:
            lines.append(f"  + {len(incoming)} nočních hlasování z jiného kalendářního dne:")
            for v in incoming[:3]:
                lines.append(
                    f"      {v.get('datum')} {v.get('cas')} #{v.get('cislo')} "
                    f"{(v.get('nazev') or '')[:50]}"
                )
            if len(incoming) > 3:
                lines.append(f"      … +{len(incoming) - 3}")

        if outgoing:
            lines.append(
                f"  − {len(outgoing)} hlasování po půlnoci odejde na "
                f"{vote_jednaci_datum(outgoing[0])}:"
            )
            for v in outgoing[:3]:
                lines.append(
                    f"      {v.get('datum')} {v.get('cas')} #{v.get('cislo')} "
                    f"{(v.get('nazev') or '')[:50]}"
                )

        if added:
            lines.append(f"  + témata po re-align/extract: {', '.join(sorted(added)[:5])}")
            if len(added) > 5:
                lines.append(f"      … +{len(added) - 5}")

        if removed:
            lines.append(f"  − témata by zmizela z tohoto dne: {', '.join(sorted(removed)[:5])}")
            if len(removed) > 5:
                lines.append(f"      … +{len(removed) - 5}")
            if manual:
                issues.append(
                    f"{key}: změna témat + ruční text (riziko rozbití vydání po re-extract)"
                )
            elif removed:
                issues.append(f"{key}: témata by se přesunula jinam po re-extract")

        info.extend(lines)
        info.append("")

    print(f"Bez dopadu: {ok}/{len(approved)} vydání\n")

    if issues:
        print(f"⚠ Riziko ({len(issues)}):\n")
        for i in issues:
            print(f"  • {i}")
        print()

    if info:
        print("Detail u dotčených dnů:\n")
        print("\n".join(info))

    print("—")
    print("Poznámka: existující HTML/noviny se samy nezmění, dokud nespustíš")
    print("align + extract. Compose už filtruje hlasování podle jednacího dne,")
    print("takže u dotčených dnů může stats ve výsledku nesedět, dokud facts")
    print("nesjednotíš re-extractem (nebo ruční úpravou topic_slugs).")

    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
