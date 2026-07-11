"""Jednací den vs. kalendářní datum PSP.

PSP u hlasování po půlnoci posune kalendářní datum. Pro vydání novin
počítáme jednací den: noční hodiny (00:00–05:59) patří k předchozímu dni.
"""

from __future__ import annotations

from datetime import datetime, timedelta

# ponytail: fixní práh místo prvního pořadu ráno — upgrade: je_porad_schuze v 6–12 h
JEDNACI_NOC_DO_HOD = 6


def _parse_datum_cas(datum: str, cas: str = "") -> datetime | None:
    datum = (datum or "").strip()
    if not datum:
        return None
    try:
        d = datetime.strptime(datum[:10], "%d.%m.%Y")
    except ValueError:
        return None
    cas = (cas or "").strip()
    if len(cas) >= 5 and cas[2] == ":":
        try:
            h, m = int(cas[:2]), int(cas[3:5])
            return d.replace(hour=h, minute=m)
        except ValueError:
            pass
    return d


def je_noc_po_pulnoci(cas: str) -> bool:
    cas = (cas or "").strip()
    if len(cas) < 5 or cas[2] != ":":
        return False
    try:
        h = int(cas[:2])
    except ValueError:
        return False
    return 0 <= h < JEDNACI_NOC_DO_HOD


def jednaci_datum(datum: str, cas: str = "") -> str:
    """Kalendářní datum PSP → jednací den (DD.MM.YYYY)."""
    dt = _parse_datum_cas(datum, cas)
    if dt is None:
        return (datum or "").strip()
    if je_noc_po_pulnoci(cas):
        return (dt - timedelta(days=1)).strftime("%d.%m.%Y")
    return dt.strftime("%d.%m.%Y")


def vote_jednaci_datum(vote: dict) -> str:
    return jednaci_datum(vote.get("datum") or "", vote.get("cas") or "")


def vote_belongs_to_jednaci_den(vote: dict, jednaci_unl: str) -> bool:
    return vote_jednaci_datum(vote) == jednaci_unl


def vote_chrono_key(vote: dict) -> tuple[datetime, int]:
    dt = _parse_datum_cas(vote.get("datum") or "", vote.get("cas") or "")
    cislo = int(vote.get("cislo") or 0)
    return (dt or datetime.min, cislo)


def jednaci_den_minuty(votes: list[dict]) -> int:
    if not votes:
        return 0
    ordered = sorted(votes, key=vote_chrono_key)
    start = _parse_datum_cas(ordered[0].get("datum", ""), ordered[0].get("cas", ""))
    end = _parse_datum_cas(ordered[-1].get("datum", ""), ordered[-1].get("cas", ""))
    if start is None or end is None:
        return 0
    return max(0, int((end - start).total_seconds() // 60))


def calendar_isos_for_jednaci_den(jednaci_unl: str) -> set[str]:
    """Kalendářní ISO data pro párování stena s jednacím dnem."""
    d = datetime.strptime(jednaci_unl, "%d.%m.%Y")
    return {
        d.strftime("%Y-%m-%d"),
        (d + timedelta(days=1)).strftime("%Y-%m-%d"),
    }


def steno_iso_patří_k_jednacímu_dni(steno_datum: str, jednaci_unl: str) -> bool:
    return (steno_datum or "")[:10] in calendar_isos_for_jednaci_den(jednaci_unl)
