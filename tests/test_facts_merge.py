"""Opakovaný extract / edition brief nesmí mazat ruční práci."""

from svejk.build.facts_merge import merge_day, merge_topic


def test_topic_keeps_manual_verdikt_and_unknown_keys():
    existing = {
        "lead": "Ruční lead.",
        "verdikt": "prvni_cteni",
        "proslo": False,
        "citace2_text": "Druhá citace.",
        "pointa_tail": "Dovětek.",
        "steno_id": "2025_20_00011",
        "pocet_hlasovani": 1,
    }
    fresh = {"lead": "", "verdikt": "schvaleno", "proslo": True, "pocet_hlasovani": 4, "nadpis": "Prošlo to"}
    out = merge_topic(existing, fresh)
    assert out["verdikt"] == "prvni_cteni"
    assert out["proslo"] is False
    assert out["citace2_text"] == "Druhá citace."
    assert out["pointa_tail"] == "Dovětek."
    assert out["steno_id"] == "2025_20_00011"
    assert out["pocet_hlasovani"] == 4  # data se obnoví
    assert out["nadpis"] == "Prošlo to"  # chybějící klíč se doplní


def test_topic_without_manual_work_is_regenerated():
    existing = {"nadpis": "Prošlo to", "verdikt": "schvaleno", "fakty": [{"source": "steno"}]}
    fresh = {"nadpis": "Prošlo", "verdikt": "zamiteno", "fakty": []}
    assert merge_topic(existing, fresh) == fresh


def test_topic_publikovat_false_survives():
    out = merge_topic({"lead": "x", "publikovat": False}, {"publikovat": True})
    assert out["publikovat"] is False


def test_day_keeps_jazykolam_slovnicek_labels():
    existing = {
        "zaver": "že …",
        "jazykolam": {"text": "Strč prst"},
        "slovnicek": ["veto"],
        "board_left_label": "Prošlo",
        "steno_zdroje": True,
        "stats": {"proslo": 9},
    }
    fresh = {"topic_slugs": ["a"], "stats": {"proslo": 1, "pocet_hlas": 3}}
    out = merge_day(existing, fresh)
    assert out["jazykolam"] == {"text": "Strč prst"}
    assert out["slovnicek"] == ["veto"]
    assert out["board_left_label"] == "Prošlo"
    assert out["topic_slugs"] == ["a"]
    assert out["stats"] == {"proslo": 1, "pocet_hlas": 3}


def test_day_skore_manual_keeps_counts():
    existing = {"zaver": "že", "skore_manual": True, "stats": {"proslo": 2, "zamitnuto": 1}}
    fresh = {"stats": {"proslo": 5, "zamitnuto": 0, "pocet_hlas": 7}}
    out = merge_day(existing, fresh)
    assert out["stats"] == {"proslo": 2, "zamitnuto": 1, "pocet_hlas": 7}
