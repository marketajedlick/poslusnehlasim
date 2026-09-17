"""Samostatná subscribe stránka."""

from svejk.build.html import render_subscribe_html


def test_subscribe_page_has_form():
    html = render_subscribe_html(2025, base_path="")
    assert "subscribe-form" in html
    assert "Poslušně odebírat" in html
    assert 'name="email"' in html
    assert 'content="noindex"' in html
    assert 'toolname="subscribe_newsletter"' in html
    assert "tooldescription=" in html
    assert 'toolparamdescription="E-mailová adresa pro odběr newsletteru"' in html
    assert "oldstandardtt-400-latin-ext.woff2" in html
    assert 'rel="preload"' in html
    assert 'as="font"' in html
    # honeypot nesmí být WebMCP parametrem
    assert 'name="_hp"' not in html
