"""Samostatná subscribe stránka."""

from svejk.build.html import render_subscribe_html


def test_subscribe_page_has_form():
    html = render_subscribe_html(2025, base_path="")
    assert "subscribe-form" in html
    assert "Poslušně odebírat" in html
    assert 'name="email"' in html
    assert 'content="noindex"' in html
