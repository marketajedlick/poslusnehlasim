"""Brána publikace — na web jdou jen schválená vydání nebo produkční snapshoty."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from svejk.paths import processed_root

if TYPE_CHECKING:
    from svejk.build.nav import Edition


def _list_obdobi_editions(obdobi: int) -> tuple[Edition, ...]:
    from svejk.build.nav import list_obdobi_editions

    return list_obdobi_editions(obdobi)

_APPROVED_NAME = "publish-approved.json"
_SNAPSHOTS_DIR = "publish-snapshots"
_DEFAULT_SITE = "https://poslusnehlasim.cz"


def publish_gate_enabled() -> bool:
    return os.environ.get("SVEJK_PUBLISH_GATE", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )


def edition_key(obdobi: int, schuze: int, datum_unl: str) -> str:
    return f"{obdobi}/{schuze}/{datum_unl}"


def parse_edition_key(key: str) -> tuple[int, int, str]:
    obdobi_s, schuze_s, datum_unl = key.split("/", 2)
    return int(obdobi_s), int(schuze_s), datum_unl


def approved_path() -> Path:
    return processed_root() / _APPROVED_NAME


def snapshots_root() -> Path:
    return processed_root() / _SNAPSHOTS_DIR


def snapshot_path(edition: Edition) -> Path:
    return (
        snapshots_root()
        / str(edition.obdobi)
        / str(edition.schuze)
        / f"{edition.datum_unl}.html"
    )


@lru_cache(maxsize=1)
def load_approved_keys() -> frozenset[str]:
    path = approved_path()
    if not path.is_file():
        return frozenset()
    data = json.loads(path.read_text(encoding="utf-8"))
    keys = data.get("approved") or []
    return frozenset(str(k) for k in keys)


@lru_cache(maxsize=1)
def load_held_keys() -> frozenset[str]:
    path = approved_path()
    if not path.is_file():
        return frozenset()
    data = json.loads(path.read_text(encoding="utf-8"))
    keys = data.get("held") or []
    return frozenset(str(k) for k in keys)


def is_edition_approved(edition: Edition) -> bool:
    return edition_key(edition.obdobi, edition.schuze, edition.datum_unl) in load_approved_keys()


def edition_source(edition: Edition) -> Literal["facts", "snapshot"] | None:
    """Z čeho se vydání exportuje na web, nebo None pokud se neexportuje."""
    if not publish_gate_enabled():
        return "facts"
    key = edition_key(edition.obdobi, edition.schuze, edition.datum_unl)
    if key in load_approved_keys():
        return "facts"
    if snapshot_path(edition).is_file():
        return "snapshot"
    return None


def list_site_editions(obdobi: int) -> tuple[Edition, ...]:
    """Vydání, která se objeví na veřejném webu."""
    all_editions = _list_obdobi_editions(obdobi)
    if not publish_gate_enabled():
        return all_editions
    out: list[Edition] = []
    for edition in all_editions:
        if edition_source(edition) is not None:
            out.append(edition)
    return tuple(out)


def list_approved_editions(obdobi: int) -> tuple[Edition, ...]:
    """Vydání schválená k sestavení z lokálních facts (newsletter, nová vydání)."""
    if not publish_gate_enabled():
        return _list_obdobi_editions(obdobi)
    return tuple(e for e in _list_obdobi_editions(obdobi) if is_edition_approved(e))


def blocked_editions(obdobi: int) -> tuple[Edition, ...]:
    """Mají facts, ale nejsou schválená ani nemají snapshot — nesmí na web."""
    if not publish_gate_enabled():
        return ()
    from svejk.paths import SchuzePaths
    from datetime import datetime

    blocked: list[Edition] = []
    held = load_held_keys()
    for edition in _list_obdobi_editions(obdobi):
        key = edition_key(edition.obdobi, edition.schuze, edition.datum_unl)
        if key in held:
            continue
        if edition_source(edition) is not None:
            continue
        paths = SchuzePaths.create(edition.obdobi, edition.schuze)
        d = datetime.strptime(edition.datum_unl, "%d.%m.%Y")
        day_path = paths.facts_by_day / f"{d.strftime('%Y-%m-%d')}.json"
        if day_path.is_file():
            blocked.append(edition)
    return tuple(blocked)


def clear_publish_cache() -> None:
    load_approved_keys.cache_clear()
    load_held_keys.cache_clear()


def held_missing_snapshots() -> tuple[str, ...]:
    missing: list[str] = []
    for key in sorted(load_held_keys()):
        obdobi, schuze, datum_unl = parse_edition_key(key)
        snap = snapshots_root() / str(obdobi) / str(schuze) / f"{datum_unl}.html"
        if not snap.is_file():
            missing.append(key)
    return tuple(missing)


def fetch_production_snapshot(
    key: str,
    *,
    site_url: str = _DEFAULT_SITE,
    overwrite: bool = False,
) -> Path:
    """Stáhne HTML vydání z produkce do publish-snapshots/."""
    obdobi, schuze, datum_unl = parse_edition_key(key)
    dest = snapshots_root() / str(obdobi) / str(schuze) / f"{datum_unl}.html"
    if dest.is_file() and not overwrite:
        return dest
    url = f"{site_url.rstrip('/')}/noviny/{obdobi}/{schuze}/{datum_unl}.html"
    req = urllib.request.Request(url, headers={"User-Agent": "poslusnehlasim-publish-snapshot/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        raise FileNotFoundError(f"Produkce nevrátila {url}: HTTP {e.code}") from e
    except urllib.error.URLError as e:
        raise OSError(f"Nepodařilo se stáhnout {url}: {e}") from e
    if "<html" not in html.lower():
        raise ValueError(f"Stažený obsah z {url} nevypadá jako HTML stránka vydání.")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(html, encoding="utf-8")
    return dest


def run_publish_check(obdobi: int) -> dict:
    blocked = blocked_editions(obdobi)
    missing_held = held_missing_snapshots()
    items = [
        {
            "key": edition_key(e.obdobi, e.schuze, e.datum_unl),
            "hint": "Přidej do publish-approved.json nebo publish-snapshot-fetch z produkce.",
        }
        for e in blocked
    ]
    held_items = [
        {
            "key": key,
            "hint": "Spusť: ./run-svejk.sh publish-snapshot-fetch KEY --overwrite",
        }
        for key in missing_held
    ]
    ok = (not items and not held_items) or not publish_gate_enabled()
    return {
        "obdobi": obdobi,
        "gate_enabled": publish_gate_enabled(),
        "approved_count": len(load_approved_keys()),
        "held_count": len(load_held_keys()),
        "site_editions": len(list_site_editions(obdobi)),
        "blocked": items,
        "held_missing_snapshots": held_items,
        "ok": ok,
    }
