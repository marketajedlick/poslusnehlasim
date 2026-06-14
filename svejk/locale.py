"""Lokalizace UI webu (fáze 1: český obsah, anglický obal)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

DEFAULT_LOCALE = "cs"
SUPPORTED_LOCALES = ("cs", "en")

_LOCALE_DIR = Path(__file__).resolve().parent / "locale"

_MESICE_CS = (
    "leden",
    "únor",
    "březen",
    "duben",
    "květen",
    "červen",
    "červenec",
    "srpen",
    "září",
    "říjen",
    "listopad",
    "prosinec",
)

_MESICE_EN = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


def normalize_locale(locale: str | None) -> str:
    if locale and locale.lower() in SUPPORTED_LOCALES:
        return locale.lower()
    return DEFAULT_LOCALE


def locale_prefix(locale: str = DEFAULT_LOCALE) -> str:
    return "/en" if normalize_locale(locale) == "en" else ""


def localized_path(path: str, locale: str = DEFAULT_LOCALE) -> str:
    """Přidá /en před cestu (kromě výchozí češtiny)."""
    loc = normalize_locale(locale)
    if loc == DEFAULT_LOCALE:
        return path
    if path == "/":
        return "/en/"
    if path.startswith("/en/"):
        return path
    return f"/en{path}"


def alternate_locale(locale: str) -> str:
    return "en" if normalize_locale(locale) == DEFAULT_LOCALE else DEFAULT_LOCALE


def locale_switch_href(
    page_path: str,
    current_locale: str,
    base_path: str = "",
) -> str:
    """URL stejné stránky v druhém jazyce."""
    base = base_path.rstrip("/")
    clean = page_path
    if base and clean.startswith(base):
        clean = clean[len(base) :]
    if clean.startswith("/en/"):
        clean = clean[3:]
    elif clean == "/en" or clean == "/en/":
        clean = "/"
    target = alternate_locale(current_locale)
    if target == "en":
        switched = "/en/" if clean in ("", "/") else localized_path(clean, "en")
    else:
        switched = clean if clean not in ("", "/") else "/"
    return f"{base}{switched}" if base else switched


def month_label(month: int, year: int, locale: str = DEFAULT_LOCALE) -> str:
    names = _MESICE_EN if normalize_locale(locale) == "en" else _MESICE_CS
    return f"{names[month - 1]} {year}"


def og_locale_tag(locale: str) -> str:
    return "en_US" if normalize_locale(locale) == "en" else "cs_CZ"


@lru_cache(maxsize=4)
def load_strings(locale: str) -> dict[str, Any]:
    loc = normalize_locale(locale)
    path = _LOCALE_DIR / f"{loc}.json"
    if not path.is_file():
        path = _LOCALE_DIR / f"{DEFAULT_LOCALE}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def footer_closings(locale: str) -> tuple[str, ...]:
    t = load_strings(locale)
    closings = t.get("footer", {}).get("closings")
    if isinstance(closings, list) and closings:
        return tuple(str(x) for x in closings)
    return (
        "Poslušně hlásím, že dnešní vydání končí. Poslanci šli domů a my taky.",
    )


def footer_stats_line(
    n_editions: int,
    schuze_part: str,
    locale: str = DEFAULT_LOCALE,
) -> str:
    t = load_strings(locale)
    template = t.get("footer", {}).get("stats", "{editions} vydání • {schuze} • 100 % veřejná data")
    return template.format(editions=n_editions, schuze=schuze_part)


def schuze_count_label(n_schuze: int, locale: str = DEFAULT_LOCALE) -> str:
    loc = normalize_locale(locale)
    if loc == "en":
        return "1 session" if n_schuze == 1 else f"{n_schuze} sessions"
    if n_schuze == 1:
        return "1 schůze"
    if 2 <= n_schuze <= 4:
        return f"{n_schuze} schůze"
    return f"{n_schuze} schůzí"


def hreflang_links(
    page_path: str,
    site_url: str,
    base_path: str = "",
) -> list[dict[str, str]]:
    """Alternativní jazykové verze pro <link rel=\"alternate\" hreflang>."""
    site = site_url.rstrip("/")
    base = base_path.rstrip("/")
    clean = page_path
    if base and clean.startswith(base):
        clean = clean[len(base) :]
    if clean.startswith("/en/"):
        clean = clean[3:]
    elif clean in ("/en", "/en/"):
        clean = "/"
    cs_path = clean if clean not in ("", "/") else "/"
    en_path = localized_path(clean if clean not in ("", "/") else "/", "en")
    prefix = base
    return [
        {"hreflang": "cs", "href": f"{site}{prefix}{cs_path}"},
        {"hreflang": "en", "href": f"{site}{prefix}{en_path}"},
        {"hreflang": "x-default", "href": f"{site}{prefix}{cs_path}"},
    ]
