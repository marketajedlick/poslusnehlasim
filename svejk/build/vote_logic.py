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
