#!/usr/bin/env python3
"""Sjednotí anglickou sněmovní terminologii v blocích ``en`` ve facts JSON."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))

# Přesné náhrady (déle první).
_EXACT: list[tuple[str, str]] = [
    ("The Austrian", "Rakušan"),
    ("Rabbit called", "Králíček called"),
    ("Officials remain", "Officials Stay Put"),
    ("The conviction did not go through", "Motion to condemn failed"),
    ("Prime minister in the dining room", "Prime Minister Missing from the Chamber"),
    ("Reduction of advances for self-employed persons", "Lower Contributions for the Self-Employed"),
    ("Two days of distrust", "Two days of no confidence"),
    ("The minimum did not pass", "Living Minimum Rejected"),
    ("Benefit minimum delayed", "Living Minimum Rejected"),
    ("They did not release Babis", "Babiš kept his immunity"),
    ("The state controls the data", "Authorities Will Share Data"),
    ("The SAO would also control the media", "Audit office to oversee public media finances"),
    ("The tubes will be monitored", "Shortages of laboratory tubes must be reported"),
    ("Okamura without trial", "Okamura keeps his immunity"),
    ("The Middle East and the show", "Middle East and a Fight Over the Agenda"),
    ("Show before midnight", "Agenda Battle Before Midnight"),
    ("The show before the budget", "Agenda Fight Before the Budget"),
    ("House of Commons", "The Chamber of Deputies"),
    ("the fight for the show", "a fight over the agenda"),
    ("votes on the show", "votes on the agenda"),
    ("voting on the show", "votes on the agenda"),
    ("only voting on the show", "only votes on the agenda"),
    ("The super dose is three months longer", "Transition to super benefit extended"),
    ("Gasoline price night", "A Long Night Over Fuel Prices"),
    ("Gasoline under state supervision", "Government Gets Fuel Price Powers"),
    ("Criminal amendment dropped", "Criminal Code Changes Failed"),
    ("Rules of The Chamber of Deputies", "Who Gets to Speak"),
    ("Prime Minister Missing from the Chamber", "Prime Minister Missing from The Chamber of Deputies"),
    ("Budget for the first attempt", "Budget Passes First Reading"),
    ("Budget passes first reading", "Budget Passes First Reading"),
    ("Committees on the edge", "The Battle for Committees"),
    ("European Committee in half", "European Committee Expanded"),
    ("Cart instead of program", "A Shopping Cart Takes the Floor"),
    ("The banner must not cover the speaker", "The Banner Incident"),
    ("Okamura at the hammer", "Okamura takes the gavel"),
    ("mandate committee", "Mandate and Immunity Committee"),
    (
        "After two days of speeches, the House rejected the motion of no confidence in the government, 99 votes against 84. The coalition applauded, the opposition did not reach the necessary majority.",
        "After two days of speeches, the government survived: 99 against, 84 for. The coalition applauded, the opposition did not pull it off this time.",
    ),
    (
        "More than 100 votes were needed to bring down the government. Mistrust fell, Babiš's government continues.",
        "More than 100 votes were needed to bring down the government. No confidence failed, Babiš's government carries on.",
    ),
    (
        "that the extraordinary meeting talked about a major reform of the authorities all day, but the House stopped it in the first round.",
        "that the extraordinary meeting talked about a major reform of the authorities all day, but The Chamber of Deputies stopped it at first reading.",
    ),
    (
        "that the House of Representatives made sure by voting twenty-one times on the building bill that it would not go home yet",
        "that The Chamber of Deputies voted twenty-one times on the building bill and still would not let anyone go home",
    ),
    (
        "that the House of Representatives occupied the CT Council and the vice-chairman's seat on Friday, returned the proposal on spraying to the second round and simply eliminated the rest of the program.",
        "that The Chamber of Deputies filled the CT Council and a Deputy Speaker's seat on Friday, sent the spraying bill back to second reading, and simply dropped the rest of the programme.",
    ),
    (
        "that after ten years the records of sales are coming back: the first round has passed, Schillerová swears that she is not obsessed with EET, and the construction law again kept the deputies in the hall until night.",
        "that after ten years sales records are coming back: first reading passed, Schillerová swears she is not EET-obsessed, and the Construction Bill again kept deputies in The Chamber of Deputies until night.",
    ),
    ("Metals on a conveyor belt", "State Honours on a conveyor belt"),
    (
        "Miloš Zeman was voted three times before it was valid.",
        "It took three rounds of voting before Zeman's nomination passed.",
    ),
    (
        "Miloš Zeman was voted three times before it was valid",
        "It took three rounds of voting before Zeman's nomination passed",
    ),
    ("she is not obsessed with EET.", "she is not EET-obsessed."),
    ("she is not obsessed with EET", "she is not EET-obsessed"),
    ("Schillerová swears she is not obsessed with EET", "Schillerová swears she is not EET-obsessed"),
    ("165 metal votes", "165 state honour votes"),
    ("proposals for metals", "state honour nominations"),
    ("candidates for metals", "candidates for state honours"),
    ("closest to the metal", "closest to the honour"),
    ("on 28 October", "on Czech Statehood Day (Oct. 28)"),
    ("on October 28", "on Czech Statehood Day (Oct. 28)"),
    (
        "first reading of EET (electronic sales records) return in the evening",
        "first reading of the return of EET (electronic sales records) in the evening",
    ),
    (
        "that The Chamber of Deputies filled the CT Council and a Deputy Speaker's seat on Friday, sent the spraying bill back to second reading, and simply dropped the rest of the programme.",
        "that The Chamber of Deputies filled the Czech Television Council and a Deputy Speaker's seat on Friday, sent the spraying bill back to second reading, and simply dropped the rest of the programme.",
    ),
]

# Regex náhrady (pořadí záleží).
_REGEX: list[tuple[str, str]] = [
    # Volby: kolo ≠ čtení.
    (r"\bin the first round of the secret election\b", "on the first ballot of the secret election"),
    (r"\bfirst round of the secret election\b", "first ballot of the secret election"),
    (r"\bvotes in the first round\b", "votes on the first ballot"),
    (r"\belected chairman \(116 votes in the first round\)", "elected chairman (116 votes on the first ballot)"),
    (r"\bJiří Barták won 113 votes, Patrik Nacher 98 votes\.", "Jiří Barták won 113 votes, Patrik Nacher 98 votes."),
    # Čtení zákonů.
    (r"\bin the final vote\b", "at third reading"),
    (r"\bthe final vote\b", "the third reading"),
    (r"\bfinal vote\b", "third reading"),
    (r"\bin the second round\b", "at second reading"),
    (r"\bto the second round\b", "to second reading"),
    (r"\bthe second round\b", "the second reading"),
    (r"\bsecond round\b", "second reading"),
    (r"\bsurvived the first round\b", "passed first reading"),
    (r"\bfailed in the first round\b", "failed at first reading"),
    (r"\bstopped it in the first round\b", "stopped it at first reading"),
    (r"\bfell in the first round\b", "fell at first reading"),
    (r"\bpassed in the first round\b", "passed at first reading"),
    (r"\bpassed the first round\b", "passed first reading"),
    (r"\bthe first round passed\b", "first reading passed"),
    (r"\bfirst round passed\b", "first reading passed"),
    (r"\badvanced from the first round\b", "passed first reading"),
    (r"\bfrom the first round\b", "from first reading"),
    (r"\bin the first round\b", "at first reading"),
    (r"\bthe first round\b", "first reading"),
    (r"\bfirst round of\b", "first reading of"),
    (r"\bfirst round\b", "first reading"),
    (r"\bIt is the first round:\b", "So far it is first reading:"),
    (r"\bit's the first round:\b", "it's first reading:"),
    (r"\bSo far, it is the first round:\b", "So far, it is first reading:"),
    (r"\bThe first round\b", "First reading"),
    # Funkce ve Sněmovně.
    (r"\bvice-presidential seat\b", "Deputy Speaker seat"),
    (r"\bvice-presidents\b", "Deputy Speakers"),
    (r"\bvice-president\b", "Deputy Speaker"),
    (r"\bvice president\b", "Deputy Speaker"),
    (r"\bvice-chairman's seat\b", "Deputy Speaker's seat"),
    (r"\bvice-chairman's\b", "Deputy Speaker's"),
    (r"\bvice-chairmen\b", "Deputy Speakers"),
    (r"\bvice-chairman\b", "Deputy Speaker"),
    (r"\bvice chairwoman\b", "Deputy Speaker"),
    (r"\bchairman's chair\b", "Speaker's chair"),
    (r"\brepresent the chairman in conducting meetings\b", "Deputy Speakers stand in for the Speaker when running meetings"),
    (r"\bThe chairman directs meetings\b", "The Speaker runs meetings"),
    (r"\bDear Mr\. Chairman\b", "Dear Mr. Speaker"),
    (r"\bswept off the table by the chairman\b", "swept off the table by the Speaker"),
    (r"\bthe chairman declared\b", "the Speaker declared"),
    (r"\bthe chairman did not read\b", "the Speaker did not read"),
    (r"\bTomio Okamura elected chairman\b", "Tomio Okamura elected Speaker"),
    (r"\bOkamura elected chairman\b", "Okamura elected Speaker"),
    (r"\belected Okamura as chairman\b", "elected Okamura as Speaker"),
    (r"\bfor Petr Fiala as chairman\b", "for Petr Fiala as Speaker"),
    (r"\bChairmen Tomio Okamura\b", "Speaker Tomio Okamura"),
    (r"\bthrough the chairman, Mrs\. Deputy Richterová\b", "through Deputy Speaker Richterová"),
    (r"\balso the chairman, MP\b", "also the committee chair, MP"),
    # Dávky a ÚP.
    (r"\bbatches\b", "benefits"),
    (r"\bBatches\b", "Benefits"),
    (r"\bLabor Office\b", "Labour Office"),
    (r"\bemployment offices\b", "Labour Offices"),
    (r"\bemployment office\b", "Labour Office"),
    # Instituce — vždy The Chamber of Deputies.
    (r"\bSpeaker of the Chamber\b(?! of Deputies)", "Speaker of the Chamber of Deputies"),
    (r"\bHouse of Representatives\b", "The Chamber of Deputies"),
    (r"\bthe House of Deputies\b", "The Chamber of Deputies"),
    (r"\bThe House of Deputies\b", "The Chamber of Deputies"),
    (r"\bthe Chamber of Deputies\b", "The Chamber of Deputies"),
    (r"\bChamber of Deputies\b", "The Chamber of Deputies"),
    (r"\bthe Chamber\b", "The Chamber of Deputies"),
    (r"\bThe Chamber\b(?! of Deputies)", "The Chamber of Deputies"),
    (r"\bThe The Chamber of Deputies\b", "The Chamber of Deputies"),
    (r"\bHouse approved\b", "The Chamber of Deputies approved"),
    (r"\bHouse rejected\b", "The Chamber of Deputies rejected"),
    (r"\bHouse stopped\b", "The Chamber of Deputies stopped"),
    (r"\bHouse overrode\b", "The Chamber of Deputies overrode"),
    (r"\bHouse adopted\b", "The Chamber of Deputies adopted"),
    (r"\bHouse began\b", "The Chamber of Deputies began"),
    (r"\bHouse occupied\b", "The Chamber of Deputies occupied"),
    (r"\bHouse passed\b", "The Chamber of Deputies passed"),
    (r"\bHouse distributed\b", "The Chamber of Deputies distributed"),
    (r"\bHouse did not\b", "The Chamber of Deputies did not"),
    (r"\bHouse will\b", "The Chamber of Deputies will"),
    (r"\bin the House\b", "in The Chamber of Deputies"),
    (r"\bto the House\b", "to The Chamber of Deputies"),
    (r"\bof the House\b", "of The Chamber of Deputies"),
    (r"\bHouse sends\b", "The Chamber of Deputies sends"),
    (r"\bHouse bodies\b", "bodies of The Chamber of Deputies"),
    (r"\bHouse Press\b", "Chamber document"),
    # Superdávka.
    (r"\bsuper dose\b", "super benefit"),
    (r"\bSuper dose\b", "Super benefit"),
    # Výbory.
    (r"\bnow awaits a round of committees\b", "now goes to committees"),
    (r"\bawaits a round of committees\b", "goes to committees"),
    (r"\bawaits a round after\b", "goes to"),
    (r"\bround of committees\b", "committee stage"),
    (r"\bthe round of committees\b", "the committee stage"),
    (r"\bnow now goes\b", "now goes"),
    # Nedůvěra.
    (r"\bMistrust fell\b", "No confidence failed"),
    (r"\bdistrust\b", "no confidence"),
    (r"\bDistrust\b", "No confidence"),
    # Stavební zákon — jednotně Construction Bill.
    (r"\bthe construction law\b", "the Construction Bill"),
    (r"\bconstruction law\b", "Construction Bill"),
    (r"\bthe building bill\b", "the Construction Bill"),
    (r"\bbuilding bill\b", "Construction Bill"),
    (r"\bbuilding law\b", "Construction Bill"),
    # Rada ČT.
    (r"\bCT Council\b", "Czech Television Council"),
    (r"\bCT Board\b", "Czech Television Council"),
]

_EET_FIRST = re.compile(r"\bEET\b(?!\s*\(electronic sales records\)|-)")
_INTERPELLATION_FIRST = re.compile(
    r"\binterpellations?\b(?!\s*\(parliamentary Q&A)"
)


def _expand_first_eet(text: str, *, done: list[bool]) -> str:
    if done[0]:
        return text
    if re.search(r"\bEET\s*\(electronic sales records\)", text):
        done[0] = True
        return text
    m = _EET_FIRST.search(text)
    if not m:
        return text
    done[0] = True
    return text[: m.start()] + "EET (electronic sales records)" + text[m.end() :]


def _expand_first_interpellation(text: str, *, done: list[bool]) -> str:
    if done[0]:
        return text
    if re.search(r"\binterpellations?\s*\(parliamentary Q&A", text):
        done[0] = True
        return text
    m = _INTERPELLATION_FIRST.search(text)
    if not m:
        return text
    done[0] = True
    word = m.group(0)
    if word.endswith("s"):
        repl = "interpellations (parliamentary Q&A sessions)"
    else:
        repl = "interpellation (parliamentary Q&A session)"
    return text[: m.start()] + repl + text[m.end() :]


def _expand_first_occurrences(obj: object) -> object:
    eet_done = [False]
    interp_done = [False]

    def walk(o: object) -> object:
        if isinstance(o, str):
            s = _expand_first_eet(o, done=eet_done)
            return _expand_first_interpellation(s, done=interp_done)
        if isinstance(o, list):
            return [walk(x) for x in o]
        if isinstance(o, dict):
            return {k: walk(v) for k, v in o.items()}
        return o

    return walk(obj)


def _apply(text: str) -> str:
    out = text
    for old, new in _EXACT:
        out = out.replace(old, new)
    for pattern, repl in _REGEX:
        out = re.sub(pattern, repl, out)
    # Volby: obnovit kolo, které regex pro čtení omylem přepíše.
    out = re.sub(
        r"\bsecond reading of the (secret )?election\b",
        r"second round of the \1election",
        out,
        flags=re.IGNORECASE,
    )
    out = re.sub(
        r"\bat second reading of the secret election\b",
        "in the second round of the secret election",
        out,
        flags=re.IGNORECASE,
    )
    out = re.sub(
        r"\bfailed at second reading of the secret election\b",
        "failed in the second round of the secret election",
        out,
        flags=re.IGNORECASE,
    )
    return out


def _walk(obj: object) -> object:
    if isinstance(obj, str):
        return _apply(obj)
    if isinstance(obj, list):
        return [_walk(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _walk(v) for k, v in obj.items()}
    return obj


def apply_en_terminology(obj: object) -> object:
    """Apply parliamentary terminology fixes to an ``en`` block."""
    return _expand_first_occurrences(_walk(obj))


def fix_file(path: Path, *, dry_run: bool = False) -> bool:
    data = read_json(path)
    en = data.get("en")
    if not isinstance(en, dict) or not en:
        return False
    new_en = apply_en_terminology(en)
    if new_en == en:
        return False
    if not dry_run:
        data["en"] = new_en
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--facts-root", type=Path, default=ROOT / "processed")
    args = parser.parse_args()

    changed = 0
    for path in sorted(args.facts_root.glob("2025-s*/facts/**/*.json")):
        if fix_file(path, dry_run=args.dry_run):
            changed += 1
            print(f"{'~' if args.dry_run else '✓'} {path.relative_to(ROOT)}")
    print(json.dumps({"changed": changed, "dry_run": args.dry_run}))


if __name__ == "__main__":
    main()
