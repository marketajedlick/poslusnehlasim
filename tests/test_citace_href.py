from dataclasses import dataclass

from svejk.build.steno_sources import (
    StenoPassage,
    _passage_from_fact,
    find_passage_for_citace,
    passage_href,
    resolve_item_citace_href,
)
from svejk.paths import SchuzePaths


def _passage(**kwargs) -> StenoPassage:
    defaults = {
        "steno_id": "2025_24_01097",
        "anchor": "steno-2025_24_01097-p2",
        "speaker": "Vít Rakušan",
        "poradi": 1097,
        "topic_slug": "debata",
        "topic_title": "Debata",
        "article_num": 1,
        "summary": "Rakušan: pomsta",
        "citace": "možná v kontextu té dnešní doby bych to nazval lex pomsta",
        "excerpt": "…",
        "psp_url": "https://www.psp.cz/eknih/2025ps/stenprot/024schuz/s024246.htm#r2",
        "source": "steno",
    }
    defaults.update(kwargs)
    return StenoPassage(**defaults)


def test_find_passage_for_citace_matches_quote_text():
    passages = [_passage()]
    hit = find_passage_for_citace(
        passages,
        citace_text="nazval lex pomsta",
        citace_href="https://www.psp.cz/eknih/2025ps/stenprot/024schuz/s024246.htm#r9",
    )
    assert hit is passages[0]


def test_find_passage_for_citace_matches_psp_url_without_anchor():
    passages = [_passage()]
    hit = find_passage_for_citace(
        passages,
        citace_text="",
        citace_href="https://www.psp.cz/eknih/2025ps/stenprot/024schuz/s024246.htm#r9",
    )
    assert hit is passages[0]


def test_resolve_item_citace_href_points_to_steno_page():
    @dataclass
    class Item:
        citace_text: str = "Tohle je msta, která se bojí denního světla."
        citace_href: str = "https://www.psp.cz/eknih/2025ps/stenprot/024schuz/s024246.htm#r2"

    item = Item()
    passage = _passage(
        citace="Tohle je msta, která se bojí denního světla, to, co tady předvádíte.",
    )
    resolve_item_citace_href(item, [passage], "/2025/s24/01-07/steno")
    assert item.citace_href == passage_href(passage, "/2025/s24/01-07/steno")


def test_passage_from_fact_skips_orphan_editorial_notes():
    paths = SchuzePaths.create(2025, 24)
    assert (
        _passage_from_fact(
            {"text": "Malá chtěla jednat do 19. a 21. hodiny."},
            paths=paths,
            steno_by_id={},
            topic_slug="debata",
            topic_title="Debata",
            article_num=1,
            passage_idx=0,
        )
        is None
    )
    assert (
        _passage_from_fact(
            {"text": "z glosy", "source": "manual"},
            paths=paths,
            steno_by_id={},
            topic_slug="debata",
            topic_title="Debata",
            article_num=1,
            passage_idx=1,
        )
        is None
    )


def test_resolve_item_citace_href_falls_back_to_steno_page():
    @dataclass
    class Item:
        citace_text: str = "Neznámá citace."
        citace_href: str = "https://www.psp.cz/eknih/2025ps/stenprot/024schuz/s024999.htm#r2"

    item = Item()
    resolve_item_citace_href(item, [_passage()], "/2025/s24/01-07/steno")
    assert item.citace_href == "/2025/s24/01-07/steno"
