"""Inline fonts.css: relativní url(fonts/…) → absolutní pod /static/."""

from __future__ import annotations

from svejk.build.html import fonts_css_inline


def test_fonts_css_inline_rewrites_font_urls() -> None:
    css = fonts_css_inline("/static/fonts.css?v=abc")
    assert "url('/static/fonts/archivo-latin.woff2')" in css
    assert "url('fonts/" not in css
    assert "@font-face" in css


def test_fonts_css_inline_respects_base_path() -> None:
    css = fonts_css_inline("/repo/static/fonts.css")
    assert "url('/repo/static/fonts/archivo-latin.woff2')" in css


def test_fonts_css_inline_empty_href() -> None:
    assert fonts_css_inline("") == ""
