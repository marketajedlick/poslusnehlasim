from svejk.build.glossary_markup import strip_glossary_markup


def test_strip_glossary_markup_keeps_label_only() -> None:
    html = (
        'Šest <span class="term-tip" tabindex="0" role="term" '
        'aria-label="Souhlas Sněmovny se smlouvou s jiným státem. '
        'Teprve po něm smlouva v Česku platí.">ratifikací'
        '<span class="term-tip-bubble" role="tooltip">Souhlas Sněmovny se '
        "smlouvou s jiným státem. Teprve po něm smlouva v Česku platí."
        "</span></span> odsouhlaseno jako na páse"
    )
    assert strip_glossary_markup(html) == "Šest ratifikací odsouhlaseno jako na páse"


def test_glossary_markup_skips_inline_terms() -> None:
    from svejk.build.glossary_markup import glossary_markup

    out = str(glossary_markup("Barták (Motoristé) mluvil o interpelaci."))
    assert "term-term" not in out
    assert "(Motoristé)" in out
    assert "interpelaci" in out
