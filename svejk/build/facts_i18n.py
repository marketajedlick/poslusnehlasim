"""Výběr lokalizovaných polí z facts JSON (blok ``en``)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from svejk.locale import normalize_locale

_TOPIC_FIELDS = (
    "nadpis",
    "lead",
    "pointa",
    "mean",
    "kuriozita",
    "predmet_lidsky",
)
_DAY_FIELDS = ("dnesni_ucet", "zaver", "result_note", "den")
_LIST_FIELDS = ("koho", "vysledek")


def _en_block(data: dict[str, Any]) -> dict[str, Any]:
    en = data.get("en")
    return en if isinstance(en, dict) else {}


def pick_field(data: dict[str, Any], field: str, locale: str = "cs") -> str:
    loc = normalize_locale(locale)
    if loc == "en":
        val = (_en_block(data).get(field) or "").strip()
        if val:
            return val
    return (data.get(field) or "").strip()


def pick_list(data: dict[str, Any], field: str, locale: str = "cs") -> list[str]:
    loc = normalize_locale(locale)
    if loc == "en":
        en_val = _en_block(data).get(field)
        if isinstance(en_val, list) and en_val:
            return [str(x) for x in en_val]
    raw = data.get(field)
    if isinstance(raw, list):
        return [str(x) for x in raw]
    return []


def localized_fakty(fact: dict[str, Any], locale: str = "cs") -> list[dict[str, Any]]:
    base = fact.get("fakty") or []
    loc = normalize_locale(locale)
    if loc != "en":
        return list(base)
    en_fakty = _en_block(fact).get("fakty")
    if not isinstance(en_fakty, list) or not en_fakty:
        return list(base)
    out: list[dict[str, Any]] = []
    for i, row in enumerate(base):
        merged = dict(row)
        if i < len(en_fakty) and isinstance(en_fakty[i], dict):
            en_row = en_fakty[i]
            if (en_row.get("text") or "").strip():
                merged["text"] = en_row["text"]
            if (en_row.get("citace") or "").strip():
                merged["citace"] = en_row["citace"]
        out.append(merged)
    return out


def localized_mean_links(fact: dict[str, Any], locale: str = "cs") -> list[tuple[str, str]]:
    loc = normalize_locale(locale)
    links: list[tuple[str, str]] = []
    source = _en_block(fact).get("mean_links") if loc == "en" else None
    if not source:
        source = fact.get("mean_links") or []
    for entry in source:
        if not isinstance(entry, dict):
            continue
        phrase = (entry.get("phrase") or "").strip()
        page = (entry.get("page") or "").strip()
        if phrase and page:
            links.append((phrase, page))
    if loc == "en" and links:
        return links
    legacy = fact.get("mean_link") or {}
    legacy_phrase = (legacy.get("phrase") or "").strip()
    legacy_page = (legacy.get("page") or "neprosli").strip()
    if legacy_phrase and not any(p == legacy_phrase for p, _ in links):
        links.append((legacy_phrase, legacy_page))
    return links


def localized_kuriozita_links(fact: dict[str, Any], locale: str = "cs") -> list[tuple[str, str]]:
    loc = normalize_locale(locale)
    source = _en_block(fact).get("kuriozita_links") if loc == "en" else None
    if not source:
        source = fact.get("kuriozita_links") or []
    out: list[tuple[str, str]] = []
    for entry in source:
        if not isinstance(entry, dict):
            continue
        label = (entry.get("label") or "").strip()
        page = (entry.get("page") or "").strip()
        if label and page:
            out.append((label, page))
    return out


def localized_fact(fact: dict[str, Any], locale: str = "cs") -> dict[str, Any]:
    """Kopie topic faktu s anglickými poli, pokud existují."""
    loc = normalize_locale(locale)
    if loc != "en" or not _en_block(fact):
        return fact
    out = deepcopy(fact)
    en = _en_block(fact)
    for key in _TOPIC_FIELDS:
        if (en.get(key) or "").strip():
            out[key] = en[key]
    if en.get("koho"):
        out["koho"] = en["koho"]
    if en.get("fakty"):
        out["fakty"] = localized_fakty(fact, loc)
    if en.get("kick"):
        out["_kick_en"] = en["kick"]
    return out


def localized_day(day: dict[str, Any], locale: str = "cs") -> dict[str, Any]:
    loc = normalize_locale(locale)
    if loc != "en" or not _en_block(day):
        return day
    out = deepcopy(day)
    en = _en_block(day)
    for key in _DAY_FIELDS:
        if (en.get(key) or "").strip():
            out[key] = en[key]
    if en.get("vysledek"):
        out["vysledek"] = en["vysledek"]
    return out


def has_en_translation(data: dict[str, Any]) -> bool:
    en = _en_block(data)
    if not en:
        return False
    for key in _TOPIC_FIELDS + _DAY_FIELDS:
        if (en.get(key) or "").strip():
            return True
    if en.get("vysledek") or en.get("koho") or en.get("fakty"):
        return True
    return False


def topic_needs_translation(fact: dict[str, Any]) -> bool:
    if not fact.get("publikovat"):
        return False
    if has_en_translation(fact):
        return False
    return bool((fact.get("nadpis") or fact.get("lead") or "").strip())


def day_needs_translation(day: dict[str, Any]) -> bool:
    if has_en_translation(day):
        return False
    return bool((day.get("dnesni_ucet") or day.get("zaver") or "").strip())
