from datetime import datetime, timezone
from unittest.mock import patch

from svejk.build.nav import Edition, build_session_calendar, edition_nav
from svejk.build.urls import vydani_pages_href, vydani_schuze_href
from svejk.paths import SchuzePaths


def _edition(day: int, schuze: int = 24, month: int = 6) -> Edition:
    datum = f"{day:02d}.{month:02d}.2026"
    return Edition(
        obdobi=2025,
        schuze=schuze,
        datum_unl=datum,
        when=datetime(2026, month, day, tzinfo=timezone.utc),
    )


def _edition_on(datum_unl: str, schuze: int = 5) -> Edition:
    when = datetime.strptime(datum_unl, "%d.%m.%Y").replace(tzinfo=timezone.utc)
    return Edition(
        obdobi=2025,
        schuze=schuze,
        datum_unl=datum_unl,
        when=when,
    )


@patch("svejk.build.nav.list_site_editions")
def test_edition_nav_pages_uses_vydani_urls(mock_list) -> None:
    editions = (_edition(1), _edition(2), _edition(3))
    mock_list.return_value = editions
    paths = SchuzePaths.create(2025, 24)

    nav = edition_nav(paths, "02.06.2026", link_mode="pages")

    assert nav.prev is not None
    assert nav.next is not None
    assert nav.prev.href == "/vydani/2026-06-01/"
    assert nav.next.href == "/vydani/2026-06-03/"
    assert nav.prev.short_label == "1. 6."
    assert nav.next.short_label == "3. 6."


@patch("svejk.build.nav.list_site_editions")
def test_edition_nav_edges(mock_list) -> None:
    editions = (_edition(1), _edition(2))
    mock_list.return_value = editions
    paths = SchuzePaths.create(2025, 24)

    first = edition_nav(paths, "01.06.2026", link_mode="pages")
    last = edition_nav(paths, "02.06.2026", link_mode="pages")

    assert first.prev is None
    assert first.next is not None
    assert last.prev is not None
    assert last.next is None


@patch("svejk.build.nav.list_site_editions")
def test_edition_nav_switches_siblings_same_day(mock_list) -> None:
    """Dvě schůze v jeden den: pager přepíná mezi nimi, datum uprostřed se nemění."""
    editions = (
        _edition(5),
        _edition(11, schuze=22),
        _edition(11, schuze=23),
        _edition(23),
    )
    mock_list.return_value = editions

    nav23 = edition_nav(SchuzePaths.create(2025, 23), "11.06.2026", link_mode="pages")
    assert nav23.prev is not None
    assert nav23.prev.href == "/vydani/2026-06-11/s22/"
    assert nav23.prev.short_label == "s22"
    assert nav23.next is not None
    assert nav23.next.href == "/vydani/2026-06-23/"
    assert nav23.next.short_label == "23. 6."

    nav22 = edition_nav(SchuzePaths.create(2025, 22), "11.06.2026", link_mode="pages")
    assert nav22.prev is not None
    assert nav22.prev.href == "/vydani/2026-06-05/"
    assert nav22.next is not None
    assert nav22.next.href == "/vydani/2026-06-11/"
    assert nav22.next.short_label == "s23"


@patch("svejk.build.nav.list_site_editions")
def test_edition_nav_siblings_june_3(mock_list) -> None:
    editions = (
        _edition(2, schuze=21),
        _edition(3, schuze=17),
        _edition(3, schuze=20),
        _edition(4, schuze=20),
    )
    mock_list.return_value = editions

    nav20 = edition_nav(SchuzePaths.create(2025, 20), "03.06.2026", link_mode="pages")
    assert nav20.prev.href == "/vydani/2026-06-03/s17/"
    assert nav20.prev.short_label == "s17"
    assert nav20.next.href == "/vydani/2026-06-04/"

    nav17 = edition_nav(SchuzePaths.create(2025, 17), "03.06.2026", link_mode="pages")
    assert nav17.prev.href == "/vydani/2026-06-02/"
    assert nav17.next.href == "/vydani/2026-06-03/"
    assert nav17.next.short_label == "s20"


@patch("svejk.build.nav.list_site_editions")
def test_edition_nav_siblings_may_6(mock_list) -> None:
    editions = (
        _edition_on("05.05.2026", schuze=16),
        _edition_on("06.05.2026", schuze=16),
        _edition_on("06.05.2026", schuze=17),
        _edition_on("13.05.2026", schuze=17),
    )
    mock_list.return_value = editions

    nav17 = edition_nav(SchuzePaths.create(2025, 17), "06.05.2026", link_mode="pages")
    assert nav17.prev.href == "/vydani/2026-05-06/s16/"
    assert nav17.prev.short_label == "s16"
    assert nav17.next.href == "/vydani/2026-05-13/"

    nav16 = edition_nav(SchuzePaths.create(2025, 16), "06.05.2026", link_mode="pages")
    assert nav16.prev.href == "/vydani/2026-05-05/"
    assert nav16.next.href == "/vydani/2026-05-06/"
    assert nav16.next.short_label == "s17"


def test_edition_nav_all_published_editions_avoid_self_links() -> None:
    from svejk.build.nav import edition_pages_href
    from svejk.build.publish import list_site_editions

    for edition in list_site_editions(2025):
        paths = SchuzePaths.create(edition.obdobi, edition.schuze)
        self_href = edition_pages_href(
            edition.obdobi, edition.schuze, edition.datum_unl
        )
        for link_mode in ("pages", "web"):
            nav = edition_nav(paths, edition.datum_unl, link_mode=link_mode)
            if nav.prev:
                assert nav.prev.href != self_href, (
                    f"s{edition.schuze} {edition.datum_unl} prev ({link_mode})"
                )
            if nav.next:
                assert nav.next.href != self_href, (
                    f"s{edition.schuze} {edition.datum_unl} next ({link_mode})"
                )


def test_edition_pages_href_sibling_subpath() -> None:
    from svejk.build.nav import edition_pages_href

    with patch("svejk.build.nav.list_site_editions") as mock_list:
        mock_list.return_value = (
            _edition_on("06.05.2026", schuze=16),
            _edition_on("06.05.2026", schuze=17),
        )
        assert edition_pages_href(2025, 17, "06.05.2026") == "/vydani/2026-05-06/"
        assert edition_pages_href(2025, 16, "06.05.2026") == "/vydani/2026-05-06/s16/"


@patch("svejk.build.nav.list_site_editions")
def test_session_calendar_bridges_empty_december(mock_list) -> None:
    """Leden bez prosincových vydání: šipky přeskočí mezeru, mřížka ukáže konec prosince."""
    editions = (
        _edition_on("27.11.2025", schuze=4),
        _edition_on("13.01.2026"),
        _edition_on("30.01.2026"),
    )
    mock_list.return_value = editions

    cal = build_session_calendar(2025, "30.01.2026", link_mode="pages")

    assert cal.prev_month is not None
    assert cal.prev_month.title == "listopad 2025"
    assert cal.prev_month.href == "/vydani/2025-11-27/"
    assert cal.weeks[0][0] == {"n": 29, "ghost": True, "muted": True}
    assert cal.weeks[0][1] == {"n": 30, "ghost": True, "muted": True}
    assert cal.weeks[0][2] == {"n": 31, "ghost": True, "muted": True}

    nov = build_session_calendar(2025, "27.11.2025", link_mode="pages")
    assert nov.next_month is not None
    assert nov.next_month.title == "leden 2026"
    assert nov.next_month.href == "/vydani/2026-01-13/"
