from svejk.build.seo import (
    article_json_ld,
    breadcrumb_json_ld,
    breadcrumbs_ctx_archiv,
    breadcrumbs_ctx_edition,
    breadcrumbs_ctx_edition_subpage,
    breadcrumbs_ctx_slovnicek,
    breadcrumbs_ctx_slovnicek_term,
    edition_meta_description,
    edition_page_title,
    faq_json_ld,
    homepage_og_title,
    homepage_page_title,
    slovnicek_term_json_ld,
    slovnicek_term_page_title,
    site_brand_line,
    site_meta_description,
    website_json_ld,
    write_robots_txt,
    write_sitemap_xml,
)
from svejk.build.seo import BreadcrumbCrumb, SITE_NAME
from svejk.build.nav import Edition


def test_site_meta_description() -> None:
    assert site_meta_description() == (
        "Satirický deník z Poslanecké sněmovny. Každý jednací den srozumitelně: "
        "o čem poslanci hlasovali, co zaznělo v rozpravě a co to znamená. "
        "Bez stenoprotokolové mlhy."
    )
    assert (
        edition_meta_description(
            dnesni_ucet="Skóre dne 1:0. <span>ratifikací</span>",
            datum_unl="02.07.2026",
            proslo=1,
        )
        == "Skóre dne 1:0. Denní přehled z Poslanecké sněmovny, 2. 7. 2026."
    )
    assert edition_meta_description(dnesni_ucet="") == site_meta_description()
    assert (
        edition_meta_description(
            dnesni_ucet=(
                'Hřib <span class="term-tip" role="term" aria-label="x">'
                '(Piráti)<span class="term-tip-bubble" role="tooltip">'
                'Česká pirátská strana.</span></span> dorazil.'
            ),
            datum_unl="08.07.2026",
        )
        == "Hřib (Piráti) dorazil. Denní přehled z Poslanecké sněmovny, 8. 7. 2026."
    )
    assert (
        edition_meta_description(
            dnesni_ucet="",
            first_item_nadpis="Titulek na počkání",
            datum_unl="02.07.2026",
        )
        == "Titulek na počkání. Denní přehled z Poslanecké sněmovny, 2. 7. 2026."
    )
    assert (
        edition_meta_description(
            dnesni_ucet="",
            nadpis_vydani="Svačina pro prezidenta",
            first_item_nadpis="Jiný první článek",
            datum_unl="30.06.2026",
        )
        == "Svačina pro prezidenta. Denní přehled z Poslanecké sněmovny, 30. 6. 2026."
    )
    assert site_brand_line() == (
        "Poslušně hlásím · poslusnehlasim.cz · Deník sněmovny"
    )


def test_homepage_website_json_ld() -> None:
    data = website_json_ld(site_url="https://poslusnehlasim.cz")
    assert data["@context"] == "https://schema.org"
    assert len(data["@graph"]) == 2
    org = data["@graph"][0]
    website = data["@graph"][1]
    assert org["@type"] == ["Organization", "NewsMediaOrganization"]
    assert org["@id"] == "https://poslusnehlasim.cz/#org"
    assert org["alternateName"] == "poslusnehlasim.cz"
    assert "Poslanecké sněmovny Parlamentu ČR" in org["description"]
    assert website["@type"] == "WebSite"
    assert website["name"] == "Poslušně hlásím, deník Poslanecké sněmovny"
    assert website["alternateName"] == "poslusnehlasim.cz"
    assert website["url"] == "https://poslusnehlasim.cz/"
    assert website["publisher"] == {"@id": "https://poslusnehlasim.cz/#org"}


def test_article_json_ld() -> None:
    data = article_json_ld(
        headline="Titulek na počkání",
        description="Perex dne.",
        url="https://poslusnehlasim.cz/vydani/2026-07-02/",
        date_unl="02.07.2026",
        site_url="https://poslusnehlasim.cz",
    )
    assert data["@type"] == "NewsArticle"
    assert data["author"] == {
        "@type": "Organization",
        "@id": "https://poslusnehlasim.cz/#org",
    }
    assert data["publisher"] == {"@id": "https://poslusnehlasim.cz/#org"}
    assert data["datePublished"] == "2026-07-02T00:00:00+02:00"
    assert data["about"][0]["name"] == (
        "Poslanecká sněmovna Parlamentu České republiky"
    )


def test_article_json_ld_has_part_urls() -> None:
    data = article_json_ld(
        headline="Titulek",
        description="Perex.",
        url="https://poslusnehlasim.cz/vydani/2026-07-02/",
        date_unl="02.07.2026",
        site_url="https://poslusnehlasim.cz",
        parts=[
            {
                "headline": "Bod A",
                "body": "Text A",
                "position": 1,
                "url": "https://poslusnehlasim.cz/vydani/2026-07-02/#novela-z-o-obalech",
            }
        ],
    )
    part = data["hasPart"][0]
    assert part["@id"] == "https://poslusnehlasim.cz/vydani/2026-07-02/#novela-z-o-obalech"
    assert part["url"] == part["@id"]


def test_homepage_page_title() -> None:
    assert homepage_page_title() == (
        "Poslušně hlásím, denní zpravodaj z Poslanecké sněmovny"
    )
    assert homepage_page_title(datum_unl="23.06.2026") == homepage_page_title()


