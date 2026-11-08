from svejk.edition.social import build_ig_caption


def test_zaver_ze_prefix_stripped_and_capitalized():
    caption = build_ig_caption(
        datum_unl="05.11.2026",
        dnesni_ucet="Účet dne.",
        zaver="že premiér přišel odpovídat.",
    )
    assert caption.splitlines()[2] == "Premiér přišel odpovídat."


def test_zaver_without_ze_unchanged():
    caption = build_ig_caption(
        datum_unl="04.11.2026",
        dnesni_ucet="Účet dne.",
        zaver="Sněmovna schválila zákon.",
    )
    assert caption.splitlines()[2] == "Sněmovna schválila zákon."
