"""File-based build: fetch → align → compose (extract jen ručně)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from svejk.build.align import run_align
from svejk.build.compose import run_compose
from svejk.build.extract import run_extract
from svejk.build.fetch import run_fetch
from svejk.build.io import read_json, write_json
from svejk.build.sync import run_sync
from svejk.build.nav import clear_edition_cache
from svejk.config import PSP_DATA_DIR, PSP_ORGAN_ID
from svejk.paths import SchuzePaths, processed_root
from psp.schuze import SchuzeAnalyzer

# extract vynechán — facts/ jsou redakční, jen ručně (--only fetch,align,extract)
STEPS = ("fetch", "align", "compose")


def compose_manifest_from_disk(paths: SchuzePaths) -> dict[str, Any]:
    """Sekce steps.compose podle skutečných souborů v out/noviny-dlouhe."""
    out_dir = paths.noviny_dlouhe_dir()
    md_files = sorted(str(p) for p in out_dir.glob("*.md")) if out_dir.is_dir() else []
    html_files = sorted(str(p) for p in out_dir.glob("*.html")) if out_dir.is_dir() else []
    return {
        "done": True,
        "days": len(md_files),
        "files": md_files,
        "html_files": html_files,
    }


def refresh_compose_manifest(paths: SchuzePaths) -> dict[str, Any]:
    """Opraví steps.compose v manifestu podle disku (bez znovu-compose)."""
    paths.ensure_dirs()
    manifest: dict[str, Any] = {}
    if paths.manifest.is_file():
        manifest = read_json(paths.manifest)
    manifest.setdefault("obdobi", paths.obdobi)
    manifest.setdefault("schuze", paths.schuze)
    manifest.setdefault("steps", {})
    manifest["steps"]["compose"] = compose_manifest_from_disk(paths)
    manifest["built_at"] = datetime.now(timezone.utc).isoformat()
    write_json(paths.manifest, manifest)
    return manifest["steps"]["compose"]


def run_build(
    obdobi: int,
    schuze: int,
    *,
    only: tuple[str, ...] | None = None,
    den: str | None = None,
    max_steno: int | None = None,
    skip_steno: bool = False,
    verbose: bool = True,
) -> SchuzePaths:
    paths = SchuzePaths.create(obdobi, schuze)
    paths.ensure_dirs()

    steps = only if only else STEPS
    manifest: dict[str, Any] = {}
    if paths.manifest.is_file():
        manifest = read_json(paths.manifest)

    manifest.setdefault("obdobi", obdobi)
    manifest.setdefault("schuze", schuze)
    manifest["steps"] = manifest.get("steps", {})

    if "fetch" in steps:
        if verbose:
            print("→ fetch", flush=True)
        manifest["steps"]["fetch"] = {
            "done": True,
            **run_fetch(paths, max_steno=max_steno, skip_steno=skip_steno, verbose=verbose),
        }

    if "align" in steps:
        if verbose:
            print("→ align", flush=True)
        manifest["steps"]["align"] = {"done": True, **run_align(paths)}

    if "extract" in steps:
        if verbose:
            print("→ extract", flush=True)
        manifest["steps"]["extract"] = {"done": True, **run_extract(paths)}

    if "compose" in steps:
        if verbose:
            print("→ compose", flush=True)
        clear_edition_cache()
        partial = run_compose(paths, den=den)
        compose = compose_manifest_from_disk(paths)
        if den:
            compose["last_partial_compose"] = {
                "den": den,
                "built_at": datetime.now(timezone.utc).isoformat(),
                **partial,
            }
        manifest["steps"]["compose"] = compose

    manifest["built_at"] = datetime.now(timezone.utc).isoformat()
    write_json(paths.manifest, manifest)

    if verbose:
        print(f"Hotovo: {paths.root}", flush=True)
    return paths


def _schuze_ma_hotovy_fetch(paths: SchuzePaths, min_steno_bytes: int = 100) -> bool:
    if not paths.manifest.is_file():
        return False
    m = read_json(paths.manifest)
    if not m.get("steps", {}).get("fetch", {}).get("done"):
        return False
    if paths.steno_jsonl.is_file() and paths.steno_jsonl.stat().st_size >= min_steno_bytes:
        return True
    if paths.steno_jsonl.is_file() and paths.steno_jsonl.stat().st_size == 0:
        return m.get("steps", {}).get("fetch", {}).get("hlidac_token_used") is False
    return paths.votes_jsonl.is_file()


def run_build_obdobi(
    obdobi: int,
    *,
    schuze_od: int = 1,
    schuze_do: int = 99,
    schuze_list: list[int] | None = None,
    only: tuple[str, ...] | None = None,
    max_steno: int | None = None,
    skip_steno: bool = False,
    preskocit_hotove: bool = False,
    verbose: bool = True,
) -> dict[str, Any]:
    """Build pro všechny schůze v období (např. 1-20 u ps2025)."""
    analyzer = SchuzeAnalyzer(PSP_DATA_DIR, PSP_ORGAN_ID)
    cisla = schuze_list if schuze_list is not None else analyzer.list_schuze_cisla(obdobi)
    cisla = [c for c in cisla if schuze_od <= c <= schuze_do]

    if not cisla:
        raise FileNotFoundError(
            f"V UNL pro období {obdobi} nejsou žádné schůze (soubor hl-{obdobi}ps/hl{obdobi}s.unl)."
        )

    vysledky: list[dict[str, Any]] = []
    for cislo in cisla:
        paths = SchuzePaths.create(obdobi, cislo)
        if preskocit_hotove and _schuze_ma_hotovy_fetch(paths):
            if verbose:
                print(f"=== Schůze {cislo}/{obdobi}, přeskočeno (už staženo) ===", flush=True)
            vysledky.append({"schuze": cislo, "skipped": True, "root": str(paths.root)})
            continue

        if verbose:
            print(f"\n=== Schůze {cislo}/{obdobi} ({cisla.index(cislo) + 1}/{len(cisla)}) ===", flush=True)
        try:
            run_build(
                obdobi,
                cislo,
                only=only,
                max_steno=max_steno,
                skip_steno=skip_steno,
                verbose=verbose,
            )
            vysledky.append({"schuze": cislo, "ok": True, "root": str(paths.root)})
        except (OSError, ValueError, FileNotFoundError) as e:
            vysledky.append({"schuze": cislo, "ok": False, "error": str(e)})
            if verbose:
                print(f"CHYBA schůze {cislo}: {e}", flush=True)

    summary = {
        "obdobi": obdobi,
        "schuze_celkem": len(cisla),
        "ok": sum(1 for r in vysledky if r.get("ok")),
        "skipped": sum(1 for r in vysledky if r.get("skipped")),
        "failed": sum(1 for r in vysledky if r.get("ok") is False and not r.get("skipped")),
        "vysledky": vysledky,
        "built_at": datetime.now(timezone.utc).isoformat(),
    }
    obdobi_manifest = processed_root() / f"{obdobi}-obdobi-build.json"
    write_json(obdobi_manifest, summary)

    if verbose:
        print(
            f"\nObdobí {obdobi}: {summary['ok']} OK, "
            f"{summary['skipped']} přeskočeno, {summary['failed']} chyb, "
            f"{obdobi_manifest}",
            flush=True,
        )
    return summary


def run_compose_changed(
    obdobi: int,
    *,
    schuze_list: list[int] | None = None,
    verbose: bool = True,
) -> dict[str, Any]:
    """Compose jen schůze ze syncu (last_updated_schuze), ne celé období."""
    from svejk.build.sync import load_sync_state

    cisla = schuze_list
    if cisla is None:
        state = load_sync_state()
        cisla = [int(c) for c in state.get("last_updated_schuze") or []]
    if not cisla:
        msg = "Žádná schůze k compose — spusť sync, nebo uveď --schuze."
        if verbose:
            print(msg, flush=True)
        return {"obdobi": obdobi, "composed": [], "message": msg}

    if verbose:
        print(f"Compose jen změněné schůze: {cisla}", flush=True)
    return run_build_obdobi(
        obdobi,
        schuze_list=cisla,
        only=("compose",),
        verbose=verbose,
    )


__all__ = [
    "run_build",
    "run_build_obdobi",
    "run_compose_changed",
    "run_sync",
    "STEPS",
    "SchuzePaths",
    "compose_manifest_from_disk",
    "refresh_compose_manifest",
]
