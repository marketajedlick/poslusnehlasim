from svejk.build.steno_sources import _load_steno_index, steno_record
from svejk.paths import SchuzePaths


def test_quote_from_other_sitting_resolves_speaker():
    paths = SchuzePaths.create(2025, 34)
    other = SchuzePaths.create(2025, 35)
    if not paths.steno_jsonl.is_file() or not other.steno_jsonl.is_file():
        return
    local = _load_steno_index(paths)
    rec = steno_record(paths, "2025_35_00024", local)
    assert rec.get("cele_jmeno") == "Karel Dvořák"
    assert "s035" in (rec.get("url") or "")
