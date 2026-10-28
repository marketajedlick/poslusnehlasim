"""Regrese k opravám z review (podstránky dvou schůzí, PSP kotvy, hidden, newsletter, fetch)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from svejk.build.nav import (
    Edition,
    recnici_pages_href,
    smlouvy_pages_href,
    steno_sources_pages_href,
    vyznamenani_pages_href,
)
from svejk.paths import SchuzePaths


def _ed(datum_unl: str, schuze: int) -> Edition:
    when = datetime.strptime(datum_unl, "%d.%m.%Y").replace(tzinfo=timezone.utc)
    return Edition(obdobi=2025, schuze=schuze, datum_unl=datum_unl, when=when)


# --- Web: podstránky dne se dvěma schůzemi -------------------------------------


@patch("svejk.build.nav.list_site_editions")
def test_subpages_on_two_sitting_day_use_schuze_prefix(mock_list) -> None:
    mock_list.return_value = (_ed("11.06.2026", 22), _ed("11.06.2026", 23))
    for schuze in (22, 23):
        assert recnici_pages_href(2025, schuze, "11.06.2026") == f"/vydani/2026-06-11/s{schuze}/recnici/"
        assert smlouvy_pages_href(2025, schuze, "11.06.2026") == f"/vydani/2026-06-11/s{schuze}/smlouvy/"
        assert (
            vyznamenani_pages_href(2025, schuze, "11.06.2026", "prosli")
            == f"/vydani/2026-06-11/s{schuze}/prosli/"
        )
        assert steno_sources_pages_href(2025, schuze, "11.06.2026") == f"/vydani/2026-06-11/s{schuze}/steno/"


@patch("svejk.build.nav.list_site_editions")
def test_subpages_on_single_sitting_day_stay_flat(mock_list) -> None:
    mock_list.return_value = (_ed("12.06.2026", 23),)
    assert recnici_pages_href(2025, 23, "12.06.2026") == "/vydani/2026-06-12/recnici/"
    assert smlouvy_pages_href(2025, 23, "12.06.2026") == "/vydani/2026-06-12/smlouvy/"


# --- Web: kotvy PSP u běžící schůze ---------------------------------------------


class _FakeFetcher:
    """Seznam stránek na disku končí s001; projev pokračuje na nové stránce s002."""

    pages = {
        "https://www.psp.cz/eknih/2025ps/stenprot/034schuz/s034001.htm": "Začátek projevu.",
        "https://www.psp.cz/eknih/2025ps/stenprot/034schuz/s034002.htm": "A tady je ta citace.",
    }

    def __init__(self) -> None:
        self.extended = 0

    @staticmethod
    def _norm_search(text: str) -> str:
        return " ".join(text.lower().split())

    @staticmethod
    def _citace_in_text(haystack: str, needle: str) -> bool:
        return needle in haystack

    def extend_steno_page_urls(self, obdobi, schuze, known):
        self.extended += 1
        return list(self.pages)

    full = 0

    def list_steno_page_urls(self, obdobi, schuze):
        self.full += 1
        return list(self.pages)

    def resolve_url_for_citace(self, obdobi, schuze, speaker, citace, *, fallback_url, page_urls, page_text_cache):
        needle = self._norm_search(citace)
        start = fallback_url.split("#", 1)[0]
        if start not in page_urls:
            return fallback_url
        for url in page_urls[page_urls.index(start) :]:
            page_text_cache[url] = self._norm_search(self.pages[url])
            if needle in page_text_cache[url]:
                return f"{url}#r2"
        return fallback_url


def _psp_paths(tmp_path: Path) -> SchuzePaths:
    paths = SchuzePaths.create(2025, 34)
    aligned = tmp_path / "aligned"
    aligned.mkdir()
    (aligned / "psp_steno_index.json").write_text(
        json.dumps(
            {
                "obdobi": 2025,
                "schuze": 34,
                "page_urls": ["https://www.psp.cz/eknih/2025ps/stenprot/034schuz/s034001.htm"],
                "poradi_urls": {"1": "x"},
            }
        ),
        encoding="utf-8",
    )
    return paths, aligned


def test_resolver_refreshes_stale_page_index(tmp_path, monkeypatch) -> None:
    from svejk.build import steno_sources as ss

    paths, aligned = _psp_paths(tmp_path)
    monkeypatch.setattr(type(paths), "aligned", property(lambda self: aligned))
    monkeypatch.setattr(ss, "_PAGE_URLS_THIS_RUN", {})
    monkeypatch.setattr(ss, "_UNRESOLVED_THIS_RUN", {})
    fake = _FakeFetcher()
    resolver = ss.PspUrlResolver(paths)
    resolver._fetcher = fake

    url = resolver.resolve(
        "",
        "https://www.psp.cz/eknih/2025ps/stenprot/034schuz/s034001.htm#r1",
        "A tady je ta citace.",
    )

    assert url == "https://www.psp.cz/eknih/2025ps/stenprot/034schuz/s034002.htm#r2"
    assert fake.extended == 1
    index = json.loads((aligned / "psp_steno_index.json").read_text(encoding="utf-8"))
    assert len(index["page_urls"]) == 2
    assert index["poradi_urls"] == {"1": "x"}
    cache = json.loads((aligned / "psp_url_cache.json").read_text(encoding="utf-8"))
    assert url in cache["resolved"].values()


def test_resolver_full_refresh_when_start_page_missing(tmp_path, monkeypatch) -> None:
    # Seznam z disku bývá děravý i uprostřed: projev začíná na stránce, která v něm není.
    from svejk.build import steno_sources as ss

    paths, aligned = _psp_paths(tmp_path)
    (aligned / "psp_steno_index.json").write_text(
        json.dumps({"obdobi": 2025, "schuze": 34, "page_urls": ["https://www.psp.cz/eknih/2025ps/stenprot/034schuz/s034009.htm"]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(type(paths), "aligned", property(lambda self: aligned))
    monkeypatch.setattr(ss, "_PAGE_URLS_THIS_RUN", {})
    monkeypatch.setattr(ss, "_UNRESOLVED_THIS_RUN", {})
    fake = _FakeFetcher()
    resolver = ss.PspUrlResolver(paths)
    resolver._fetcher = fake

    url = resolver.resolve(
        "",
        "https://www.psp.cz/eknih/2025ps/stenprot/034schuz/s034001.htm#r1",
        "A tady je ta citace.",
    )
    assert url == "https://www.psp.cz/eknih/2025ps/stenprot/034schuz/s034002.htm#r2"
    assert fake.full == 1 and fake.extended == 0


def test_resolver_does_not_cache_unverified_link(tmp_path, monkeypatch) -> None:
    from svejk.build import steno_sources as ss

    paths, aligned = _psp_paths(tmp_path)
    monkeypatch.setattr(type(paths), "aligned", property(lambda self: aligned))
    monkeypatch.setattr(ss, "_PAGE_URLS_THIS_RUN", {})
    monkeypatch.setattr(ss, "_UNRESOLVED_THIS_RUN", {})
    resolver = ss.PspUrlResolver(paths)
    resolver._fetcher = _FakeFetcher()

    fallback = "https://www.psp.cz/eknih/2025ps/stenprot/034schuz/s034001.htm#r1"
    assert resolver.resolve("", fallback, "Tohle v přepisu ještě není.") == fallback
    assert not (aligned / "psp_url_cache.json").is_file()


# --- Web: skryté vydání ---------------------------------------------------------


def test_hidden_edition_is_not_approved(tmp_path, monkeypatch) -> None:
    from svejk.build import publish

    (tmp_path / "publish-approved.json").write_text(
        json.dumps({"approved": ["2025/34/21.10.2026", "2025/34/22.10.2026"], "hidden": ["2025/34/22.10.2026"]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(publish, "processed_root", lambda: tmp_path)
    monkeypatch.setattr(
        publish,
        "_list_obdobi_editions",
        lambda obdobi: (_ed("21.10.2026", 34), _ed("22.10.2026", 34)),
    )
    publish.clear_publish_cache()
    try:
        assert [e.datum_unl for e in publish.list_approved_editions(2025)] == ["21.10.2026"]
        assert not publish.is_edition_approved(_ed("22.10.2026", 34))
    finally:
        publish.clear_publish_cache()


def test_publish_unhides_edition(tmp_path, monkeypatch) -> None:
    from svejk.build import publish
    from svejk.edition import state

    path = tmp_path / "publish-approved.json"
    path.write_text(json.dumps({"approved": [], "hidden": ["2025/34/22.10.2026"], "held": []}), encoding="utf-8")
    monkeypatch.setattr(state, "processed_root", lambda: tmp_path)
    monkeypatch.setattr(publish, "processed_root", lambda: tmp_path)
    state.sync_publish_approved("2025/34/22.10.2026", add=True)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["approved"] == ["2025/34/22.10.2026"]
    assert data["hidden"] == []
    publish.clear_publish_cache()


# --- Web: vnořené odkazy při druhém vykreslení -----------------------------------


def test_render_den_html_does_not_mutate_cached_content() -> None:
    from svejk.build.day_content import build_den_content, clear_den_content_cache
    from svejk.build.html import render_den_html
    from svejk.paths import processed_root

    # 5. 6. 2026 má v lead/mean odkazy na tabulky vyznamenání (inject_mean_links).
    day_path = processed_root() / "2025-s20" / "facts" / "by_day" / "2026-06-05.json"
    if not day_path.is_file():
        pytest.skip("chybí data vydání 5. 6. 2026")
    schuze = int(day_path.parents[2].name.split("-s", 1)[1])
    paths = SchuzePaths.create(2025, schuze)
    clear_den_content_cache()
    content = build_den_content(day_path, paths, link_mode="pages")
    before = [(i.lead, i.mean, i.kuriozita_nav) for i in content.items]
    render_den_html(content, paths, day_path, link_mode="pages")
    again = build_den_content(day_path, paths, link_mode="pages")
    assert again is content
    assert [(i.lead, i.mean, i.kuriozita_nav) for i in again.items] == before
    clear_den_content_cache()


# --- Data: skip_steno nesmaže steno ----------------------------------------------


def test_run_fetch_skip_steno_keeps_existing(tmp_path, monkeypatch) -> None:
    from svejk.build import fetch

    steno = tmp_path / "steno.jsonl"
    steno.write_text('{"id": "a"}\n{"id": "b"}\n', encoding="utf-8")

    class _P:
        votes_jsonl = tmp_path / "votes.jsonl"
        steno_jsonl = steno
        obdobi, schuze = 2025, 34

        def ensure_dirs(self):
            pass

    class _A:
        def __init__(self, *a):
            pass

        def load_votes(self, obdobi, schuze):
            return []

    monkeypatch.setattr(fetch, "SchuzeAnalyzer", _A)
    info = fetch.run_fetch(_P(), skip_steno=True, verbose=False)
    assert steno.read_text(encoding="utf-8").count("\n") == 2
    assert info["steno"] == 2


# --- Newsletter -----------------------------------------------------------------


def _nwl_env(monkeypatch, tmp_path, editions, state):
    from svejk.newsletter import notify

    (tmp_path / "newsletter-state.json").write_text(json.dumps(state), encoding="utf-8")
    monkeypatch.setattr(notify, "processed_root", lambda: tmp_path)
    monkeypatch.setattr(notify, "list_approved_editions", lambda obdobi: editions)
    monkeypatch.setattr(notify, "is_edition_approved", lambda e: True)
    monkeypatch.setattr(notify, "_edition_ready", lambda e: True)
    monkeypatch.setattr(notify, "_build_email_body", lambda e, **kw: (f"S {e.datum_unl}", "p", "<p>h</p>"))
    monkeypatch.setenv("ECOMAIL_API_KEY", "k")
    monkeypatch.setenv("ECOMAIL_LIST_ID", "3")
    monkeypatch.setenv("ECOMAIL_FROM_EMAIL", "a@b.cz")
    return notify


def test_newsletter_drafts_every_new_edition(tmp_path, monkeypatch) -> None:
    editions = (_ed("16.10.2026", 34), _ed("20.10.2026", 34), _ed("21.10.2026", 34))
    notify = _nwl_env(monkeypatch, tmp_path, editions, {"last_drafted_id": "2025/34/16.10.2026"})
    created = []
    monkeypatch.setattr(notify, "create_campaign", lambda **kw: created.append(kw["subject"]) or {"id": 1})

    out = notify.run_newsletter_notify(2025)

    assert created == ["S 20.10.2026", "S 21.10.2026"]
    assert out["drafted_ids"] == ["2025/34/20.10.2026", "2025/34/21.10.2026"]
    st = notify.load_state()
    assert st["last_drafted_id"] == "2025/34/21.10.2026"
    assert notify.run_newsletter_notify(2025)["skipped"]


def test_newsletter_failure_does_not_block_retry(tmp_path, monkeypatch) -> None:
    editions = (_ed("16.10.2026", 34), _ed("20.10.2026", 34))
    notify = _nwl_env(monkeypatch, tmp_path, editions, {"last_drafted_id": "2025/34/16.10.2026"})

    def boom(**kw):
        raise OSError("Ecomail 503")

    monkeypatch.setattr(notify, "create_campaign", boom)
    with pytest.raises(OSError):
        notify.run_newsletter_notify(2025)
    st = notify.load_state()
    assert st["last_error_id"] == "2025/34/20.10.2026"
    assert st["last_drafted_id"] == "2025/34/16.10.2026"

    monkeypatch.setattr(notify, "create_campaign", lambda **kw: {"id": 2})
    out = notify.run_newsletter_notify(2025)
    assert out.get("drafted") is True
    st = notify.load_state()
    assert "last_error_id" not in st
    assert st["last_drafted_id"] == "2025/34/20.10.2026"


def test_newsletter_manual_old_edition_keeps_marker(tmp_path, monkeypatch) -> None:
    editions = (_ed("16.10.2026", 34), _ed("21.10.2026", 34))
    notify = _nwl_env(monkeypatch, tmp_path, editions, {"last_drafted_id": "2025/34/21.10.2026"})
    monkeypatch.setattr(notify, "create_campaign", lambda **kw: {"id": 3})
    monkeypatch.setattr(notify, "_find_edition", lambda obdobi, schuze: editions[0])
    notify.run_newsletter_notify(2025, schuze=34, force=True)
    assert notify.load_state()["last_drafted_id"] == "2025/34/21.10.2026"
