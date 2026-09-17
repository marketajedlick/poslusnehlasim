"""OG/share pro den s více schůzemi musí brát kanonické vydání."""

from svejk.build.export_pages import homepage_canonical_url
from svejk.build.nav import edition_pages_href, resolve_edition
from svejk.build.publish import list_approved_editions, list_site_editions


def test_duplicate_date_og_uses_canonical_schuze() -> None:
    day = "07.07.2026"
    matches = [e for e in list_site_editions(2025) if e.datum_unl == day]
    assert len(matches) >= 2, "fixture: 7. 7. 2026 má s24 i s25"
    assert matches[0].schuze == 24
    canonical = resolve_edition(2025, day)
    assert canonical is not None
    assert canonical.schuze == matches[-1].schuze == 25


def test_homepage_canonical_points_to_edition_not_root() -> None:
    """Homepage = plný text vydání; canonical musí být /vydani/DATUM/, ne /."""
    editions = list_site_editions(2025)
    assert editions
    approved = list_approved_editions(2025)
    homepage_edition = approved[-1] if approved else editions[-1]
    href = edition_pages_href(
        homepage_edition.obdobi,
        homepage_edition.schuze,
        homepage_edition.datum_unl,
    )
    assert href.startswith("/vydani/")
    assert href.endswith("/")
    url = homepage_canonical_url("https://poslusnehlasim.cz", homepage_edition)
    assert url == f"https://poslusnehlasim.cz{href}"
    assert url != "https://poslusnehlasim.cz/"
