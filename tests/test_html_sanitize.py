from svejk.build.day_content import (
    _filter_allowed_html_tag,
    _sanitize_mean_export,
    _sanitize_text_export,
)


def test_sanitize_strips_script_tags():
    text = "Ahoj <script>alert('x')</script> světe"
    out = _sanitize_text_export(text)
    assert "<script>" not in out.lower()
    assert "alert('x')" in out


def test_sanitize_keeps_strong():
    text = "Turek řekl: <strong>„Citát.“</strong> Pak odešel."
    out = _sanitize_text_export(text)
    assert "<strong>„Citát.“</strong>" in out


def test_sanitize_strips_onerror_img():
    text = 'Text <img src=x onerror="alert(1)"> konec'
    out = _sanitize_text_export(text)
    assert "<img" not in out.lower()
    assert "Text" in out and "konec" in out


def test_sanitize_keeps_steno_link():
    href = "https://www.psp.cz/eknih/cdrom/2025/test"
    text = f'Podle <a class="steno-link" href="{href}">Turka</a> to tak bylo.'
    out = _sanitize_text_export(text)
    assert f'<a class="steno-link" href="{href}">Turka</a>' in out


def test_sanitize_strips_javascript_href():
    text = '<a class="mean-link" href="javascript:alert(1)">odkaz</a>'
    out = _sanitize_mean_export(text)
    assert "<a" not in out
    assert "odkaz" in out


def test_filter_rejects_inline_tag_attributes():
    assert _filter_allowed_html_tag('<strong class="x">') == ""
    assert _filter_allowed_html_tag("<strong>") == "<strong>"
