"""Navigace mezi vydáními — chronologicky přes celé období."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from svejk.build.day_content import datum_design
from svejk.build.io import read_json
from svejk.paths import SchuzePaths, processed_root
from svejk.timeline import den_v_tydnu


@dataclass(frozen=True)
class EditionLink:
    href: str
    label: str
    title: str


@dataclass(frozen=True)
class EditionNav:
    prev: EditionLink | None
    next: EditionLink | None


@dataclass(frozen=True)
class Edition:
    obdobi: int
    schuze: int
    datum_unl: str
    when: datetime


def _schuze_dirs(obdobi: int) -> list[tuple[int, Path]]:
    root = processed_root()
    out: list[tuple[int, Path]] = []
    for p in root.glob(f"{obdobi}-s*"):
        if not p.is_dir():
            continue
        try:
            cislo = int(p.name.split("-s", 1)[1])
        except ValueError:
            continue
        out.append((cislo, p))
    return sorted(out, key=lambda x: x[0])


@lru_cache(maxsize=8)
def list_obdobi_editions(obdobi: int) -> tuple[Edition, ...]:
    """Všechna vydání v období seřazená podle kalendářního data."""
    editions: list[Edition] = []
    for schuze, _ in _schuze_dirs(obdobi):
        paths = SchuzePaths.create(obdobi, schuze)
        if not paths.facts_by_day.is_dir():
            continue
        for day_path in paths.facts_by_day.glob("*.json"):
            day = read_json(day_path)
            datum = day.get("datum")
            if not datum:
                continue
            when = datetime.strptime(datum, "%d.%m.%Y")
            editions.append(Edition(obdobi=obdobi, schuze=schuze, datum_unl=datum, when=when))
    editions.sort(key=lambda e: (e.when, e.schuze))
    return tuple(editions)


def _editions_on_day(editions: tuple[Edition, ...], datum_unl: str) -> tuple[Edition, ...]:
    return tuple(e for e in editions if e.datum_unl == datum_unl)


def edition_web_href(obdobi: int, schuze: int, datum_unl: str) -> str:
    return f"/noviny/{obdobi}/{schuze}/{datum_unl}"


def edition_pages_href(
    obdobi: int,
    schuze: int,
    datum_unl: str,
    base_path: str = "",
) -> str:
    """Statická URL pro GitHub Pages (soubor .html)."""
    base = base_path.rstrip("/")
    path = f"/noviny/{obdobi}/{schuze}/{datum_unl}.html"
    return f"{base}{path}" if base else path


def resolve_edition(obdobi: int, datum_unl: str, schuze: int | None = None) -> Edition | None:
    matches = _editions_on_day(list_obdobi_editions(obdobi), datum_unl)
    if not matches:
        return None
    if schuze is not None:
        for e in matches:
            if e.schuze == schuze:
                return e
        return None
    if len(matches) == 1:
        return matches[0]
    return matches[-1]


def _den_z_index(paths: SchuzePaths, datum_unl: str) -> str:
    d = datetime.strptime(datum_unl, "%d.%m.%Y")
    day_path = paths.facts_by_day / f"{d.strftime('%Y-%m-%d')}.json"
    if day_path.is_file():
        return read_json(day_path).get("den") or den_v_tydnu(datum_unl)
    return den_v_tydnu(datum_unl)


def _link_label(edition: Edition, editions: tuple[Edition, ...]) -> str:
    d = datetime.strptime(edition.datum_unl, "%d.%m.%Y")
    base = f"{d.day:02d} / {d.month:02d}"
    if len(_editions_on_day(editions, edition.datum_unl)) > 1:
        return f"{base} · s{edition.schuze}"
    return base


def _make_link(
    edition: Edition,
    editions: tuple[Edition, ...],
    *,
    link_mode: str,
    from_paths: SchuzePaths,
    from_datum: str,
    base_path: str = "",
) -> EditionLink:
    target_paths = SchuzePaths.create(edition.obdobi, edition.schuze)
    den = _den_z_index(target_paths, edition.datum_unl)
    if link_mode == "web":
        href = edition_web_href(edition.obdobi, edition.schuze, edition.datum_unl)
    elif link_mode == "pages":
        href = edition_pages_href(edition.obdobi, edition.schuze, edition.datum_unl, base_path)
    else:
        from_file = from_paths.noviny_dlouhe_html(from_datum)
        to_file = target_paths.noviny_dlouhe_html(edition.datum_unl)
        href = Path(os.path.relpath(to_file, from_file.parent)).as_posix()
    title = datum_design(edition.datum_unl, den)
    if len(_editions_on_day(editions, edition.datum_unl)) > 1:
        title = f"{title} · schůze {edition.schuze}"
    return EditionLink(
        href=href,
        label=_link_label(edition, editions),
        title=title,
    )


def edition_nav(
    paths: SchuzePaths,
    datum_unl: str,
    *,
    link_mode: str = "file",
    obdobi: int | None = None,
    base_path: str = "",
) -> EditionNav:
    ob = obdobi if obdobi is not None else paths.obdobi
    editions = list_obdobi_editions(ob)
    idx = next(
        (i for i, e in enumerate(editions) if e.schuze == paths.schuze and e.datum_unl == datum_unl),
        None,
    )
    if idx is None:
        return EditionNav(None, None)

    kw = {
        "editions": editions,
        "link_mode": link_mode,
        "from_paths": paths,
        "from_datum": datum_unl,
        "base_path": base_path,
    }
    prev = _make_link(editions[idx - 1], **kw) if idx > 0 else None
    nxt = _make_link(editions[idx + 1], **kw) if idx < len(editions) - 1 else None
    return EditionNav(prev, nxt)


def clear_edition_cache() -> None:
    list_obdobi_editions.cache_clear()
