"""Sloučení automatické kostry facts s ruční prací redakce.

Pravidlo: když je soubor ručně upravený, vyhrává existující obsah. Automatika
jen doplní chybějící klíče a obnoví čistě datová pole (počty, signály).
Dřív se brala čerstvá kostra a z ruční práce se přenesl jen whitelist, takže
opakovaný extract / edition brief tiše mazal jazykolam, slovníček, citace2…,
pointa_tail, steno_id a ruční verdikt.
"""

from __future__ import annotations

from typing import Any

# Pole odvozená z dat, která se při každém běhu obnoví.
AUTO_TOPIC_KEYS = frozenset(
    {"slug", "nazev", "datum", "pocet_hlasovani", "signaly", "steno_slov", "priorita"}
)
AUTO_DAY_KEYS = frozenset({"datum", "den", "stats"})

_EMPTY = (None, "", [], {})


def _is_empty(value: Any) -> bool:
    return any(value is e or (type(value) is type(e) and value == e) for e in _EMPTY)


def topic_manually_edited(existing: dict[str, Any]) -> bool:
    if any(existing.get(k) for k in ("lead", "pointa", "mean", "citace_text")):
        return True
    fakty = [f for f in existing.get("fakty") or [] if isinstance(f, dict)]
    if any(f.get("source") in ("votes", "manual") or f.get("link_phrase") for f in fakty):
        return True
    nadpis = (existing.get("nadpis") or "").strip()
    if nadpis and nadpis not in ("Prošlo to", "Prošlo"):
        return True
    return False


def day_manually_edited(existing: dict[str, Any]) -> bool:
    return any(
        existing.get(k)
        for k in (
            "dnesni_ucet",
            "zaver",
            "vysledek",
            "nwl_predmet",
            "jazykolam",
            "slovnicek",
            "board_left_label",
            "board_right_label",
            "skore_manual",
        )
    )


def _overlay(existing: dict[str, Any], fresh: dict[str, Any], auto: frozenset[str]) -> dict[str, Any]:
    out = dict(fresh)
    for key, value in existing.items():
        if key in auto:
            continue
        if _is_empty(value) and key in fresh:
            continue
        out[key] = value
    return out


def merge_topic(existing: dict[str, Any], fresh: dict[str, Any]) -> dict[str, Any]:
    if not existing or not topic_manually_edited(existing):
        return fresh
    return _overlay(existing, fresh, AUTO_TOPIC_KEYS)


def merge_day(existing: dict[str, Any], fresh: dict[str, Any]) -> dict[str, Any]:
    if not existing or not day_manually_edited(existing):
        return fresh
    out = _overlay(existing, fresh, AUTO_DAY_KEYS)
    if existing.get("skore_manual") and isinstance(existing.get("stats"), dict):
        stats = dict(out.get("stats") or {})
        for key in ("proslo", "zamitnuto"):
            if key in existing["stats"]:
                stats[key] = existing["stats"][key]
        out["stats"] = stats
    return out
