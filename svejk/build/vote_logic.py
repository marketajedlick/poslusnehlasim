"""Sdílená logika pro vyhodnocení témat a hlasování."""

from __future__ import annotations

from svejk.noviny import _law_kategorie
from svejk.timeline import BlokDne


def vote_kategorie(nazev: str) -> str:
    blok = BlokDne(
        cas_od="",
        cas_do="",
        typ="law",
        svejk="",
        nazev=nazev,
    )
    return _law_kategorie(blok)


def topic_proslo_druhe_cteni_ukonceno(steno_texts: list[str]) -> bool:
    """Druhé čtení skončilo bez zamítnutí celého návrhu (posun k třetímu čtení)."""
    joined = "\n".join(steno_texts).lower()
    if "končím tedy druhé čtení" not in joined:
        return False
    if "návrh na vrácení zákona garančnímu výboru" in joined:
        return True
    if "nepadly žádné návrhy, o kterých by se mělo hlasovat" in joined:
        return True
    return False


def topic_proslo_from_votes(group: list[dict]) -> bool:
    """Prošlo, pokud existuje rozhodující A (pro > proti); u maratonů přerušení ne."""
    group = sorted(group, key=lambda v: (v.get("datum", ""), v.get("cas", "")))
    if not group:
        return False
    prijato = sum(1 for v in group if v.get("vysledek") == "A")
    zamitnuto = sum(1 for v in group if v.get("vysledek") == "R")
    decisive = [
        v
        for v in group
        if v.get("vysledek") == "A" and (v.get("pro") or 0) > (v.get("proti") or 0)
    ]
    if not decisive:
        return False
    if prijato <= 2 and zamitnuto >= max(10, prijato * 5):
        return False
    return True


def spor_o_porad_schuze(day_votes: list[dict]) -> bool:
    """True, pokud hlasování o pořadu vypadá jako výrazný spor (ne jen rutina)."""
    porad = [v for v in day_votes if v.get("je_porad_schuze")]
    if not porad:
        return False
    if max(v.get("proti", 0) for v in porad) >= 40:
        return True
    if len(porad) >= 3:
        return True
    times = sorted({v.get("cas", "")[:5] for v in porad if v.get("cas")})
    if len(times) >= 2:
        sh, sm = int(times[0][:2]), int(times[0][3:5])
        eh, em = int(times[-1][:2]), int(times[-1][3:5])
        if (eh * 60 + em) - (sh * 60 + sm) >= 20:
            return True
    return False


def debata_vysledek_radek(stats: dict) -> str:
    """Třetí odrážka ve Výsledku dne podle délky debaty a sporu o pořadu."""
    if stats.get("spor_o_porad"):
        return "* nejdřív se dlouho hádali o pořadu dne"
    if stats.get("dlouha_debata"):
        minuty = int(stats.get("minuty") or 0)
        if minuty >= 240:
            return "* celé odpoledne se mluvilo o jednom bodu"
        return "* dlouhá debata u jednoho bodu"
    return "* nikdo se nepohádal tak, aby to stálo za zmínku"
