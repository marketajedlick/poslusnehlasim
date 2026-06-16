"""Synchronizace dat PSP: UNL hlasování + steno z Hlídače → processed/."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from psp.fetch_unl import refresh_unl, unl_needs_refresh
from psp.hlidac import HlidacClient
from psp.schuze import SchuzeAnalyzer

from svejk.build.fetch import run_fetch
from svejk.build.io import iter_jsonl, read_json, write_json
from svejk.config import HLIDAC_TOKEN, PSP_DATA_DIR, PSP_ORGAN_ID
from svejk.paths import SchuzePaths, processed_root


def sync_state_path(base=None):
    return processed_root(base) / "sync-state.json"


def load_sync_state(base=None) -> dict[str, Any]:
    path = sync_state_path(base)
    if path.is_file():
        return read_json(path)
    return {"obdobi": None, "unl": {}, "schuze": {}}


def save_sync_state(state: dict[str, Any], base=None) -> None:
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    write_json(sync_state_path(base), state)


def _vote_stats(obdobi: int, cislo: int, analyzer: SchuzeAnalyzer) -> dict[str, Any]:
    try:
        votes = analyzer.load_votes(obdobi, cislo)
    except FileNotFoundError:
        return {"count": 0, "max_cislo": 0, "last_datum": ""}
    if not votes:
        return {"count": 0, "max_cislo": 0, "last_datum": ""}
    return {
        "count": len(votes),
        "max_cislo": max(v.cislo for v in votes),
        "last_datum": votes[-1].datum,
    }


def _stored_vote_stats(paths: SchuzePaths) -> dict[str, Any]:
    rows = list(iter_jsonl(paths.votes_jsonl))
    if not rows:
        return {"count": 0, "max_cislo": 0, "last_datum": ""}
    cisla = [int(r["cislo"]) for r in rows if r.get("cislo") is not None]
    return {
        "count": len(rows),
        "max_cislo": max(cisla) if cisla else 0,
        "last_datum": rows[-1].get("datum") or "",
    }


def _steno_stats(
    paths: SchuzePaths,
    state: dict[str, Any] | None = None,
    cislo: int | None = None,
) -> dict[str, Any]:
    count = 0
    last_poradi = 0
    last_datum = ""
    for row in iter_jsonl(paths.steno_jsonl):
        count += 1
        p = int(row.get("poradi") or 0)
        last_poradi = max(last_poradi, p)
        d = (row.get("datum") or "")[:10]
        if d:
            last_datum = d
    if last_poradi == 0 and state is not None and cislo is not None:
        saved = (state.get("schuze") or {}).get(str(cislo)) or {}
        saved_poradi = int(saved.get("last_steno_poradi") or 0)
        if saved_poradi > 0:
            return {
                "count": int(saved.get("steno_count") or 0),
                "last_poradi": saved_poradi,
                "last_datum": saved.get("last_steno_datum") or last_datum,
                "from_sync_state": True,
            }
    return {"count": count, "last_poradi": last_poradi, "last_datum": last_datum}


def _votes_need_update(unl_stats: dict[str, Any], stored: dict[str, Any]) -> bool:
    if stored["count"] == 0:
        return unl_stats["count"] > 0
    return (
        unl_stats["count"] != stored["count"]
        or unl_stats["max_cislo"] != stored["max_cislo"]
        or unl_stats["last_datum"] != stored["last_datum"]
    )


def _steno_probe_has_new(
    client: HlidacClient | None,
    obdobi: int,
    cislo: int,
    last_poradi: int,
) -> bool:
    if client is None:
        return False
    nxt = last_poradi + 1 if last_poradi > 0 else 1
    return client.fetch_steno(HlidacClient.steno_id(obdobi, cislo, nxt)) is not None


def _needs_pipeline(paths: SchuzePaths) -> bool:
    return not paths.topics_json.is_file() or not paths.facts_by_day.is_dir()


def _saved_steno_poradi(state: dict[str, Any], cislo: int) -> int:
    saved = (state.get("schuze") or {}).get(str(cislo)) or {}
    return int(saved.get("last_steno_poradi") or 0)


def _steno_file_last_poradi(paths: SchuzePaths) -> int:
    if not paths.steno_jsonl.is_file() or paths.steno_jsonl.stat().st_size == 0:
        return 0
    last = 0
    for row in iter_jsonl(paths.steno_jsonl):
        p = row.get("poradi")
        if p is not None:
            last = max(last, int(p))
    return last


def _steno_cache_missing(
    paths: SchuzePaths,
    state: dict[str, Any],
    cislo: int,
) -> bool:
    """sync-state říká, že steno je stažené, ale lokální soubor chybí nebo je prázdný."""
    if paths.steno_jsonl.is_file() and paths.steno_jsonl.stat().st_size > 0:
        return False
    return _saved_steno_poradi(state, cislo) > 0


def _steno_download_incomplete(
    paths: SchuzePaths,
    state: dict[str, Any],
    cislo: int,
) -> bool:
    """Stažený soubor má méně záznamů, než slibuje sync-state (přerušený download)."""
    saved_poradi = _saved_steno_poradi(state, cislo)
    if saved_poradi <= 0:
        return False
    return _steno_file_last_poradi(paths) < saved_poradi


def run_sync(
    obdobi: int,
    *,
    schuze_od: int = 1,
    schuze_do: int = 99,
    schuze_list: list[int] | None = None,
    skip_steno: bool = False,
    force_unl: bool = False,
    check_only: bool = False,
    verbose: bool = True,
) -> dict[str, Any]:
    """
    1. Aktualizuje hl{obdobi}s.unl z PSP (HEAD/GET ZIP).
    2. Pro každou schůzi: porovná hlasování, doplní steno z Hlídače do raw/.

    Align, extract a compose se nespouští — facts jsou redakční, jen ručně pod dohledem.
    """
    analyzer = SchuzeAnalyzer(PSP_DATA_DIR, PSP_ORGAN_ID)
    state = load_sync_state()
    state["obdobi"] = obdobi
    state.setdefault("unl", {})
    state.setdefault("schuze", {})

    if check_only:
        remote, unl_would_change = unl_needs_refresh(
            obdobi, PSP_DATA_DIR, state.get("unl"), force=force_unl
        )
        unl_result: dict[str, Any] = {
            "changed": unl_would_change,
            "remote": remote,
            "check_only": True,
        }
    else:
        unl_result = refresh_unl(
            obdobi,
            PSP_DATA_DIR,
            local_meta=state.get("unl"),
            force=force_unl,
            verbose=verbose,
        )
        if unl_result.get("changed"):
            state["unl"] = {
                k: unl_result[k]
                for k in ("etag", "last_modified", "content_length", "lines", "fetched_at")
                if k in unl_result
            }

    cisla = schuze_list if schuze_list is not None else analyzer.list_schuze_cisla(obdobi)
    cisla = [c for c in cisla if schuze_od <= c <= schuze_do]

    use_steno = not skip_steno and bool(HLIDAC_TOKEN)
    client: HlidacClient | None = None
    if use_steno:
        rate = float(os.environ.get("HLIDAC_RATE_LIMIT_S", "1.0"))
        client = HlidacClient(HLIDAC_TOKEN, rate_limit_s=rate)
    elif not skip_steno and verbose:
        print("HLIDAC_TOKEN chybí — steno se nestáhne.", flush=True)

    vysledky: list[dict[str, Any]] = []
    errors: list[str] = []

    for cislo in cisla:
        paths = SchuzePaths.create(obdobi, cislo)
        unl_stats = _vote_stats(obdobi, cislo, analyzer)
        if unl_stats["count"] == 0:
            continue

        stored_votes = _stored_vote_stats(paths)
        steno_stats = _steno_stats(paths, state, cislo)

        votes_changed = _votes_need_update(unl_stats, stored_votes) or unl_result.get("changed")
        steno_missing = _steno_cache_missing(paths, state, cislo)
        steno_incomplete = _steno_download_incomplete(paths, state, cislo)
        if steno_missing or steno_incomplete:
            steno_new = True
        else:
            steno_new = _steno_probe_has_new(client, obdobi, cislo, steno_stats["last_poradi"])
        pipeline_missing = _needs_pipeline(paths)

        needs_work = votes_changed or steno_new or steno_missing or steno_incomplete
        action = "would_update" if check_only and needs_work else ("update" if needs_work else "skip")

        entry: dict[str, Any] = {
            "schuze": cislo,
            "action": action,
            "votes_unl": unl_stats,
            "votes_stored": stored_votes,
            "steno_stored": steno_stats,
            "steno_new_available": steno_new,
            "steno_cache_missing": steno_missing,
            "steno_download_incomplete": steno_incomplete,
            "pipeline_missing": pipeline_missing,
        }
        vysledky.append(entry)

        if action != "update":
            continue

        paths.ensure_dirs()
        try:
            if verbose:
                print(f"→ sync schůze {cislo}/{obdobi}", flush=True)
            fetch_info = run_fetch(
                paths,
                skip_steno=not use_steno,
                verbose=verbose,
            )
            entry["fetch"] = fetch_info
            steno_after = _steno_stats(paths, state, cislo)
            votes_after = _stored_vote_stats(paths)
            state["schuze"][str(cislo)] = {
                **votes_after,
                "steno_count": steno_after["count"],
                "last_steno_poradi": steno_after["last_poradi"],
                "last_steno_datum": steno_after["last_datum"],
                "synced_at": datetime.now(timezone.utc).isoformat(),
            }
        except (OSError, ValueError, FileNotFoundError) as e:
            msg = f"schůze {cislo}: {e}"
            errors.append(msg)
            entry["error"] = str(e)
            if verbose:
                print(f"CHYBA {msg}", flush=True)

    updated_schuze = [int(r["schuze"]) for r in vysledky if r.get("action") == "update"]
    would_schuze = [int(r["schuze"]) for r in vysledky if r.get("action") == "would_update"]
    if not check_only:
        state["last_updated_schuze"] = updated_schuze
        save_sync_state(state)

    updated = len(updated_schuze)
    would = sum(1 for r in vysledky if r.get("action") == "would_update")
    summary = {
        "obdobi": obdobi,
        "unl": unl_result,
        "schuze_celkem": len(cisla),
        "updated": updated,
        "would_update": would,
        "skipped": sum(1 for r in vysledky if r.get("action") == "skip"),
        "updated_schuze": would_schuze if check_only else updated_schuze,
        "vysledky": vysledky,
        "errors": errors,
        "check_only": check_only,
    }
    if verbose:
        tag = "would update" if check_only else "aktualizováno"
        n = would if check_only else updated
        print(
            f"Sync hotovo: UNL {'změněn' if unl_result.get('changed') else 'beze změny'}, "
            f"schůze {tag} {n}/{len(cisla)}",
            flush=True,
        )
    return summary


__all__ = ["run_sync", "load_sync_state", "save_sync_state", "sync_state_path"]
