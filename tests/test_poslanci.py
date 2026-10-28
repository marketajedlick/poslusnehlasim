from psp.poslanci import poslanec_registry


def test_kovarova_disambiguation():
    reg = poslanec_registry()
    assert "Kovářová (Piráti)" in reg.annotate("Kovářová mluvila o bydlení.")
    assert "Veronika Kovářová (Piráti)" in reg.annotate("Veronika Kovářová kritizovala novelu.")
    assert "Věra Kovářová (STAN)" in reg.annotate("Věra Kovářová podpořila návrh.")


def test_zenske_tvary_s_pohlavim_z_psp():
    # osoby.unl má u poslankyň "Ž"/"Z", ne "F".
    from psp.poslanci import _prijmeni_tvary

    for pohlavi in ("Ž", "Z", "F"):
        tvary = _prijmeni_tvary("Pošarová", pohlavi)
        assert {"Pošarové", "Pošarovou"} <= tvary, pohlavi
    assert "Pošarovou" not in _prijmeni_tvary("Pošarová", "M")


def test_pad_poslankyne_dostane_stranu():
    reg = poslanec_registry()
    assert "Pošarovou (" in reg.annotate("Jednal s Pošarovou o rozpočtu.")
