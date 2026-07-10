from svejk.build.nav import (
    Edition,
    archiv_pages_href,
    edition_pages_href,
    pivo_pages_href,
    slovnicek_pages_href,
    slovnicek_term_pages_href,
    steno_sources_pages_href,
)
from svejk.build.urls import (
    article_anchor_id,
    datum_iso_to_unl,
    datum_unl_to_iso,
    edition_article_href,
    edition_export_relpath,
    edition_legacy_pages_href,
    edition_slug,
    edition_subpage_export_relpath,
    poslanec_slug,
    vydani_pages_href,
    vydani_schuze_href,
)
from svejk.glossary import slovnicek_term_slug
from svejk.build.day_content import DenItem
from datetime import datetime, timezone


def test_datum_conversions() -> None:
    assert datum_unl_to_iso("08.07.2026") == "2026-07-08"
    assert datum_iso_to_unl("2026-07-08") == "08.07.2026"


def test_vydani_hrefs() -> None:
    assert edition_pages_href(2025, 24, "26.06.2026") == "/vydani/2026-06-26/"
    assert steno_sources_pages_href(2025, 24, "26.06.2026") == (
        "/vydani/2026-06-26/steno/"
    )
    assert archiv_pages_href() == "/vydani/"
    assert slovnicek_pages_href() == "/slovnicek/"
    assert slovnicek_term_pages_href("obstrukce") == "/slovnicek/obstrukce/"
    assert pivo_pages_href() == "/pivo/"


def test_slovnicek_term_slug() -> None:
    assert slovnicek_term_slug("rozpočtové brzdy") == "rozpoctove-brzdy"
    assert slovnicek_term_slug("Dozimetr") == "dozimetr"


def test_article_anchor_id() -> None:
    assert article_anchor_id(slug="novela-z-o-obalech") == "novela-z-o-obalech"
    assert article_anchor_id(slug="", num=3) == "article-3"


def test_edition_article_href() -> None:
    assert edition_article_href(
        "02.07.2026",
        slug="novela-z-o-obalech",
    ) == "/vydani/2026-07-02/#novela-z-o-obalech"


def test_den_item_anchor_id() -> None:
    item = DenItem(
        num=2,
        kick="",
        nadpis="Test",
        nadpis_radky=["Test"],
        lead="",
        mean="",
        dopad="",
        parliament_lead="",
        verdikt="schvaleno",
        slug="novela-z-o-obalech",
    )
    assert item.anchor_id == "novela-z-o-obalech"
    item.slug = ""
    assert item.anchor_id == "article-2"


def test_export_relpaths() -> None:
    assert edition_export_relpath("26.06.2026") == "vydani/2026-06-26/index.html"
    assert edition_export_relpath("06.05.2026", 16) == "vydani/2026-05-06/s16/index.html"
    assert edition_subpage_export_relpath("26.06.2026", "steno") == (
        "vydani/2026-06-26/steno/index.html"
    )


def test_vydani_schuze_href() -> None:
    assert vydani_schuze_href("06.05.2026", 16) == "/vydani/2026-05-06/s16/"


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
