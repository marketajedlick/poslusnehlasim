from dataclasses import dataclass

from psp.poslanci import Poslanec
from svejk.validate.names import (
    audit_day,
    audit_text,
    is_vote_score,
    party_matches,
)


@dataclass
class _FakeIndex:
    poslanci: dict[str, Poslanec]

    def resolve(self, name: str):
        name = name.strip()
        parts = name.split()
        if len(parts) >= 2:
            return self.poslanci.get(f"{parts[0]} {parts[-1]}".lower())
        matches = [
            p for p in self.poslanci.values() if p.prijmeni.lower() == name.lower()
        ]
        return matches[0] if len(matches) == 1 else None

    def expected_party(self, poslanec: Poslanec) -> str:
        if (poslanec.jmeno, poslanec.prijmeni) == ("Gabriela", "Svárovská"):
            return "Zelení, klub Pirátů"
        return poslanec.klub


def _fake_index() -> _FakeIndex:
    return _FakeIndex(
        {
            "jan papajanovský": Poslanec("Jan", "Papajanovský", "Motoristé", "M"),
            "petr bendl": Poslanec("Petr", "Bendl", "ODS", "M"),
            "gabriela svárovská": Poslanec("Gabriela", "Svárovská", "Piráti", "F"),
        }
    )


def test_wrong_party_detected():
    idx = _fake_index()
    issues = audit_text(
        "Papajanovský (STAN) mluvil za starosty.",
        index=idx,
        slug="eet",
        context="lead",
    )
    assert len(issues) == 1
    assert issues[0].code == "wrong_party"
    assert "Motoristé" in issues[0].message


def test_correct_party_ok():
    idx = _fake_index()
    issues = audit_text("Bendl (ODS) chtěl pojistky.", index=idx)
    assert issues == []


def test_vote_score_ignored():
    idx = _fake_index()
    issues = audit_text("Skóre bylo (154:0).", index=idx)
    assert issues == []


def test_party_matches_display_override():
    assert party_matches("Zelení, klub Pirátů", "Zelení, klub Pirátů")
    assert party_matches("Zelení, klub Pirátů", "Zelení")


def test_svárovská_display_override():
    idx = _fake_index()
    issues = audit_text(
        "Svárovská (Zelení, klub Pirátů) hlasovala proti.",
        index=idx,
    )
    assert issues == []


def test_audit_day_vysledek():
    idx = _fake_index()
    day = {
        "dnesni_ucet": "Bendl (ODS) tlačil na pojistky.",
        "vysledek": ["* EET: Papajanovský (Motoristé) varoval."],
        "zaver": "že Bendl (ODS) a Papajanovský (Motoristé) se hádali.",
    }
    issues = audit_day(day, index=idx)
    assert all(i.code != "wrong_party" for i in issues)


def test_is_vote_score():
    assert is_vote_score("154:0")
    assert not is_vote_score("ODS")
