"""Stav vydání, fingerprint, guard proti editaci published."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from svejk.build.io import read_json, write_json
from svejk.build.publish import edition_key, load_approved_keys
from svejk.paths import SchuzePaths, processed_root

EditionState = Literal[
    "data_ready", "draft", "in_review", "approved", "published", "stale"
]

_EDITION_STATES: frozenset[str] = frozenset(
    {"data_ready", "draft", "in_review", "approved", "published", "stale"}
)
_MANUAL_TOPIC_KEYS = frozenset(
    {
        "lead",
        "lead_tail",
        "pointa",
        "mean",
        "kuriozita",
        "kuriozita_links",
        "nadpis",
        "publikovat",
        "koho",
        "fakty",
        "citace_text",
        "citace_autor",
    }
)
_MANUAL_DAY_KEYS = frozenset(
    {"dnesni_ucet", "zaver", "vysledek", "topic_slugs", "skore_manual"}
)


class EditionFrozenError(RuntimeError):
    pass


def edition_dir(paths: SchuzePaths, iso: str) -> Path:
    return paths.root / "editions" / iso


def edition_json_path(paths: SchuzePaths, iso: str) -> Path:
    return edition_dir(paths, iso) / "edition.json"


def published_root() -> Path:
    return processed_root() / "published"


def published_snapshot_dir(key: str) -> Path:
    obdobi, schuze, datum_unl = key.split("/", 2)
    return published_root() / obdobi / schuze / datum_unl


def compute_input_fingerprint(paths: SchuzePaths) -> dict[str, Any]:
    votes_count = votes_max = 0
    if paths.votes_jsonl.is_file():
        for line in paths.votes_jsonl.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            votes_count += 1
            v = json.loads(line)
            c = int(v.get("cislo") or 0)
            votes_max = max(votes_max, c)
    steno_count = steno_last = 0
    if paths.steno_jsonl.is_file():
        for line in paths.steno_jsonl.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            steno_count += 1
            r = json.loads(line)
            steno_last = max(steno_last, int(r.get("poradi") or 0))
    topics_mtime = ""
    if paths.topics_json.is_file():
        topics_mtime = datetime.fromtimestamp(
            paths.topics_json.stat().st_mtime, tz=timezone.utc
        ).isoformat()
    raw = f"v{votes_count}:{votes_max}:s{steno_count}:{steno_last}:t{topics_mtime}"
    digest = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return {
        "votes_count": votes_count,
        "votes_max_cislo": votes_max,
        "steno_count": steno_count,
        "steno_last_poradi": steno_last,
        "topics_built_at": topics_mtime,
        "fingerprint": digest,
    }


def steno_incomplete(paths: SchuzePaths) -> bool:
    from svejk.build.sync import _steno_download_incomplete

    state_path = processed_root() / "sync-state.json"
    state: dict[str, Any] = {}
    if state_path.is_file():
        state = read_json(state_path)
    return _steno_download_incomplete(paths, state, paths.schuze)


def default_edition(
    paths: SchuzePaths,
    *,
    datum_unl: str,
    iso: str,
) -> dict[str, Any]:
    return {
        "key": edition_key(paths.obdobi, paths.schuze, datum_unl),
        "obdobi": paths.obdobi,
        "schuze": paths.schuze,
        "datum_unl": datum_unl,
        "iso": iso,
        "state": "data_ready",
        "topic_slugs": [],
        "recommended_slugs": [],
        "rejected_slugs": [],
        "brief_path": f"editions/{iso}/brief.md",
        "feedback": [],
        "metrics": {},
        "inputs": compute_input_fingerprint(paths),
        "published_at": None,
        "snapshot_dir": None,
        "supersedes": None,
    }


def load_edition(paths: SchuzePaths, iso: str) -> dict[str, Any]:
    p = edition_json_path(paths, iso)
    if p.is_file():
        return read_json(p)
    d_unl = datetime.strptime(iso, "%Y-%m-%d").strftime("%d.%m.%Y")
    return default_edition(paths, datum_unl=d_unl, iso=iso)


def save_edition(paths: SchuzePaths, iso: str, doc: dict[str, Any]) -> Path:
    d = edition_dir(paths, iso)
    d.mkdir(parents=True, exist_ok=True)
    p = edition_json_path(paths, iso)
    write_json(p, doc)
    return p


def is_published(doc: dict[str, Any]) -> bool:
    return doc.get("state") == "published"


def assert_editable(
    doc: dict[str, Any],
    *,
    force: bool = False,
    action: str = "upravit",
) -> None:
    if force or not is_published(doc):
        return
    key = doc.get("key", "?")
    raise EditionFrozenError(
        f"Vydání {key} je published — nelze {action}. "
        f"Použij --force pro fatální opravu nebo edition republish."
    )


def fingerprint_stale(doc: dict[str, Any], paths: SchuzePaths) -> bool:
    saved = (doc.get("inputs") or {}).get("fingerprint")
    if not saved:
        return False
    return saved != compute_input_fingerprint(paths).get("fingerprint")


def effective_state(doc: dict[str, Any], paths: SchuzePaths) -> EditionState:
    state = doc.get("state") or "data_ready"
    if state == "published":
        return "published"
    if fingerprint_stale(doc, paths):
        return "stale"
    if state in _EDITION_STATES:
        return state  # type: ignore[return-value]
    return "data_ready"


def merge_topic_skeleton(
    existing: dict[str, Any],
    fresh: dict[str, Any],
) -> dict[str, Any]:
    """Zachová ruční lead/pointa/mean/fakty od agenta."""
    if not existing:
        return fresh
    edited = any(existing.get(k) for k in ("lead", "pointa", "mean", "citace_text"))
    if not edited and not (existing.get("fakty") and any(
        f.get("link_phrase") for f in existing.get("fakty") or [] if isinstance(f, dict)
    )):
        return fresh
    out = dict(fresh)
    for key in _MANUAL_TOPIC_KEYS:
        if key in existing and existing[key] not in (None, "", []):
            out[key] = existing[key]
    return out


def merge_day_skeleton(
    existing: dict[str, Any],
    fresh: dict[str, Any],
) -> dict[str, Any]:
    if not existing:
        return fresh
    if not any(existing.get(k) for k in ("dnesni_ucet", "zaver", "vysledek")):
        return fresh
    out = dict(fresh)
    for key in _MANUAL_DAY_KEYS:
        if key in existing and existing[key] not in (None, "", []):
            out[key] = existing[key]
    return out


def sync_publish_approved(key: str, *, add: bool = True) -> None:
    path = processed_root() / "publish-approved.json"
    data: dict[str, Any] = {"approved": [], "hidden": [], "held": []}
    if path.is_file():
        data = read_json(path)
    approved = list(data.get("approved") or [])
    if add and key not in approved:
        approved.append(key)
        approved.sort()
    elif not add and key in approved:
        approved.remove(key)
    data["approved"] = approved
    write_json(path, data)
    from svejk.build.publish import clear_publish_cache

    clear_publish_cache()


def is_key_in_approved(key: str) -> bool:
    return key in load_approved_keys()
