"""Stránky pojmů slovníčku: aliasy, duplicity, rozšířený obsah."""

from svejk.glossary import (
    SLOVNICEK_DETAIL,
    SLOVNICEK_META,
    SLOVNICEK_SLUG_ALIASES,
    slovnicek_anchor,
    slovnicek_detail,
    slovnicek_entries,
    slovnicek_pages,
    slovnicek_term_slug,
)


def test_alias_points_to_canonical_page() -> None:
    assert slovnicek_term_slug("elektronická evidence tržeb") == "eet"
    assert slovnicek_term_slug("EET") == "eet"
    assert slovnicek_detail("elektronicka-evidence-trzeb") is SLOVNICEK_DETAIL["eet"]


def test_pages_have_unique_slugs_and_skip_aliases() -> None:
    slugs = [slovnicek_anchor(t) for t, _ in slovnicek_pages()]
    assert len(slugs) == len(set(slugs))
    assert not set(slugs) & set(SLOVNICEK_SLUG_ALIASES)
    # aliasy zůstávají v SLOVNIČEK kvůli značkování textů
    assert "elektronicka-evidence-trzeb" in {slovnicek_anchor(t) for t, _ in slovnicek_entries()}


def test_detail_entries_are_valid() -> None:
    page_slugs = {slovnicek_anchor(t) for t, _ in slovnicek_pages()}
    for slug, detail in SLOVNICEK_DETAIL.items():
        assert slug in page_slugs, slug
        assert len(detail.get("title", "")) <= 60, slug
        assert detail["sections"], slug
        for heading, body in detail["sections"]:
            assert heading.endswith("?"), heading
            assert len(body) > 60
        for rel in detail.get("related", ()):
            assert slovnicek_term_slug(rel) in page_slugs, (slug, rel)


def test_every_page_has_meta_of_bing_length() -> None:
    """Bing Site Scan: meta description pod 150 znaků je „too short“, nad 160 se ořízne."""
    from svejk.glossary import slovnicek_meta

    page_slugs = {slovnicek_anchor(t) for t, _ in slovnicek_pages()}
    assert set(SLOVNICEK_META) == page_slugs
    for slug in page_slugs:
        meta = slovnicek_meta(slug)
        assert 150 <= len(meta) <= 160, (slug, len(meta))
        assert meta == " ".join(meta.split()), slug
    assert slovnicek_meta("elektronicka-evidence-trzeb") == slovnicek_meta("eet")


def test_plain_strips_leftover_links() -> None:
    from svejk.build.slovnicek_index import _plain

    raw = 'k <a href="https://psp.cz/x#uzbach-6">příspěvek na mobilitu</a> &amp; péči'
    assert _plain(raw) == "k příspěvek na mobilitu & péči"


def test_no_long_dashes_in_glossary_texts() -> None:
    """Export odmítá —/– ve výstupu, hlídáme to už ve zdrojových textech."""
    from svejk.glossary import GLOSSARY, SLOVNIČEK

    texts = [t for pair in (*GLOSSARY, *SLOVNIČEK) for t in pair]
    texts += list(SLOVNICEK_META.values())
    for d in SLOVNICEK_DETAIL.values():
        texts.append(d.get("title", ""))
        texts += [t for pair in d["sections"] for t in pair]
    bad = [t for t in texts if "—" in t or "–" in t]
    assert not bad, bad