def test_homepage_og_title() -> None:
    assert homepage_og_title() == (
        "Poslušně hlásím, denní zpravodaj z Poslanecké sněmovny"
    )


def test_edition_page_title() -> None:
    title = edition_page_title(
        dnesni_ucet="Hádka o média.",
        first_item_nadpis="Titulek na počkání",
        datum_unl="02.07.2026",
        den="čtvrtek",
    )
    assert title == "Sněmovna 2. 7. 2026: Titulek na počkání | Poslušně hlásím"


def test_homepage_share_og_title() -> None:
    from svejk.build.seo import homepage_share_og_title

    title = homepage_share_og_title(
        dnesni_ucet="Hádka o média.",
        first_item_nadpis="Fiktivní zpravodajství",
        datum_unl="23.06.2026",
        den="úterý",
    )
    assert title.startswith("Sněmovna 23. 6. 2026: ")
    assert "Fiktivní zpravodajství" in title
    assert title.endswith("| Poslušně hlásím")


def test_faq_json_ld() -> None:
    data = faq_json_ld(
        url="https://poslusnehlasim.cz/slovnicek/",
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
    assert "https://poslusnehlasim.cz/vydani/" in xml
    assert "https://poslusnehlasim.cz/slovnicek/" in xml
    assert "https://poslusnehlasim.cz/slovnicek/obstrukce/" in xml
    assert "https://poslusnehlasim.cz/vydani/2026-06-26/" in xml
    assert "noviny/" not in xml
    assert "feed.xml" not in xml


def test_breadcrumb_json_ld() -> None:
    crumbs = (
        BreadcrumbCrumb(label=SITE_NAME, href="/"),
        BreadcrumbCrumb(label="Archiv vydání", href="/vydani/"),
        BreadcrumbCrumb(label="8. 7. 2026", href=""),
    )
    data = breadcrumb_json_ld(
        site_url="https://poslusnehlasim.cz",
        crumbs=crumbs,
    )
    assert data["@type"] == "BreadcrumbList"
    items = data["itemListElement"]
    assert len(items) == 3
    assert items[0]["name"] == SITE_NAME
    assert items[0]["item"] == "https://poslusnehlasim.cz/"
    assert items[1]["item"] == "https://poslusnehlasim.cz/vydani/"
    assert "item" not in items[2]


def test_breadcrumbs_ctx_edition_skips_homepage() -> None:
    empty = breadcrumbs_ctx_edition(
        site_url="https://poslusnehlasim.cz",
        datum_unl="08.07.2026",
        is_homepage=True,
    )
    assert empty["breadcrumbs"] == ()
    assert empty["breadcrumb_json_ld"] is None

    edition = breadcrumbs_ctx_edition(
        site_url="https://poslusnehlasim.cz",
        datum_unl="08.07.2026",
        is_homepage=False,
    )
    assert len(edition["breadcrumbs"]) == 3
    assert edition["breadcrumbs"][-1].label == "8. 7. 2026"
    assert edition["breadcrumb_json_ld"] is not None


def test_breadcrumbs_ctx_archiv_and_slovnicek() -> None:
    arch = breadcrumbs_ctx_archiv(site_url="https://poslusnehlasim.cz")
    assert arch["breadcrumbs"][-1].href == ""
    assert arch["breadcrumbs"][0].href == "/"

    sub = breadcrumbs_ctx_edition_subpage(
        site_url="https://poslusnehlasim.cz",
        obdobi=2025,
        schuze=45,
        datum_unl="08.07.2026",
        subpage_label="Stenoprotokol",
    )
    assert len(sub["breadcrumbs"]) == 4
    assert sub["breadcrumbs"][-1].label == "Stenoprotokol"
    assert "/vydani/2026-07-08/" in sub["breadcrumbs"][2].href

    gloss = breadcrumbs_ctx_slovnicek(site_url="https://poslusnehlasim.cz")
    assert gloss["breadcrumbs"][-1].label == "Švejkův slovníček"

    term = breadcrumbs_ctx_slovnicek_term(
        site_url="https://poslusnehlasim.cz",
        term_label="Obstrukce",
    )
    assert len(term["breadcrumbs"]) == 3
    assert term["breadcrumbs"][1].href == "/slovnicek/"
    assert term["breadcrumbs"][-1].label == "Obstrukce"


def test_slovnicek_term_json_ld() -> None:
    data = slovnicek_term_json_ld(
        url="https://poslusnehlasim.cz/slovnicek/obstrukce/",
        term="Obstrukce",
        answer="Zdržování jednání.",
        glossary_url="https://poslusnehlasim.cz/slovnicek/",
    )
    graph = data["@graph"]
    assert graph[0]["@type"] == "DefinedTerm"
    assert graph[0]["name"] == "Obstrukce"
    assert graph[1]["@type"] == "FAQPage"
    assert graph[1]["mainEntity"][0]["name"] == "Co je Obstrukce?"


def test_slovnicek_term_page_title() -> None:
    assert slovnicek_term_page_title("Obstrukce") == (
        "Co je Obstrukce? Švejkov slovníček | Poslušně hlásím"
    )
