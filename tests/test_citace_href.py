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


def test_collect_steno_sources_adds_citace_text_passage(tmp_path, monkeypatch):
    """Top-level citace_text musí mít vlastní kotvu, i když fakty[] citují jiný úsek."""
    from svejk.build.io import write_json
    from svejk.build.steno_sources import collect_steno_sources, find_passage_for_citace
    from svejk.paths import SchuzePaths

    paths = SchuzePaths.create(2025, 99)
    monkeypatch.setattr(
        "svejk.build.steno_sources.SchuzePaths.create",
        lambda ob, sch: paths,
    )
    paths.raw.mkdir(parents=True, exist_ok=True)
    paths.aligned.mkdir(parents=True, exist_ok=True)
    paths.facts_by_day.mkdir(parents=True, exist_ok=True)
    paths.facts_by_topic.mkdir(parents=True, exist_ok=True)

    steno_id = "2025_99_00001"
    full = (
        "Já už jsem se tady zabýval spoustou motoristických trafik na MŽP, "
        "ale toto mě skutečně překvapilo. Skutečně to vyvolává dojem o politické trafice."
    )
    write_json(
        paths.aligned / "steno_refs.json",
        {
            steno_id: {
                "url": "https://www.psp.cz/eknih/2025ps/stenprot/099schuz/s099001.htm#r1",
                "cele_jmeno": "Martin Šmída",
                "poradi": 1,
                "text": full,
            }
        },
    )
    slug = "interpelace-test"
    write_json(
        paths.facts_by_day / "2026-07-02.json",
        {"topic_slugs": [slug], "steno_zdroje": True},
    )
    write_json(
        paths.facts_by_topic / f"{slug}.json",
        {
            "slug": slug,
            "publikovat": True,
            "nadpis": "Test",
            "citace_text": "Já už jsem se tady zabýval spoustou motoristických trafik na MŽP, ale toto mě skutečně…",
            "steno_id": steno_id,
            "fakty": [
                {
                    "source": "steno",
                    "steno_id": steno_id,
                    "citace": "politickou trafiku pro bývalého poslance.",
                    "text": "Šmída pojmenoval trafiku.",
                }
            ],
        },
    )

    blocks = collect_steno_sources(paths, "02.07.2026")
    passages = blocks[0].passages
    assert len(passages) == 2
    assert passages[0].citace.startswith("Já už jsem se tady zabýval")
    hit = find_passage_for_citace(
        passages,
        citace_text="Já už jsem se tady zabýval spoustou motoristických trafik na MŽP, ale toto mě skutečně…",
    )
    assert hit is passages[0]
