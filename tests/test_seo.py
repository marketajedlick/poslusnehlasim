from svejk.build.seo import (
    edition_meta_description,
    faq_json_ld,
    homepage_og_title,
    homepage_page_title,
    site_brand_line,
    site_meta_description,
    website_json_ld,
    write_robots_txt,
    write_sitemap_xml,
)
from svejk.build.nav import Edition


def test_site_meta_description() -> None:
    assert site_meta_description() == (
        "Poslušně hlásím je srozumitelný přehled z Poslanecké sněmovny: "
        "co se projednalo, co prošlo a proč na tom záleží."
    )
    # Vydání s obsahem dává unikátní popis odvozený z textu dne (ne fallback).
    assert (
        edition_meta_description(
            dnesni_ucet="Skóre dne 1:0. <span>ratifikací</span>",
            proslo=1,
        )
        == "Skóre dne 1:0 · Prošlo 1 z 1 bodů."
    )
    # Prázdný vstup spadne na fallback se značkovou větou.
    assert edition_meta_description(dnesni_ucet="") == site_meta_description()
    # Slovníkové bubliny (tooltip) se do popisu nesmí propsat — jen viditelný label.
    assert (
        edition_meta_description(
            dnesni_ucet=(
                'Hřib <span class="term-tip" role="term" aria-label="x">'
                '(Piráti)<span class="term-tip-bubble" role="tooltip">'
                'Česká pirátská strana.</span></span> dorazil.'
            ),
        )
        == "Hřib (Piráti) dorazil"
    )
    assert site_brand_line() == (
        "Poslušně hlásím · poslusnehlasim.cz · Deník sněmovny"
    )


def test_homepage_website_json_ld() -> None:
    data = website_json_ld(site_url="https://poslusnehlasim.cz")
    assert data["@context"] == "https://schema.org"
    assert len(data["@graph"]) == 2
    website = data["@graph"][0]
    org = data["@graph"][1]
    assert website["@type"] == "WebSite"
    assert website["name"] == "Poslušně hlásím"
    assert website["alternateName"] == "poslusnehlasim.cz"
    assert website["url"] == "https://poslusnehlasim.cz/"
    assert org["@type"] == ["Organization", "NewsMediaOrganization"]
    assert org["alternateName"] == "poslusnehlasim.cz"
    assert website["publisher"] == {"@id": "https://poslusnehlasim.cz/#organization"}


def test_homepage_page_title() -> None:
    assert homepage_page_title() == "Poslušně hlásím · Švejkův deník ze Sněmovny"
    assert homepage_page_title(datum_unl="23.06.2026") == homepage_page_title()


def test_homepage_og_title() -> None:
    assert homepage_og_title() == "Poslušně hlásím · Švejkův deník ze Sněmovny"


def test_homepage_share_og_title() -> None:
    from svejk.build.seo import homepage_share_og_title

    title = homepage_share_og_title(
        dnesni_ucet="Hádka o média.",
        first_item_nadpis="Fiktivní zpravodajství",
        datum_unl="23.06.2026",
        den="úterý",
    )
    assert title.startswith("Poslušně hlásím, Úterý 23. 6. 2026: ")
    assert "Fiktivní zpravodajství" in title


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
    assert "Content-Signal: search=yes,ai-train=no" in text
    assert "User-agent: ClaudeBot\nAllow: /" in text
    assert "Disallow: /" not in text
    # Explicitní Allow pro AI boty před obecným User-agent: *
    assert text.index("User-agent: GPTBot") < text.index("User-agent: *")


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
    assert "https://poslusnehlasim.cz/noviny/2025/24/26.06.2026.html" in xml
    assert "feed.xml" not in xml
    assert "-steno.html" not in xml
    assert "-neprosli.html" not in xml
    assert "-recnici.html" not in xml
