"""Navigace mezi vydáními, chronologicky přes celé období."""

from __future__ import annotations

import calendar
import os
from dataclasses import dataclass
from datetime import date, datetime
from functools import lru_cache
from itertools import groupby
from pathlib import Path

from svejk.build.day_content import datum_design
from svejk.build.urls import vydani_pages_href, vydani_subpage_href
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
    short_label: str = ""


@dataclass(frozen=True)
class SessionCalendar:
    month_label: str
    year: int
    weeks: tuple[tuple[dict[str, object], ...], ...]
    prev_month: EditionLink | None = None
    next_month: EditionLink | None = None


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
class ArchiveTextEntry:
    href: str
    date_label: str
    headline: str
    label: str


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


def short_pager_label(datum_unl: str) -> str:
    d = datetime.strptime(datum_unl, "%d.%m.%Y")
    return f"{d.day}. {d.month}."


def edition_web_href(obdobi: int, schuze: int, datum_unl: str) -> str:
    _ = obdobi, schuze
    return vydani_pages_href(datum_unl)


def edition_pages_href(
    obdobi: int,
    schuze: int,
    datum_unl: str,
    base_path: str = "",
) -> str:
    """Kanonická URL vydání na produkčním webu."""
    _ = obdobi, schuze
    return vydani_pages_href(datum_unl, base_path)


def archiv_pages_href(base_path: str = "") -> str:
    return _join_href_path(base_path, "/archiv/")


def _join_href_path(base_path: str, path: str) -> str:
    base = base_path.rstrip("/")
    if not path.startswith("/"):
        path = "/" + path
    return f"{base}{path}" if base else path


def o_webu_pages_href(base_path: str = "") -> str:
    return _join_href_path(base_path, "/o-webu/")


def slovnicek_pages_href(base_path: str = "") -> str:
    return _join_href_path(base_path, "/slovnicek/")


def slovnicek_term_pages_href(slug: str, base_path: str = "") -> str:
    slug = slug.strip("/")
    return _join_href_path(base_path, f"/slovnicek/{slug}/")


def pivo_pages_href(base_path: str = "") -> str:
    return _join_href_path(base_path, "/pivo.html")


def soukromi_pages_href(base_path: str = "") -> str:
    return _join_href_path(base_path, "/soukromi/")


def podpora_pages_href(base_path: str = "") -> str:
    return _join_href_path(base_path, "/podpora/")


def podminky_pages_href(base_path: str = "") -> str:
    return _join_href_path(base_path, "/podminky/")


def dekuju_pages_href(base_path: str = "") -> str:
    return _join_href_path(base_path, "/dekuju.html")


def vyznamenani_pages_href(
    obdobi: int,
    schuze: int,
    datum_unl: str,
    kind: str,
    base_path: str = "",
) -> str:
    _ = obdobi, schuze
    return vydani_subpage_href(datum_unl, kind, base_path)


def steno_sources_pages_href(
    obdobi: int,
    schuze: int,
    datum_unl: str,
    base_path: str = "",
) -> str:
    _ = obdobi, schuze
    return vydani_subpage_href(datum_unl, "steno", base_path)


def smlouvy_pages_href(
    obdobi: int,
    schuze: int,
    datum_unl: str,
    base_path: str = "",
) -> str:
    _ = obdobi, schuze
    return vydani_subpage_href(datum_unl, "smlouvy", base_path)


def recnici_pages_href(
    obdobi: int,
    schuze: int,
    datum_unl: str,
    base_path: str = "",
) -> str:
    _ = obdobi, schuze
    return vydani_subpage_href(datum_unl, "recnici", base_path)


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
        short_label=short_pager_label(edition.datum_unl),
    )


def _shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    month += delta
    if month < 1:
        return year - 1, 12
    if month > 12:
        return year + 1, 1
    return year, month


def _editions_in_month(
    editions: tuple[Edition, ...], year: int, month: int
) -> tuple[Edition, ...]:
    out: list[Edition] = []
    for edition in editions:
        when = datetime.strptime(edition.datum_unl, "%d.%m.%Y")
        if when.year == year and when.month == month:
            out.append(edition)
    return tuple(out)


def _edition_when(edition: Edition) -> datetime:
    return datetime.strptime(edition.datum_unl, "%d.%m.%Y")


def _nearest_edition_before(
    editions: tuple[Edition, ...], before: date
) -> Edition | None:
    prior = [e for e in editions if _edition_when(e).date() < before]
    return prior[-1] if prior else None


def _nearest_edition_from(
    editions: tuple[Edition, ...], start: date
) -> Edition | None:
    for edition in editions:
        if _edition_when(edition).date() >= start:
            return edition
    return None


def _ghost_day(year: int, month: int, week_idx: int, day_idx: int) -> int:
    """Číslo dne z předchozího nebo následujícího měsíce (monthcalendar vrací 0)."""
    first_weekday = calendar.weekday(year, month, 1)
    day_offset = week_idx * 7 + day_idx - first_weekday
    days_in_month = calendar.monthrange(year, month)[1]
    if day_offset < 0:
        prev_year, prev_m = _shift_month(year, month, -1)
        return calendar.monthrange(prev_year, prev_m)[1] + day_offset + 1
    return day_offset - days_in_month + 1


def _calendar_month_link(
    edition: Edition,
    *,
    year: int,
    month: int,
    link_mode: str,
    base_path: str,
    arrow: str,
) -> EditionLink:
    if link_mode == "pages":
        href = edition_pages_href(
            edition.obdobi, edition.schuze, edition.datum_unl, base_path
        )
    else:
        href = edition_web_href(edition.obdobi, edition.schuze, edition.datum_unl)
    label = month_label(month, year)
    return EditionLink(href=href, label=label, title=label, short_label=arrow)


