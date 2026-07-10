from svejk.build.steno_sources import _find_phrase_in_text, inject_steno_link


def test_phrase_with_party_labels():
    text = "Lang (ANO) Hřibovi (Piráti) připomněl, že už není primátorem."
    assert _find_phrase_in_text(text, "Lang Hřibovi připomněl") == "Lang (ANO) Hřibovi (Piráti) připomněl"


def test_inject_steno_link_with_party_labels():
    text = "Kolovratník (ANO) se ptal, kde je férovost."
    out = inject_steno_link(text, "Kolovratník se ptal", "/steno/#x")
    assert 'class="steno-link"' in out
    assert "Kolovratník (ANO) se ptal" in out
