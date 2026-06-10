"""Doplní za jména poslanců stranu v závorce."""

from __future__ import annotations

from psp.poslanci import PoslanecRegistry, poslanec_registry


def dopln_strany_poslancu(text: str) -> str:
    """Richterová -> Richterová (Piráti); existující závorky nechá být."""
    if not (text or "").strip():
        return text
    return poslanec_registry().annotate(text)
