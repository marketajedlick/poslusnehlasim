"""Zmrazení publikovaných vydání.

Web se skládá z živých facts/, takže „published“ samo nic nechrání. Ochrana:
- snapshot v processed/published/{obdobi}/{schuze}/{datum}/facts/ je
  referenční stav publikovaného vydání,
- `publish-check` (CI před deployem) selže, když se živá facts publikovaného
  vydání liší od snapshotu (drift),
- vědomá změna jde jen přes `edition republish --reason`, který zapíše revizi
  a snapshot obnoví.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from svejk.build.io import read_json
from svejk.paths import SchuzePaths, processed_root


def _canonical_json(path: Path) -> str | None:
    if not path.is_file():
        return None
    return json.dumps(read_json(path), ensure_ascii=False, sort_keys=True)


def edition_fact_files(paths: SchuzePaths, iso: str) -> dict[str, Path]:
    """Relativní cesta ve snapshotu → živý soubor facts pro vydání."""
    day_path = paths.facts_by_day / f"{iso}.json"
    out: dict[str, Path] = {f"facts/by_day/{iso}.json": day_path}
    if day_path.is_file():
        for slug in read_json(day_path).get("topic_slugs") or []:
            out[f"facts/by_topic/{slug}.json"] = paths.facts_by_topic / f"{slug}.json"
    return out


def edition_content_hash(paths: SchuzePaths, iso: str) -> str:
    """Otisk obsahu vydání (by_day + témata dne), nezávislý na formátování JSON."""
    h = hashlib.sha256()
    for rel, path in sorted(edition_fact_files(paths, iso).items()):
        h.update(rel.encode())
        h.update((_canonical_json(path) or "<missing>").encode())
    return h.hexdigest()[:16]


def edition_drift(paths: SchuzePaths, iso: str, snapshot: Path) -> list[str]:
    """Soubory, kde se živá facts liší od snapshotu publikovaného vydání."""
    diffs: list[str] = []
    live = edition_fact_files(paths, iso)
    snap_files = {
        p.relative_to(snapshot).as_posix()
        for p in (snapshot / "facts").rglob("*.json")
    } if (snapshot / "facts").is_dir() else set()
    for rel in sorted(set(live) | snap_files):
        live_json = _canonical_json(live[rel]) if rel in live else None
        snap_json = _canonical_json(snapshot / rel)
        if live_json != snap_json:
            if live_json is None:
                diffs.append(f"{rel} (téma už ve vydání není)")
            elif snap_json is None:
                diffs.append(f"{rel} (nové ve vydání)")
            else:
                diffs.append(rel)
    return diffs


def _published_docs(obdobi: int) -> list[tuple[SchuzePaths, str, dict[str, Any]]]:
    out = []
    for edir in sorted(processed_root().glob(f"{obdobi}-s*/editions/*/edition.json")):
        doc = read_json(edir)
        if doc.get("state") != "published":
            continue
        try:
            cislo = int(edir.parents[2].name.split("-s", 1)[1])
        except (IndexError, ValueError):
            continue
        out.append((SchuzePaths.create(obdobi, cislo), edir.parent.name, doc))
    return out


def check_published_drift(obdobi: int) -> list[dict[str, Any]]:
    from svejk.edition.state import published_snapshot_dir

    items: list[dict[str, Any]] = []
    for paths, iso, doc in _published_docs(obdobi):
        key = doc.get("key") or ""
        if not key:
            continue
        snap = published_snapshot_dir(key)
        if not snap.is_dir():
            items.append({"key": key, "files": [], "hint": "chybí snapshot"})
            continue
        diffs = edition_drift(paths, iso, snap)
        if diffs:
            items.append(
                {
                    "key": key,
                    "files": diffs,
                    "hint": (
                        f"./run-svejk.sh edition republish --schuze {paths.schuze} "
                        f"--den {doc.get('datum_unl') or iso} --reason \"…\" "
                        "(nebo vrať facts podle snapshotu)"
                    ),
                }
            )
    return items


def check_shared_topic_slugs(obdobi: int) -> list[dict[str, Any]]:
    """Téma ve dvou vydáních téže schůze: úprava jednoho dne tiše mění druhý."""
    from svejk.build.publish import list_site_editions

    by_schuze: dict[int, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for edition in list_site_editions(obdobi):
        paths = SchuzePaths.create(edition.obdobi, edition.schuze)
        iso = datetime.strptime(edition.datum_unl, "%d.%m.%Y").strftime("%Y-%m-%d")
        day_path = paths.facts_by_day / f"{iso}.json"
        if not day_path.is_file():
            continue
        for slug in read_json(day_path).get("topic_slugs") or []:
            by_schuze[edition.schuze][slug].append(edition.datum_unl)
    items = []
    for schuze, slugs in sorted(by_schuze.items()):
        for slug, days in sorted(slugs.items()):
            if len(days) > 1:
                items.append(
                    {
                        "schuze": schuze,
                        "slug": slug,
                        "days": days,
                        "hint": "Každý den potřebuje vlastní soubor tématu (např. slug-DD-MM).",
                    }
                )
    return items


def check_approved_not_published(obdobi: int) -> list[str]:
    """Klíč v approved, ale vydání neprošlo edition publish (obchází gate)."""
    from svejk.build.publish import load_approved_keys

    states: dict[str, str] = {}
    for edir in processed_root().glob(f"{obdobi}-s*/editions/*/edition.json"):
        doc = read_json(edir)
        if doc.get("key"):
            states[doc["key"]] = doc.get("state") or ""
    return sorted(
        k
        for k in load_approved_keys()
        if k.startswith(f"{obdobi}/") and states.get(k) != "published"
    )


def record_revision(doc: dict[str, Any], *, reason: str, content_hash: str) -> None:
    doc.setdefault("revisions", []).append(
        {
            "at": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
            "content_hash": content_hash,
        }
    )
    doc["published_hash"] = content_hash
