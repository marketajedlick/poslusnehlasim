from psp.steno_web import PspStenoFetcher


def test_anchor_for_citace_in_page_finds_later_speech_block():
    html = """
    <p><b><a id="r4">Filip Turek</a></b>: Začátek projevu o parodii.</p>
    <p>Pokračování o větru.</p>
    <p><b><a id="r9">Marian Jurečka</a></b>: Jiný řečník.</p>
    <p><b><a id="r12">Filip Turek</a></b>: Fouká u nás totiž 20 procent času.</p>
    """
    fetcher = PspStenoFetcher(rate_limit_s=0)
    anchor = fetcher._anchor_for_citace_in_page(
        html,
        "Fouká u nás totiž 20 procent času a ještě tak drze.",
        default="r4",
    )
    assert anchor == "r12"


def test_anchor_for_citace_in_page_keeps_default_when_missing():
    html = """
    <p><b><a id="r4">Filip Turek</a></b>: Jen úvod.</p>
    """
    fetcher = PspStenoFetcher(rate_limit_s=0)
    anchor = fetcher._anchor_for_citace_in_page(
        html,
        "Tahle citace na stránce není.",
        default="r4",
    )
    assert anchor == "r4"
