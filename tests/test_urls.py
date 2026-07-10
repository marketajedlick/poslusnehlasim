from svejk.build.nav import (
    Edition,
    archiv_pages_href,
    edition_pages_href,
    slovnicek_pages_href,
    steno_sources_pages_href,
)
from svejk.build.urls import (
    datum_iso_to_unl,
    datum_unl_to_iso,
    edition_export_relpath,
    edition_legacy_pages_href,
    edition_slug,
    edition_subpage_export_relpath,
    poslanec_slug,
    vydani_pages_href,
)
from datetime import datetime, timezone


def test_datum_conversions() -> None:
    assert datum_unl_to_iso("08.07.2026") == "2026-07-08"
    assert datum_iso_to_unl("2026-07-08") == "08.07.2026"


def test_vydani_hrefs() -> None:
    assert edition_pages_href(2025, 24, "26.06.2026") == "/vydani/2026-06-26/"
    assert steno_sources_pages_href(2025, 24, "26.06.2026") == (
        "/vydani/2026-06-26/steno/"
    )
    assert archiv_pages_href() == "/archiv/"
    assert slovnicek_pages_href() == "/slovnicek/"


def test_export_relpaths() -> None:
    assert edition_export_relpath("26.06.2026") == "vydani/2026-06-26/index.html"
    assert edition_subpage_export_relpath("26.06.2026", "steno") == (
        "vydani/2026-06-26/steno/index.html"
    )


def test_legacy_href() -> None:
    assert edition_legacy_pages_href(2025, 24, "26.06.2026") == (
        "/noviny/2025/24/26.06.2026.html"
    )


def test_slugs() -> None:
    edition = Edition(
        obdobi=2025,
        schuze=24,
        datum_unl="26.06.2026",
        when=datetime(2026, 6, 26, tzinfo=timezone.utc),
    )
    assert edition_slug(edition) == "2026-06-26"
    assert poslanec_slug("Andrej", "Babiš") == "andrej-babis"
    assert vydani_pages_href("26.06.2026") == "/vydani/2026-06-26/"
