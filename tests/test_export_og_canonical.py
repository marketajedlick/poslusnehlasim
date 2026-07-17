"""OG/share pro den s více schůzemi musí brát kanonické vydání."""

from svejk.build.nav import resolve_edition
from svejk.build.publish import list_site_editions


def test_duplicate_date_og_uses_canonical_schuze() -> None:
    day = "07.07.2026"
    matches = [e for e in list_site_editions(2025) if e.datum_unl == day]
    assert len(matches) >= 2, "fixture: 7. 7. 2026 má s24 i s25"
    assert matches[0].schuze == 24
    canonical = resolve_edition(2025, day)
    assert canonical is not None
    assert canonical.schuze == matches[-1].schuze == 25
