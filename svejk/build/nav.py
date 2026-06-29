"""Navigace mezi vydáními, chronologicky přes celé období."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from itertools import groupby
from pathlib import Path

from svejk.build.day_content import datum_design
from svejk.build.io import read_json
from svejk.paths import SchuzePaths, processed_root

from svejk.build.publish import list_site_editions
from svejk.strings import load_strings, month_label
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
class ArchiveChip:
    href: str
    day_label: str
    schuze_suffix: str
    is_current: bool
    title: str
    headline: str
    date_label: str
    schuze: int


@dataclass(frozen=True)
class ArchiveMonth:
    label: str
    chips: tuple[ArchiveChip, ...]


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


def archiv_pages_href(base_path: str = "") -> str:
    base = base_path.rstrip("/")
    path = "/archiv.html"
    return f"{base}{path}" if base else path


def o_webu_pages_href(base_path: str = "") -> str:
    base = base_path.rstrip("/")
    path = "/o-webu/"
    return f"{base}{path}" if base else path


def slovnicek_pages_href(base_path: str = "") -> str:
    base = base_path.rstrip("/")
    path = "/slovnicek.html"
    return f"{base}{path}" if base else path


def pivo_pages_href(base_path: str = "") -> str:
    base = base_path.rstrip("/")
    path = "/pivo.html"
    return f"{base}{path}" if base else path


def soukromi_pages_href(base_path: str = "") -> str:
    base = base_path.rstrip("/")
    path = "/soukromi/"
    return f"{base}{path}" if base else path


def podpora_pages_href(base_path: str = "") -> str:
    base = base_path.rstrip("/")
    path = "/podpora/"
    return f"{base}{path}" if base else path


def podminky_pages_href(base_path: str = "") -> str:
    base = base_path.rstrip("/")
    path = "/podminky/"
    return f"{base}{path}" if base else path


def dekuju_pages_href(base_path: str = "") -> str:
    base = base_path.rstrip("/")
    path = "/dekuju.html"
    return f"{base}{path}" if base else path


def vyznamenani_pages_href(
    obdobi: int,
    schuze: int,
    datum_unl: str,
    kind: str,
    base_path: str = "",
) -> str:
    base = base_path.rstrip("/")
    path = f"/noviny/{obdobi}/{schuze}/{datum_unl}-{kind}.html"
    return f"{base}{path}" if base else path


def steno_sources_pages_href(
    obdobi: int,
    schuze: int,
    datum_unl: str,
    base_path: str = "",
) -> str:
    base = base_path.rstrip("/")
    path = f"/noviny/{obdobi}/{schuze}/{datum_unl}-steno.html"
    return f"{base}{path}" if base else path


def smlouvy_pages_href(
    obdobi: int,
    schuze: int,
    datum_unl: str,
    base_path: str = "",
) -> str:
    base = base_path.rstrip("/")
    path = f"/noviny/{obdobi}/{schuze}/{datum_unl}-smlouvy.html"
    return f"{base}{path}" if base else path


def recnici_pages_href(
    obdobi: int,
    schuze: int,
    datum_unl: str,
    base_path: str = "",
) -> str:
    base = base_path.rstrip("/")
    path = f"/noviny/{obdobi}/{schuze}/{datum_unl}-recnici.html"
    return f"{base}{path}" if base else path


def vyznamenani_neprosli_pages_href(
    obdobi: int,
    schuze: int,
    datum_unl: str,
    base_path: str = "",
) -> str:
    return vyznamenani_pages_href(obdobi, schuze, datum_unl, "neprosli", base_path)


def resolve_edition(obdobi: int, datum_unl: str, schuze: int | None = None) -> Edition | None:
    matches = _editions_on_day(list_site_editions(obdobi), datum_unl)
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


def _edition_headline(edition: Edition, *, max_len: int = 80) -> str:
    from svejk.build.day_content import build_den_content
    from svejk.build.seo import article_headline

    paths = SchuzePaths.create(edition.obdobi, edition.schuze)
    d = datetime.strptime(edition.datum_unl, "%d.%m.%Y")
    day_path = paths.facts_by_day / f"{d.strftime('%Y-%m-%d')}.json"
    if not day_path.is_file():
        return ""
    content = build_den_content(day_path, paths)
    return article_headline(
        dnesni_ucet=content.dnesni_ucet,
        first_item_nadpis=content.items[0].nadpis if content.items else "",
        edition_title="",
        max_len=max_len,
    )


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


def _schuze_nav_suffix(schuze: int) -> str:
    word = load_strings().get("edition", {}).get("schuze_title", "schůze")
    return f" · {word} {schuze}"


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
        href = edition_pages_href(
            edition.obdobi, edition.schuze, edition.datum_unl, base_path
        )
    else:
        from_file = from_paths.noviny_dlouhe_html(from_datum)
        to_file = target_paths.noviny_dlouhe_html(edition.datum_unl)
        href = Path(os.path.relpath(to_file, from_file.parent)).as_posix()
    title = datum_design(edition.datum_unl, den)
    if len(_editions_on_day(editions, edition.datum_unl)) > 1:
        title = f"{title}{_schuze_nav_suffix(edition.schuze)}"
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
    editions = list_site_editions(ob)
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


def _archive_chips(
    subset: tuple[Edition, ...],
    editions: tuple[Edition, ...],
    *,
    current_schuze: int,
    current_datum: str,
    link_mode: str,
    from_paths: SchuzePaths,
    from_datum: str,
    base_path: str,
) -> tuple[ArchiveChip, ...]:
    chips: list[ArchiveChip] = []
    kw = {
        "editions": editions,
        "link_mode": link_mode,
        "from_paths": from_paths,
        "from_datum": from_datum,
        "base_path": base_path,
    }
    schuze_word = load_strings().get("edition", {}).get("schuze_title", "schůze")
    for edition in subset:
        d = datetime.strptime(edition.datum_unl, "%d.%m.%Y")
        link = _make_link(edition, **kw)
        target_paths = SchuzePaths.create(edition.obdobi, edition.schuze)
        den = _den_z_index(target_paths, edition.datum_unl)
        date_label = datum_design(edition.datum_unl, den)
        headline = _edition_headline(edition)
        schuze_part = f"{schuze_word} {edition.schuze}"
        aria = f"{headline}. {date_label}, {schuze_part}" if headline else (
            f"{date_label}, {schuze_part}"
        )
        chips.append(
            ArchiveChip(
                href=link.href,
                day_label=f"{d.day:02d}",
                schuze_suffix=f"s{edition.schuze}",
                is_current=(
                    edition.schuze == current_schuze and edition.datum_unl == current_datum
                ),
                title=aria,
                headline=headline,
                date_label=date_label,
                schuze=edition.schuze,
            )
        )
    return tuple(chips)


def archive_recent(
    paths: SchuzePaths,
    datum_unl: str,
    *,
    link_mode: str = "file",
    obdobi: int | None = None,
    base_path: str = "",
    limit: int = 30,
) -> tuple[ArchiveChip, ...]:
    ob = obdobi if obdobi is not None else paths.obdobi
    editions = list_site_editions(ob)
    if not editions:
        return ()
    recent = list(editions[-limit:] if len(editions) > limit else editions)
    in_recent = any(
        e.schuze == paths.schuze and e.datum_unl == datum_unl for e in recent
    )
    if not in_recent:
        current = next(
            (
                e
                for e in editions
                if e.schuze == paths.schuze and e.datum_unl == datum_unl
            ),
            None,
        )
        if current is not None:
            recent = [current] + recent[-(limit - 1) :]
    subset = tuple(recent)
    return _archive_chips(
        subset,
        editions,
        current_schuze=paths.schuze,
        current_datum=datum_unl,
        link_mode=link_mode,
        from_paths=paths,
        from_datum=datum_unl,
        base_path=base_path,
    )


def archive_by_month(
    paths: SchuzePaths,
    datum_unl: str,
    *,
    link_mode: str = "file",
    obdobi: int | None = None,
    base_path: str = "",
) -> tuple[ArchiveMonth, ...]:
    ob = obdobi if obdobi is not None else paths.obdobi
    editions = list_site_editions(ob)
    if not editions:
        return ()

    months: list[ArchiveMonth] = []
    for (year, month), group in groupby(editions, key=lambda e: (e.when.year, e.when.month)):
        subset = tuple(group)
        label = month_label(month, year)
        chips = _archive_chips(
            subset,
            editions,
            current_schuze=paths.schuze,
            current_datum=datum_unl,
            link_mode=link_mode,
            from_paths=paths,
            from_datum=datum_unl,
            base_path=base_path,
        )
        months.append(ArchiveMonth(label=label, chips=chips))
    return tuple(months)


def clear_edition_cache() -> None:
    list_obdobi_editions.cache_clear()
    from svejk.build.publish import clear_publish_cache

    clear_publish_cache()
