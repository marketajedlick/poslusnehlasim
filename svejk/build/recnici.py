"""Samostatná stránka s tabulkou „Kdo kolik mluvil“ (obsahové projevy dne)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from svejk.build.io import read_json
from svejk.build.nav import recnici_pages_href
from svejk.strings import load_strings
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
) -> str:
    if link_mode == "pages":
        return recnici_pages_href(obdobi, schuze, datum_unl, base_path)
    d = datetime.strptime(datum_unl, "%d.%m.%Y")
    return f"{d.strftime('%Y-%m-%d')}-recnici.html"


def _strings() -> dict[str, Any]:
    base = dict(_PAGE_FALLBACK_CS)
    override = load_strings().get("recnici") or {}
    base.update({k: v for k, v in override.items() if isinstance(v, str) and v.strip()})
    return base


def recnici_datum_label(datum_unl: str) -> str:
    d = datetime.strptime(datum_unl, "%d.%m.%Y")
    return f"{d.day}. {d.month}. {d.year}"


def _localized_rows(data: dict[str, Any]) -> list[dict[str, Any]]:
    rows = data.get("radky") or []
    return [dict(r) for r in rows if isinstance(r, dict)]


def recnici_rows(data: dict[str, Any]) -> list[dict[str, str]]:
    rows = _localized_rows(data)
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
) -> dict[str, str]:
    s = _strings()
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
        )
        out.append((label, href))
    return out
