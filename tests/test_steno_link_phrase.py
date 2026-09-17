from svejk.build.steno_sources import _find_phrase_in_text, inject_steno_link, steno_sources_href


def test_phrase_with_party_labels():
    text = "Lang (ANO) Hřibovi (Piráti) připomněl, že už není primátorem."
    assert _find_phrase_in_text(text, "Lang Hřibovi připomněl") == "Lang (ANO) Hřibovi (Piráti) připomněl"


def test_inject_steno_link_with_party_labels():
    text = "Kolovratník (ANO) se ptal, kde je férovost."
    out = inject_steno_link(text, "Kolovratník se ptal", "/steno/#x")
    assert 'class="steno-link"' in out
    assert "Kolovratník (ANO) se ptal" in out


def test_file_mode_steno_href_is_local_html():
    assert (
        steno_sources_href(2025, 30, "09.09.2026", link_mode="file")
        == "2026-09-09-steno.html"
    )


def test_phrase_with_party_labels():
    text = "Lang (ANO) Hřibovi (Piráti) připomněl, že už není primátorem."
    assert _find_phrase_in_text(text, "Lang Hřibovi připomněl") == "Lang (ANO) Hřibovi (Piráti) připomněl"


def test_inject_steno_link_with_party_labels():
    text = "Kolovratník (ANO) se ptal, kde je férovost."
    out = inject_steno_link(text, "Kolovratník se ptal", "/steno/#x")
    assert 'class="steno-link"' in out
    assert "Kolovratník (ANO) se ptal" in out
