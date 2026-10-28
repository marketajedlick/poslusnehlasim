"""Obnova neautorizovaného stena: strop dotazů a vracené počty."""

import json

from svejk.build.fetch import refresh_steno_rows


class _Rec:
    def __init__(self, rid, text):
        self.id, self.poradi, self.obdobi, self.schuze = rid, int(rid[-5:]), 2025, 1
        self.datum, self.cele_jmeno, self.tema, self.text = "2026-01-01T10:00:00", "X", "", text
        self.pocet_slov, self.url, self.cislo_hlasovani = len(text.split()), "", None


class _Client:
    def __init__(self):
        self.calls = 0

    def fetch_steno(self, rid):
        self.calls += 1
        return _Rec(rid, "autorizovaný text")


def test_refresh_respects_budget(tmp_path):
    path = tmp_path / "steno.jsonl"
    rows = [
        {"id": f"2025_1_{i:05d}", "poradi": i, "datum": "2026-01-01T10:00:00",
         "text": "*** Neprošlo jazykovou korekturou, neautorizováno! ***"}
        for i in range(1, 11)
    ]
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    client = _Client()
    changed, asked = refresh_steno_rows(client, path, max_records=3, verbose=False)
    assert asked == client.calls == 3
    assert changed == 3
    # podruhé se tytéž záznamy do týdne znovu neptají
    changed2, asked2 = refresh_steno_rows(client, path, max_records=3, verbose=False)
    assert asked2 == 3 and client.calls == 6
