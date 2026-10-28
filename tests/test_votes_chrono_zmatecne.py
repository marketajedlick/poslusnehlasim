"""Zmatečná hlasování a řazení hlasování podle data (DD.MM.YYYY)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from psp.schuze import SchuzeAnalyzer
from svejk.build.vote_logic import topic_proslo_from_votes
from svejk.jednaci_den import datum_unl_key, vote_chrono_key

ROOT = Path(__file__).resolve().parents[1]


def _row(id_, cislo, datum, cas, vysledek, nazev="Novela z. o podpoře bydlení", pritomno=180):
    pro = 120 if vysledek == "A" else 40
    proti = 180 - pro
    return (
        f"{id_}|174|17|{cislo}|2|{datum}|{cas}|{pro}|{proti}|0|0|{pritomno}|91|N|{vysledek}|{nazev}||"
    )


def _analyzer(tmp_path: Path, rows: list[str], zmatecne: list[str] | None = None) -> SchuzeAnalyzer:
    d = tmp_path / "hl-2025ps"
    d.mkdir()
    (d / "hl2025s.unl").write_text("\n".join(rows) + "\n", encoding="cp1250")
    if zmatecne is not None:
        (d / "zmatecne.unl").write_text("".join(f"{z}|\n" for z in zmatecne), encoding="cp1250")
    return SchuzeAnalyzer(tmp_path, "174")


def test_load_votes_chronological_across_month(tmp_path):
    a = _analyzer(
        tmp_path,
        [
            _row(3, 30, "03.06.2026", "10:00", "A"),
            _row(1, 10, "29.05.2026", "11:00", "R"),
            _row(2, 20, "29.05.2026", "12:00", "R"),
        ],
    )
    votes = a.load_votes(2025, 17)
    assert [v.cislo for v in votes] == [10, 20, 30]
    topic = a._summarize_topics(votes)[0]
    assert topic.posledni_hlasovani.datum == "03.06.2026"
    assert topic.posledni_hlasovani.vysledek == "A"


def test_load_votes_skips_zmatecne(tmp_path):
    a = _analyzer(
        tmp_path,
        [
            _row(87371, 68, "06.05.2026", "21:17", "A", pritomno=75),
            _row(87372, 69, "06.05.2026", "21:20", "A", pritomno=103),
        ],
        zmatecne=["10003", "87371"],
    )
    votes = a.load_votes(2025, 17)
    assert [v.cislo for v in votes] == [69]
    assert a.analyze(2025, 17).temata[0].pocet_hlasovani == 1


def test_load_votes_without_zmatecne_file(tmp_path):
    a = _analyzer(tmp_path, [_row(1, 1, "01.07.2026", "10:00", "A")])
    assert len(a.load_votes(2025, 17)) == 1


def test_analyze_dny_chronological(tmp_path):
    a = _analyzer(
        tmp_path,
        [_row(1, 1, "29.05.2026", "10:00", "A"), _row(2, 2, "03.06.2026", "10:00", "A")],
    )
    assert list(a.analyze(2025, 17).dny) == ["29.05.2026", "03.06.2026"]


def test_vote_chrono_key_and_datum_key():
    votes = [
        {"datum": "01.07.2026", "cas": "00:30", "cislo": 3},
        {"datum": "30.06.2026", "cas": "23:50", "cislo": 2},
        {"datum": "30.06.2026", "cas": "10:00", "cislo": 1},
    ]
    assert [v["cislo"] for v in sorted(votes, key=vote_chrono_key)] == [1, 2, 3]
    assert sorted(["03.06.2026", "29.05.2026"], key=datum_unl_key) == ["29.05.2026", "03.06.2026"]


def test_topic_proslo_uses_chronological_order():
    group = [
        {"datum": "03.06.2026", "cas": "10:00", "cislo": 30, "vysledek": "A", "pro": 120, "proti": 60},
        {"datum": "29.05.2026", "cas": "11:00", "cislo": 10, "vysledek": "R", "pro": 40, "proti": 140},
    ]
    assert topic_proslo_from_votes(group) is True


def _load_fix_steno_published():
    spec = importlib.util.spec_from_file_location(
        "fix_steno_published", ROOT / "scripts" / "fix_steno_published.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_fix_steno_published_keeps_unverifiable_steno_id():
    mod = _load_fix_steno_published()
    fact = {"citace": "Tohle ve stenu není.", "steno_id": "2025_17_00999", "link_phrase": "x", "source": "steno"}
    rows = [{"id": "2025_17_00001", "datum": "2026-05-29", "text": "Úplně jiný projev."}]
    by_id = {r["id"]: r for r in rows}
    assert mod.fix_fact(fact, rows, by_id, ["2026-05-29"]) is False
    assert fact["steno_id"] == "2025_17_00999"
    assert fact["link_phrase"] == "x"


def test_fix_steno_published_strips_verified_mismatch():
    mod = _load_fix_steno_published()
    fact = {"citace": "Tohle ve stenu není.", "steno_id": "2025_17_00001", "link_phrase": "x", "source": "steno"}
    rows = [{"id": "2025_17_00001", "datum": "2026-05-29", "text": "Úplně jiný projev."}]
    by_id = {r["id"]: r for r in rows}
    assert mod.fix_fact(fact, rows, by_id, ["2026-05-29"]) is False
    assert "steno_id" not in fact


def test_fix_steno_published_norm_curly_quotes():
    mod = _load_fix_steno_published()
    assert mod.norm("„A“ “B”") == '"a" "b"'
