"""CLI handlery pro edition workflow."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from svejk.build.compose import run_compose
from svejk.edition.brief import run_edition_brief
from svejk.edition.dates import resolve_edition_day
from svejk.edition.link_phrases import run_link_phrases_for_day
from svejk.edition.metrics import format_edition_review
from svejk.edition.publish import (
    run_edition_approve,
    run_edition_backfill,
    run_edition_publish,
)
from svejk.edition.state import EditionFrozenError, load_edition, save_edition
from svejk.paths import SchuzePaths


def _paths(args: argparse.Namespace) -> SchuzePaths:
    return SchuzePaths.create(args.obdobi, args.schuze)


def cmd_edition_brief(args: argparse.Namespace) -> int:
    paths = _paths(args)
    try:
        summary = run_edition_brief(
            paths,
            args.den,
            allow_incomplete_steno=args.allow_incomplete_steno,
            force=args.force,
            max_articles=args.max_articles,
        )
    except (EditionFrozenError, RuntimeError, FileNotFoundError) as e:
        print(f"Chyba: {e}", file=sys.stderr)
        return 1
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def cmd_edition_link_phrases(args: argparse.Namespace) -> int:
    paths = _paths(args)
    try:
        summary = run_link_phrases_for_day(
            paths,
            args.den,
            dry_run=args.dry_run,
            force=args.force,
        )
    except EditionFrozenError as e:
        print(f"Chyba: {e}", file=sys.stderr)
        return 1
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def cmd_edition_preview(args: argparse.Namespace) -> int:
    paths = _paths(args)
    datum_unl, iso, _ = resolve_edition_day(paths, args.den)
    run_compose(paths, den=datum_unl)
    md = paths.noviny_dlouhe_md(datum_unl)
    html = paths.noviny_dlouhe_html(datum_unl)
    print(f"Compose hotovo: {md}")
    if html.is_file():
        print(f"HTML: {html}")
    if args.serve:
        from svejk.build.export_pages import run_export_pages

        run_export_pages(args.obdobi, args.out, base_path=args.base_path, cname="")
        print(f"Export: {args.out}")
        print(f"Náhled: http://127.0.0.1:{args.port}/vydani/{iso}/")
    return 0


def cmd_edition_review(args: argparse.Namespace) -> int:
    paths = _paths(args)
    text = format_edition_review(paths, args.den, as_json=args.json)
    print(text)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
    return 0


def cmd_edition_feedback(args: argparse.Namespace) -> int:
    paths = _paths(args)
    _, iso, _ = resolve_edition_day(paths, args.den)
    doc = load_edition(paths, iso)
    entry = {
        "at": datetime.now(timezone.utc).isoformat(),
        "field": (args.field or "").strip(),
        "note": (args.note or "").strip(),
    }
    if not entry["note"]:
        print("Chyba: --note je povinné", file=sys.stderr)
        return 1
    doc.setdefault("feedback", []).append(entry)
    save_edition(paths, iso, doc)
    print(json.dumps(entry, ensure_ascii=False, indent=2))
    return 0


def cmd_edition_approve(args: argparse.Namespace) -> int:
    paths = _paths(args)
    try:
        summary = run_edition_approve(paths, args.den)
    except EditionFrozenError as e:
        print(f"Chyba: {e}", file=sys.stderr)
        return 1
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def cmd_edition_publish(args: argparse.Namespace) -> int:
    paths = _paths(args)
    try:
        summary = run_edition_publish(
            paths,
            args.den,
            force=args.force,
            skip_newsletter=args.skip_newsletter,
            dry_run=args.dry_run,
        )
    except (EditionFrozenError, RuntimeError, FileNotFoundError) as e:
        print(f"Chyba: {e}", file=sys.stderr)
        return 1
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def cmd_edition_backfill(args: argparse.Namespace) -> int:
    summary = run_edition_backfill(args.obdobi)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def register_edition_parser(sub: argparse._SubParsersAction) -> None:
    p_ed = sub.add_parser("edition", help="Workflow jednoho vydání (den)")
    ed_sub = p_ed.add_subparsers(dest="edition_cmd", required=True)

    def _common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--schuze", type=int, required=True)
        p.add_argument("--obdobi", type=int, default=2025)
        p.add_argument("--den", required=True, help="DD.MM.RRRR nebo YYYY-MM-DD")
        p.add_argument("--force", action="store_true")

    p_brief = ed_sub.add_parser("brief", help="Brief + kostra facts pro Cursor agenta")
    _common(p_brief)
    p_brief.add_argument("--allow-incomplete-steno", action="store_true")
    p_brief.add_argument("--max-articles", type=int, default=3)
    p_brief.set_defaults(func=cmd_edition_brief)

    p_lp = ed_sub.add_parser("link-phrases", help="Doplnit link_phrase ve facts")
    _common(p_lp)
    p_lp.add_argument("--dry-run", action="store_true")
    p_lp.set_defaults(func=cmd_edition_link_phrases)

    p_prev = ed_sub.add_parser("preview", help="Compose + volitelně export náhledu")
    _common(p_prev)
    p_prev.add_argument("--serve", action="store_true", help="Export do site/ pro náhled")
    p_prev.add_argument("-o", "--out", type=Path, default=Path("site"))
    p_prev.add_argument("--base-path", default="")
    p_prev.add_argument("--port", type=int, default=8765)
    p_prev.set_defaults(func=cmd_edition_preview)

    p_rev = ed_sub.add_parser("review", help="Review + metriky kvality")
    _common(p_rev)
    p_rev.add_argument("--json", action="store_true")
    p_rev.add_argument("-o", "--out", type=Path)
    p_rev.set_defaults(func=cmd_edition_review)

    p_fb = ed_sub.add_parser("feedback", help="Zapsat feedback pro další brief")
    _common(p_fb)
    p_fb.add_argument("--note", required=True)
    p_fb.add_argument("--field", default="", help="lead, pointa, mean, …")
    p_fb.set_defaults(func=cmd_edition_feedback)

    p_app = ed_sub.add_parser("approve", help="Schválit vydání před publish")
    _common(p_app)
    p_app.set_defaults(func=cmd_edition_approve)

    p_pub = ed_sub.add_parser("publish", help="Zmrazit snapshot + assety + approved")
    _common(p_pub)
    p_pub.add_argument("--dry-run", action="store_true")
    p_pub.add_argument("--skip-newsletter", action="store_true")
    p_pub.set_defaults(func=cmd_edition_publish)

    p_bf = ed_sub.add_parser("backfill-published", help="Backfill edition state pro approved")
    p_bf.add_argument("--obdobi", type=int, default=2025)
    p_bf.set_defaults(func=cmd_edition_backfill)
