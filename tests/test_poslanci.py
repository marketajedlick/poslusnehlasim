from psp.poslanci import poslanec_registry


def test_kovarova_disambiguation():
    reg = poslanec_registry()
    assert "Kovářová (Piráti)" in reg.annotate("Kovářová mluvila o bydlení.")
    assert "Veronika Kovářová (Piráti)" in reg.annotate("Veronika Kovářová kritizovala novelu.")
    assert "Věra Kovářová (STAN)" in reg.annotate("Věra Kovářová podpořila návrh.")
