"""Zmrazení publikovaných vydání: drift proti snapshotu, sdílená témata, gate."""

import json
from pathlib import Path

from svejk.edition.freeze import (
    check_approved_not_published,
    check_published_drift,
    check_shared_topic_slugs,
    edition_content_hash,
    edition_drift,
)
from svejk.validate.names import party_matches


class _Paths:
    def __init__(self, root: Path):
        self.facts_by_day = root / "facts" / "by_day"
        self.facts_by_topic = root / "facts" / "by_topic"
        self.facts_by_day.mkdir(parents=True)
        self.facts_by_topic.mkdir(parents=True)


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def test_drift_detects_changed_and_swapped_topics(tmp_path):
    paths = _Paths(tmp_path / "live")
    snap = tmp_path / "snap"
    _write(paths.facts_by_day / "2026-06-30.json", {"topic_slugs": ["a"]})
    _write(paths.facts_by_topic / "a.json", {"lead": "x"})
    _write(snap / "facts/by_day/2026-06-30.json", {"topic_slugs": ["a"]})
    _write(snap / "facts/by_topic/a.json", {"lead": "x"})
    assert edition_drift(paths, "2026-06-30", snap) == []

    # formátování JSON nehraje roli
    (paths.facts_by_topic / "a.json").write_text('{"lead":"x"}', encoding="utf-8")
    assert edition_drift(paths, "2026-06-30", snap) == []

    _write(paths.facts_by_topic / "a.json", {"lead": "y"})
    assert edition_drift(paths, "2026-06-30", snap) == ["facts/by_topic/a.json"]
    h1 = edition_content_hash(paths, "2026-06-30")
    _write(paths.facts_by_topic / "a.json", {"lead": "z"})
    assert edition_content_hash(paths, "2026-06-30") != h1


def test_repo_published_editions_match_snapshots():
    """Publikované vydání se mění jen přes edition republish."""
    assert check_published_drift(2025) == []
    assert check_shared_topic_slugs(2025) == []
    assert check_approved_not_published(2025) == []


def test_party_matches_strict():
    assert party_matches("ODS", "ODS")
    assert party_matches("Zelení, klub Pirátů", "Zelení")
    assert not party_matches("STAN", "Piráti")
    assert not party_matches("KDU-ČSL", "KDU")


def test_bod_v_zavorce_neni_strana():
    from svejk.validate.names import is_vote_score

    assert is_vote_score("105:64")
    assert is_vote_score("bod 63")
    assert is_vote_score("sněmovní tisk 77")
    assert not is_vote_score("ANO")
    assert not is_vote_score("TOP 09")


def test_citace_autor_s_poznamkou_neni_chyba():
    from svejk.validate.names import audit_topic

    topic = {"slug": "x", "citace_autor": "Eva Decroix (ODS), cituje Wünschovou", "steno_id": "s1"}
    issues = audit_topic(topic, steno_by_id={"s1": {"cele_jmeno": "Eva Decroix"}})
    assert not [i for i in issues if i.code == "citace_autor_spelling"]
