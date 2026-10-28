"""Publish: snapshot, approved gate, assety."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from svejk.build.compose import run_compose
from svejk.build.io import read_json, write_json
from svejk.build.nav import clear_edition_cache
from svejk.edition.dates import resolve_edition_day
from svejk.edition.freeze import edition_content_hash, edition_drift, record_revision
from svejk.edition.social import run_social_assets
from svejk.edition.state import (
    assert_editable,
    edition_dir,
    is_key_in_approved,
    load_edition,
    published_snapshot_dir,
    save_edition,
    sync_publish_approved,
)
from svejk.newsletter.notify import run_newsletter_notify
from svejk.paths import SchuzePaths, processed_root
from svejk.validate.names import audit_edition_day, format_party_errors


def _copy_tree(src: Path, dest: Path) -> None:
    if not src.is_file():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


def _freeze_snapshot(
    paths: SchuzePaths,
    key: str,
    iso: str,
    datum_unl: str,
    slugs: list[str],
) -> Path:
    snap = published_snapshot_dir(key)
    if snap.exists():
        shutil.rmtree(snap)
    snap.mkdir(parents=True)
    day_src = paths.facts_by_day / f"{iso}.json"
    if day_src.is_file():
        _copy_tree(day_src, snap / "facts" / "by_day" / f"{iso}.json")
    for slug in slugs:
        tsrc = paths.facts_by_topic / f"{slug}.json"
        if tsrc.is_file():
            _copy_tree(tsrc, snap / "facts" / "by_topic" / f"{slug}.json")
    for ext in (".md", ".html"):
        out = paths.noviny_dlouhe_dir() / f"{iso}{ext}"
        _copy_tree(out, snap / "out" / f"{iso}{ext}")
        steno = paths.noviny_dlouhe_dir() / f"{iso}-steno{ext}"
        _copy_tree(steno, snap / "out" / f"{iso}-steno{ext}")
    edir = edition_dir(paths, iso)
    if edir.is_dir():
        shutil.copytree(edir, snap / "edition", dirs_exist_ok=True)
    meta = {
        "key": key,
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "slugs": slugs,
    }
    write_json(snap / "meta.json", meta)
    return snap


def run_edition_publish(
    paths: SchuzePaths,
    den: str,
    *,
    force: bool = False,
    skip_newsletter: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    datum_unl, iso, day_path = resolve_edition_day(paths, den)
    doc = load_edition(paths, iso)
    key = doc.get("key") or f"{paths.obdobi}/{paths.schuze}/{datum_unl}"

    if not day_path.is_file():
        raise FileNotFoundError(f"Chybí {day_path}")

    if doc.get("state") == "published":
        raise RuntimeError(
            f"Vydání {key} už je published. Změnu publikovaného vydání dělej přes "
            "edition republish --reason \"…\" (zapíše revizi, newsletter se znovu nepošle)."
        )

    if doc.get("state") != "approved" and not force:
        raise RuntimeError(
            f"Vydání {key} není approved (stav: {doc.get('state')}). "
            "Nejdřív: edition approve"
        )

    current_hash = edition_content_hash(paths, iso)
    approved_hash = doc.get("approved_hash")
    if approved_hash and approved_hash != current_hash and not force:
        raise RuntimeError(
            f"Facts vydání {key} se od schválení změnily. Spusť znovu edition review "
            "a edition approve (nebo --force)."
        )

    if dry_run:
        return {"key": key, "dry_run": True, "state": doc.get("state"), "would_publish": True}

    day = read_json(day_path)
    slugs = day.get("topic_slugs") or doc.get("topic_slugs") or []

    party_issues = audit_edition_day(paths, iso)
    party_errors = [i for i in party_issues if i.level == "error"]
    if party_errors:
        raise RuntimeError(format_party_errors(party_errors))

    clear_edition_cache()
    run_compose(paths, den=datum_unl)

    assets_dir = edition_dir(paths, iso) / "assets"
    assets = run_social_assets(paths, datum_unl, iso, assets_dir, day_doc=day)

    snap = _freeze_snapshot(paths, key, iso, datum_unl, slugs)

    doc["state"] = "published"
    doc["published_at"] = datetime.now(timezone.utc).isoformat()
    doc["published_hash"] = current_hash
    doc["snapshot_dir"] = str(snap.relative_to(processed_root()))
    doc["assets"] = assets
    save_edition(paths, iso, doc)
    sync_publish_approved(key, add=True)

    nwl: dict[str, Any] = {"skipped": True}
    if not skip_newsletter:
        try:
            nwl = run_newsletter_notify(
                paths.obdobi,
                schuze=paths.schuze,
                den=datum_unl,
                force=True,
            )
        except Exception as e:  # ponytail: NWL nesmí zabít publish
            nwl = {"error": str(e)}

    return {
        "key": key,
        "state": "published",
        "snapshot_dir": str(snap),
        "assets": assets,
        "newsletter": nwl,
        "approved": is_key_in_approved(key),
    }


def run_edition_republish(
    paths: SchuzePaths,
    den: str,
    *,
    reason: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Vědomá oprava publikovaného vydání: revize + nový snapshot, bez newsletteru.

    published_at zůstává (og:published_time / JSON-LD se nemění), přibude
    revisions[] a dateModified.
    """
    reason = (reason or "").strip()
    if not reason:
        raise RuntimeError("edition republish potřebuje --reason (co a proč se opravilo).")
    datum_unl, iso, day_path = resolve_edition_day(paths, den)
    doc = load_edition(paths, iso)
    key = doc.get("key") or f"{paths.obdobi}/{paths.schuze}/{datum_unl}"
    if doc.get("state") != "published":
        raise RuntimeError(f"Vydání {key} není published (stav: {doc.get('state')}). Použij edition publish.")
    if not day_path.is_file():
        raise FileNotFoundError(f"Chybí {day_path}")

    snap_dir = published_snapshot_dir(key)
    drift = edition_drift(paths, iso, snap_dir) if snap_dir.is_dir() else ["snapshot chybí"]
    current_hash = edition_content_hash(paths, iso)
    if dry_run:
        return {"key": key, "dry_run": True, "drift": drift, "content_hash": current_hash}

    day = read_json(day_path)
    slugs = day.get("topic_slugs") or []
    party_errors = [i for i in audit_edition_day(paths, iso) if i.level == "error"]
    if party_errors:
        raise RuntimeError(format_party_errors(party_errors))

    clear_edition_cache()
    run_compose(paths, den=datum_unl)
    doc["topic_slugs"] = slugs
    doc["republished_at"] = datetime.now(timezone.utc).isoformat()
    record_revision(doc, reason=reason, content_hash=current_hash)
    save_edition(paths, iso, doc)
    snap = _freeze_snapshot(paths, key, iso, datum_unl, slugs)
    return {"key": key, "state": "published", "drift": drift, "snapshot_dir": str(snap)}


