"""Test edition state merge a fingerprint."""

from svejk.edition.state import (
    compute_input_fingerprint,
    merge_day_skeleton,
    merge_topic_skeleton,
)


def test_merge_topic_preserves_lead():
    existing = {"lead": "Hotový lead.", "pointa": "Pointa.", "fakty": [{"citace": "x"}]}
    fresh = {"lead": "Nový.", "fakty": [], "priorita": 1}
    out = merge_topic_skeleton(existing, fresh)
    assert out["lead"] == "Hotový lead."
    assert out["fakty"] == [{"citace": "x"}]
    assert out["priorita"] == 1


def test_merge_day_preserves_zaver():
    existing = {"dnesni_ucet": "řádek1\nřádek2", "zaver": "že den skončil."}
    fresh = {"topic_slugs": ["a"], "stats": {"proslo": 1}}
    out = merge_day_skeleton(existing, fresh)
    assert out["zaver"] == "že den skončil."
    assert out["topic_slugs"] == ["a"]


def test_fingerprint_stable_key():
    fp = compute_input_fingerprint
    # bez souborů vrátí nuly, ale fingerprint string existuje
    class P:
        votes_jsonl = type("F", (), {"is_file": lambda self: False})()
        steno_jsonl = type("F", (), {"is_file": lambda self: False})()
        topics_json = type("F", (), {"is_file": lambda self: False})()

    data = fp(P())  # type: ignore[arg-type]
    assert "fingerprint" in data
