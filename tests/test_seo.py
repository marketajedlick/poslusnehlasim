from svejk.build.seo import (
    faq_json_ld,
    homepage_og_title,
    homepage_page_title,
    write_robots_txt,
    write_sitemap_xml,
)
from svejk.build.nav import Edition


def test_homepage_page_title() -> None:
    assert homepage_page_title() == "Poslušně hlásím · Deník ze Sněmovny"
    assert homepage_page_title(datum_unl="23.06.2026") == homepage_page_title()


def test_homepage_og_title() -> None:
    assert homepage_og_title() == "Poslušně hlásím · Deník ze Sněmovny"


def test_faq_json_ld() -> None:
    data = faq_json_ld(
        url="https://poslusnehlasim.cz/slovnicek.html",
        entries=[("Co je obstrukce?", "Zdržování jednání.")],
    )
    assert data["@type"] == "FAQPage"
    assert data["mainEntity"][0]["name"] == "Co je obstrukce?"
    assert data["mainEntity"][0]["acceptedAnswer"]["text"] == "Zdržování jednání."


def test_write_robots_txt(tmp_path) -> None:
    path = write_robots_txt(tmp_path, site_url="https://poslusnehlasim.cz")
    text = path.read_text(encoding="utf-8")
    assert "Sitemap: https://poslusnehlasim.cz/sitemap.xml" in text
    assert "Allow: /" in text


def test_write_sitemap_includes_o_webu(tmp_path) -> None:
    from datetime import datetime, timezone

    editions = [
        Edition(
            obdobi=2025,
            schuze=24,
            datum_unl="26.06.2026",
            when=datetime(2026, 6, 26, tzinfo=timezone.utc),
        )
    ]
    path = write_sitemap_xml(
        tmp_path,
        editions,
        site_url="https://poslusnehlasim.cz",
    )
    xml = path.read_text(encoding="utf-8")
    assert "https://poslusnehlasim.cz/o-webu/" in xml
    assert "https://poslusnehlasim.cz/slovnicek.html" in xml
