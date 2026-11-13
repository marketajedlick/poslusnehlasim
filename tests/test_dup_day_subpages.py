"""Den se dvěma schůzemi: holé /vydani/DATUM/<druh>/ nesmí skončit 404 a sitemap má obě vydání."""

from datetime import datetime, timezone

from svejk.build.export_pages import dup_day_bare_subpage_redirects
from svejk.build.nav import Edition
from svejk.build.publish import list_site_editions
from svejk.build.seo import write_sitemap_xml


def _ed(schuze: int, datum: str) -> Edition:
    return Edition(
        obdobi=2025,
        schuze=schuze,
        datum_unl=datum,
        when=datetime(2026, 6, 11, tzinfo=timezone.utc),
    )


def test_bare_subpage_redirects_to_sibling_that_has_it() -> None:
    editions = [_ed(22, "11.06.2026"), _ed(23, "11.06.2026"), _ed(24, "12.06.2026")]
    written = {
        "vydani/2026-06-11/index.html",
        "vydani/2026-06-11/s22/index.html",
        "vydani/2026-06-11/s22/recnici/index.html",  # jen nekanonická schůze
        "vydani/2026-06-11/s22/steno/index.html",
        "vydani/2026-06-11/s23/steno/index.html",
        "vydani/2026-06-12/steno/index.html",
    }
    got = dup_day_bare_subpage_redirects(editions, written, lambda _d: 23)
    assert ("vydani/2026-06-11/recnici/index.html", "11.06.2026", "s22/recnici") in got
    # Steno mají obě: přednost má kanonická schůze.
    assert ("vydani/2026-06-11/steno/index.html", "11.06.2026", "s23/steno") in got
    # Podstránky, které neexistují, a dny s jednou schůzí se nepřesměrovávají.
    assert {rel for rel, _, _ in got} == {
        "vydani/2026-06-11/recnici/index.html",
        "vydani/2026-06-11/steno/index.html",
    }


def test_bare_subpage_already_written_is_kept() -> None:
    editions = [_ed(22, "11.06.2026"), _ed(23, "11.06.2026")]
    written = {
        "vydani/2026-06-11/steno/index.html",
        "vydani/2026-06-11/s22/steno/index.html",
    }
    assert dup_day_bare_subpage_redirects(editions, written, lambda _d: 23) == []


def test_sitemap_lists_both_editions_of_two_session_day(tmp_path) -> None:
    day = "07.07.2026"
    editions = [e for e in list_site_editions(2025) if e.datum_unl == day]
    assert len(editions) >= 2, "fixture: 7. 7. 2026 má s24 i s25"
    xml = write_sitemap_xml(
        tmp_path, editions, site_url="https://poslusnehlasim.cz"
    ).read_text(encoding="utf-8")
    assert xml.count("<loc>https://poslusnehlasim.cz/vydani/2026-07-07/</loc>") == 1
    assert "<loc>https://poslusnehlasim.cz/vydani/2026-07-07/s25/</loc>" in xml
