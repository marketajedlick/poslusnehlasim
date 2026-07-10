from svejk.build.day_content import edition_day_meta, datum_day_month
from svejk.strings import load_strings


def test_homepage_strings() -> None:
    t = load_strings()
    assert "homepage" in t
    assert "Poslanecké sněmovny" in t["homepage"]["h1"]
    assert "poslanci hlasovali" in t["homepage"]["intro"]


def test_edition_day_meta() -> None:
    assert (
        edition_day_meta("úterý", "02.07.2026")
        == "Poslanecká sněmovna, Úterý 2. července 2026"
    )


def test_datum_day_month() -> None:
    assert datum_day_month("02.07.2026") == "2. července"


def test_nadpis_export_capitalizes() -> None:
    from svejk.build.day_content import _sanitize_nadpis_export

    assert _sanitize_nadpis_export("k pultu") == "K pultu"
    assert _sanitize_nadpis_export("Lex ukrajina") == "Lex ukrajina"
