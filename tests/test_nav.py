from datetime import datetime, timezone
from unittest.mock import patch

from svejk.build.nav import Edition, build_session_calendar, edition_nav
from svejk.paths import SchuzePaths


def _edition(day: int, schuze: int = 24) -> Edition:
    datum = f"{day:02d}.06.2026"
    return Edition(
        obdobi=2025,
        schuze=schuze,
        datum_unl=datum,
        when=datetime(2026, 6, day, tzinfo=timezone.utc),
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


def _edition_on(datum_unl: str, schuze: int = 5) -> Edition:
    when = datetime.strptime(datum_unl, "%d.%m.%Y").replace(tzinfo=timezone.utc)
    return Edition(
        obdobi=2025,
        schuze=schuze,
        datum_unl=datum_unl,
        when=when,
    )


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