def run_edition_approve(paths: SchuzePaths, den: str, *, force: bool = False) -> dict[str, Any]:
    """Schválení jen s čistým edition review; otisk obsahu hlídá publish."""
    from svejk.edition.metrics import run_edition_metrics

    datum_unl, iso, _ = resolve_edition_day(paths, den)
    doc = load_edition(paths, iso)
    assert_editable(doc, action="schvalovat")
    metrics = run_edition_metrics(paths, den)
    if not metrics.get("ok") and not force:
        raise RuntimeError(
            "edition review hlásí chyby, vydání nejde schválit (--force jen vědomě):\n  "
            + "\n  ".join(metrics.get("errors") or [])
        )
    doc = load_edition(paths, iso)  # metrics ukládá do edition.json
    doc["state"] = "approved"
    doc["approved_hash"] = edition_content_hash(paths, iso)
    save_edition(paths, iso, doc)
    return {"key": doc.get("key"), "state": "approved", "approved_hash": doc["approved_hash"]}


def run_edition_backfill(obdobi: int) -> dict[str, Any]:
    from svejk.build.publish import edition_key, load_approved_keys
    from svejk.build.nav import list_obdobi_editions

    count = 0
    for edition in list_obdobi_editions(obdobi):
        key = edition_key(edition.obdobi, edition.schuze, edition.datum_unl)
        if key not in load_approved_keys():
            continue
        p = SchuzePaths.create(edition.obdobi, edition.schuze)
        iso = datetime.strptime(edition.datum_unl, "%d.%m.%Y").strftime("%Y-%m-%d")
        day_path = p.facts_by_day / f"{iso}.json"
        if not day_path.is_file():
            continue
        day = read_json(day_path)
        doc = load_edition(p, iso)
        if doc.get("state") == "published":
            continue
        doc["state"] = "published"
        doc["published_at"] = doc.get("published_at") or "backfill"
        doc["topic_slugs"] = day.get("topic_slugs") or []
        doc["key"] = key
        snap = published_snapshot_dir(key)
        if not snap.is_dir():
            _freeze_snapshot(
                p,
                key,
                iso,
                edition.datum_unl,
                doc["topic_slugs"],
            )
            doc["snapshot_dir"] = str(snap.relative_to(processed_root()))
        save_edition(p, iso, doc)
        count += 1
    return {"backfilled": count, "obdobi": obdobi}