def build_session_calendar(
    obdobi: int,
    datum_unl: str,
    *,
    base_path: str = "",
    link_mode: str = "pages",
) -> SessionCalendar:
    """Mini kalendář zasedání pro levý rail (Po–Ne)."""
    current = datetime.strptime(datum_unl, "%d.%m.%Y")
    year, month = current.year, current.month
    editions = list_site_editions(obdobi)
    by_day: dict[int, Edition] = {}
    for edition in editions:
        when = datetime.strptime(edition.datum_unl, "%d.%m.%Y")
        if when.year == year and when.month == month:
            by_day[when.day] = edition

    weeks: list[tuple[dict[str, object], ...]] = []
    for week_idx, week in enumerate(calendar.monthcalendar(year, month)):
        row: list[dict[str, object]] = []
        for day_idx, day in enumerate(week):
            if day == 0:
                row.append(
                    {
                        "n": _ghost_day(year, month, week_idx, day_idx),
                        "ghost": True,
                        "muted": True,
                    }
                )
            elif day == current.day:
                row.append({"n": day, "today": True})
            elif day in by_day:
                edition = by_day[day]
                if link_mode == "pages":
                    href = edition_pages_href(
                        edition.obdobi, edition.schuze, edition.datum_unl, base_path
                    )
                else:
                    href = edition_web_href(
                        edition.obdobi, edition.schuze, edition.datum_unl
                    )
                row.append({"n": day, "link": href})
            else:
                row.append({"n": day, "muted": True})
        weeks.append(tuple(row))

    prev_month = next_month = None
    month_start = date(year, month, 1)
    prev_year, prev_m = _shift_month(year, month, -1)
    prev_editions = _editions_in_month(editions, prev_year, prev_m)
    if prev_editions:
        prev_anchor = prev_editions[-1]
        prev_label_year, prev_label_month = prev_year, prev_m
    elif anchor := _nearest_edition_before(editions, month_start):
        prev_anchor = anchor
        when = _edition_when(anchor)
        prev_label_year, prev_label_month = when.year, when.month
    else:
        prev_anchor = None
    if prev_anchor is not None:
        prev_month = _calendar_month_link(
            prev_anchor,
            year=prev_label_year,
            month=prev_label_month,
            link_mode=link_mode,
            base_path=base_path,
            arrow="←",
        )
    next_year, next_m = _shift_month(year, month, 1)
    next_editions = _editions_in_month(editions, next_year, next_m)
    if next_editions:
        next_anchor = next_editions[0]
        next_label_year, next_label_month = next_year, next_m
    elif anchor := _nearest_edition_from(editions, date(next_year, next_m, 1)):
        next_anchor = anchor
        when = _edition_when(anchor)
        next_label_year, next_label_month = when.year, when.month
    else:
        next_anchor = None
    if next_anchor is not None:
        next_month = _calendar_month_link(
            next_anchor,
            year=next_label_year,
            month=next_label_month,
            link_mode=link_mode,
            base_path=base_path,
            arrow="→",
        )

    month_name = month_label(month, year).split()[0]
    return SessionCalendar(
        month_label=month_name,
        year=year,
        weeks=tuple(weeks),
        prev_month=prev_month,
        next_month=next_month,
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


def homepage_archive_list(
    paths: SchuzePaths,
    datum_unl: str,
    *,
    link_mode: str = "pages",
    obdobi: int | None = None,
    base_path: str = "",
    limit: int = 5,
) -> tuple[ArchiveTextEntry, ...]:
    """Poslední vydání pro homepage (bez aktuálního dne), nejnovější první."""
    ob = obdobi if obdobi is not None else paths.obdobi
    current_href = edition_pages_href(ob, paths.schuze, datum_unl, base_path)
    out: list[ArchiveTextEntry] = []
    for entry in archive_text_list(ob, link_mode=link_mode, base_path=base_path):
        if entry.href == current_href:
            continue
        out.append(entry)
        if len(out) >= limit:
            break
    return tuple(out)


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


def archive_text_list(
    obdobi: int,
    *,
    link_mode: str = "pages",
    base_path: str = "",
) -> tuple[ArchiveTextEntry, ...]:
    """Chronologický seznam vydání s viditelným anchor textem pro crawlery."""
    editions = list_site_editions(obdobi)
    if not editions:
        return ()
    entries: list[ArchiveTextEntry] = []
    for edition in reversed(editions):
        paths = SchuzePaths.create(edition.obdobi, edition.schuze)
        den = _den_z_index(paths, edition.datum_unl)
        date_label = datum_design(edition.datum_unl, den)
        headline = _edition_headline(edition)
        if link_mode == "pages":
            href = edition_pages_href(
                edition.obdobi, edition.schuze, edition.datum_unl, base_path
            )
        elif link_mode == "web":
            href = edition_web_href(edition.obdobi, edition.schuze, edition.datum_unl)
        else:
            href = edition_pages_href(
                edition.obdobi, edition.schuze, edition.datum_unl, base_path
            )
        label = f"{date_label}, {headline}" if headline else date_label
        entries.append(
            ArchiveTextEntry(
                href=href,
                date_label=date_label,
                headline=headline,
                label=label,
            )
        )
    return tuple(entries)


def clear_edition_cache() -> None:
    list_obdobi_editions.cache_clear()
    from svejk.build.publish import clear_publish_cache

    clear_publish_cache()
