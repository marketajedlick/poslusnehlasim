"""Stránky zákonů: data se načtou, citace sedí na steno, HTML se vyrenderuje."""

import warnings

from svejk.build.zakony import list_zakony, zakon_for_topic
from svejk.build.zakony_html import render_zakon_html, render_zakony_index_html
from svejk.text_norm import ma_dlouhou_pomlcku


def test_zakony_citace_sedi_na_steno():
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        zakony = list_zakony()
    assert zakony, "processed/zakony/ je prázdné"
    for z in zakony:
        for side in ("vlada", "opozice"):
            for c in z[side].get("citace", []):
                assert c.get("href", "").startswith("https://www.psp.cz/"), c


def test_zakon_render_a_odkaz_z_clanku():
    for z in list_zakony():
        html = render_zakon_html(2025, z)
        assert "zakon-flow" in html and "zakon-side--opozice" in html
        assert not ma_dlouhou_pomlcku(html)
        for slug in z.get("temata", []):
            assert zakon_for_topic(slug) == (z["href"], z.get("nazev_kratky") or z["nazev"])
    assert "zakony-card" in render_zakony_index_html(2025)
