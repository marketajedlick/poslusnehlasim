"""Stažení UNL hlasování a stenozáznamů z Hlídače do raw/*.jsonl."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from psp.schuze import SchuzeAnalyzer, Vote

from svejk.build.io import append_jsonl, iter_jsonl, write_jsonl
from svejk.config import HLIDAC_TOKEN, PSP_DATA_DIR, PSP_ORGAN_ID
from svejk.paths import SchuzePaths
from psp.hlidac import HlidacClient, StenoRecord


def _vote_row(v: Vote) -> dict[str, Any]:
    return {
        "cislo": v.cislo,
        "bod": v.bod,
        "datum": v.datum,
        "cas": v.cas,
        "nazev": v.nazev,
        "vysledek": v.vysledek,
        "pro": v.pro,
        "proti": v.proti,
        "zdrzel": v.zdrzel,
        "nehlasoval": v.nehlasoval,
        "pritomno": v.pritomno,
        "je_porad_schuze": v.je_porad_schuze,
    }


def _steno_row(r: StenoRecord) -> dict[str, Any]:
    return {
        "id": r.id,
        "poradi": r.poradi,
        "obdobi": r.obdobi,
        "schuze": r.schuze,
        "datum": r.datum,
        "cele_jmeno": r.cele_jmeno,
        "tema": r.tema,
        "text": r.text,
        "pocet_slov": r.pocet_slov,
        "url": r.url,
        "cislo_hlasovani": r.cislo_hlasovani,
    }


def _last_poradi_in_jsonl(path) -> int:
    last = 0
    if not path.is_file():
        return 0
    for row in iter_jsonl(path):
        p = row.get("poradi")
        if p is not None:
            last = max(last, int(p))
    return last


def _fetch_steno_to_jsonl(
    client: HlidacClient,
    path,
    obdobi: int,
    schuze: int,
    *,
    max_records: int | None = None,
    resume: bool = True,
    verbose: bool = True,
) -> int:
    """Stáhne steno a průběžně zapisuje do jsonl (při pádu zůstanou stažené řádky)."""
    import sys
    import time

    path.parent.mkdir(parents=True, exist_ok=True)
    start_poradi = 1
    existing = 0
    if resume and path.is_file() and path.stat().st_size > 0:
        start_poradi = _last_poradi_in_jsonl(path) + 1
        existing = start_poradi - 1
    else:
        path.write_text("", encoding="utf-8")

    t0 = time.monotonic()
    count = 0
    if verbose:
        if existing:
            print(
                f"Stahuji steno schuze {schuze}/{obdobi}, pokracuji od por. {start_poradi} "
                f"({existing} jiz v {path.name})...",
                file=sys.stderr,
                flush=True,
            )
        else:
            print(
                f"Stahuji stenozaznamy schuze {schuze}/{obdobi} (ukladam prubezne do {path.name})...",
                file=sys.stderr,
                flush=True,
            )

    for record in client.iter_steno(
        obdobi, schuze, start=start_poradi, max_records=max_records
    ):
        append_jsonl(path, _steno_row(record))
        count += 1
        if verbose and (count == 1 or count % 10 == 0):
            tema = (record.tema or "(bez tematu)")[:55]
            print(
                f"  [{existing + count}] por. {record.poradi} ({time.monotonic() - t0:.0f}s), {tema}",
                file=sys.stderr,
                flush=True,
            )

    if verbose:
        print(
            f"Steno hotovo: {existing + count} zaznamu celkem (+{count} novych, {time.monotonic() - t0:.0f}s).",
            file=sys.stderr,
            flush=True,
        )
    return existing + count


def run_fetch(
    paths: SchuzePaths,
    *,
    max_steno: int | None = None,
    skip_steno: bool = False,
    verbose: bool = True,
) -> dict[str, Any]:
    paths.ensure_dirs()
    analyzer = SchuzeAnalyzer(PSP_DATA_DIR, PSP_ORGAN_ID)
    votes = analyzer.load_votes(paths.obdobi, paths.schuze)
    vote_rows = [_vote_row(v) for v in votes]
    write_jsonl(paths.votes_jsonl, vote_rows)

    steno_count = 0
    hlidac_used = False
    if skip_steno:
        write_jsonl(paths.steno_jsonl, [])
    elif not HLIDAC_TOKEN:
        if verbose:
            print("HLIDAC_TOKEN chybí, steno.jsonl bude prázdný.", flush=True)
        write_jsonl(paths.steno_jsonl, [])
    else:
        rate = float(os.environ.get("HLIDAC_RATE_LIMIT_S", "1.0"))
        client = HlidacClient(HLIDAC_TOKEN, rate_limit_s=rate)
        limit = max_steno if max_steno and max_steno > 0 else None
        steno_count = _fetch_steno_to_jsonl(
            client,
            paths.steno_jsonl,
            paths.obdobi,
            paths.schuze,
            max_records=limit,
            verbose=verbose,
        )
        hlidac_used = True

    return {
        "votes": len(vote_rows),
        "steno": steno_count,
        "hlidac_token_used": hlidac_used,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
