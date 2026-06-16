"""Samostatná stránka s tabulkou „Kdo kolik mluvil“ (obsahové projevy dne)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from svejk.build.io import read_json
from svejk.build.nav import recnici_pages_href
from svejk.locale import load_strings, month_label, normalize_locale
from svejk.paths import SchuzePaths

_PAGE_FALLBACK_CS = {
    "title": "Kdo kolik mluvil",
    "gloss": (
        "Obsahové projevy z mimořádné schůze {datum}, seřazené podle počtu slov. "
        "Procedurální a krátké vstupy předsedajícího se nepočítají."
    ),
    "note": (
        "Délka projevu není totéž co síla argumentu. Hodnota „~“ u Martina Kupky "
        "je součet tří vystoupení."
    ),
    "table_speaker": "Řečník",
    "table_words": "Slov",
    "table_role": "Strana / role",
    "back_to_edition": "← Zpět na vydání {date}",
}

_PAGE_FALLBACK_EN = {
    "title": "Who spoke how much",
    "gloss": (
        "Substantive speeches from the extraordinary session on {datum}, ranked by word count. "
        "Procedural and short chair interventions are not counted."
    ),
    "note": (
        "Length of a speech is not the same as the strength of an argument. The \"~\" value "
        "next to Martin Kupka is the sum of three speeches."
    ),
    "table_speaker": "Speaker",
    "table_words": "Words",
    "table_role": "Party / role",
    "back_to_edition": "← Back to edition {date}",
}


def recnici_json_path(paths: SchuzePaths, datum_unl: str) -> Path:
    d = datetime.strptime(datum_unl, "%d.%m.%Y")
    return paths.facts / f"recnici-{d.strftime('%Y-%m-%d')}.json"


def load_recnici(paths: SchuzePaths, datum_unl: str) -> dict[str, Any] | None:
    fp = recnici_json_path(paths, datum_unl)
    if not fp.is_file():
        return None
    return read_json(fp)


def has_recnici(paths: SchuzePaths, datum_unl: str) -> bool:
    data = load_recnici(paths, datum_unl)
    return bool(data and data.get("radky"))


def recnici_href(
    obdobi: int,
    schuze: int,
    datum_unl: str,
    *,
    link_mode: str,
    base_path: str = "",
    locale: str = "cs",
) -> str:
    if link_mode == "pages":
        return recnici_pages_href(obdobi, schuze, datum_unl, base_path, locale)
    d = datetime.strptime(datum_unl, "%d.%m.%Y")
    return f"{d.strftime('%Y-%m-%d')}-recnici.html"


def _strings(locale: str = "cs") -> dict[str, Any]:
    loc = normalize_locale(locale)
    base = dict(_PAGE_FALLBACK_EN if loc == "en" else _PAGE_FALLBACK_CS)
    override = load_strings(loc).get("recnici") or {}
    base.update({k: v for k, v in override.items() if isinstance(v, str) and v.strip()})
    return base


def recnici_datum_label(datum_unl: str, locale: str = "cs") -> str:
    d = datetime.strptime(datum_unl, "%d.%m.%Y")
    if normalize_locale(locale) == "en":
        return f"{d.day} {month_label(d.month, d.year, 'en')}"
    return f"{d.day}. {d.month}. {d.year}"


def _localized_rows(data: dict[str, Any], locale: str) -> list[dict[str, Any]]:
    loc = normalize_locale(locale)
    rows = data.get("radky") or []
    if loc != "en":
        return [dict(r) for r in rows if isinstance(r, dict)]
    en_by_name: dict[str, dict[str, Any]] = {}
    for r in (data.get("en") or {}).get("radky") or []:
        if isinstance(r, dict) and (r.get("jmeno") or "").strip():
            en_by_name[str(r["jmeno"]).strip()] = r
    out: list[dict[str, Any]] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        merged = dict(r)
        en_row = en_by_name.get(str(r.get("jmeno") or "").strip())
        if en_row:
            for key in ("role", "pozn"):
                if (en_row.get(key) or "").strip():
                    merged[key] = en_row[key]
        out.append(merged)
    return out


def recnici_rows(data: dict[str, Any], *, locale: str = "cs") -> list[dict[str, str]]:
    rows = _localized_rows(data, locale)
    rows.sort(key=lambda r: -int(r.get("slov") or 0))
    out: list[dict[str, str]] = []
    for r in rows:
        slov = int(r.get("slov") or 0)
        slov_label = f"~{slov}" if r.get("pribl") else str(slov)
        out.append(
            {
                "jmeno": str(r.get("jmeno") or "").strip(),
                "slov": slov_label,
                "role": str(r.get("role") or "").strip(),
                "pozn": str(r.get("pozn") or "").strip(),
            }
        )
    return out


def recnici_page_meta(
    data: dict[str, Any],
    *,
    datum_label: str,
    locale: str = "cs",
) -> dict[str, str]:
    s = _strings(locale)
    return {
        "title": s["title"],
        "gloss": s["gloss"].format(datum=datum_label, date=datum_label),
        "note": s["note"],
        "table_speaker": s["table_speaker"],
        "table_words": s["table_words"],
        "table_role": s["table_role"],
        "back_to_edition": s["back_to_edition"],
    }


def resolve_recnici_page_links(
    paths: SchuzePaths,
    datum_unl: str,
    links: list[tuple[str, str]],
    *,
    obdobi: int,
    schuze: int,
    link_mode: str,
    base_path: str = "",
    locale: str = "cs",
) -> list[tuple[str, str]]:
    """Přeloží (popisek, "recnici") na (popisek, href), jen když data existují."""
    out: list[tuple[str, str]] = []
    if not has_recnici(paths, datum_unl):
        return out
    for label, page in links:
        if page != "recnici":
            continue
        href = recnici_href(
            obdobi,
            schuze,
            datum_unl,
            link_mode=link_mode,
            base_path=base_path,
            locale=locale,
        )
        out.append((label, href))
    return out
