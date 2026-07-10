from svejk.build.day_content import edition_day_meta
from svejk.strings import load_strings


def test_homepage_strings() -> None:
    t = load_strings()
    assert "homepage" in t
    assert "Poslanecké sněmovny" in t["homepage"]["h1"]
    assert "poslanci hlasovali" in t["homepage"]["intro"]


def test_edition_day_meta() -> None:
    assert (
        edition_day_meta("úterý", "02.07.2026", 45)
        == "Poslanecká sněmovna, Úterý 2. července 2026 · 45. schůze"
    )
