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
