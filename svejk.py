#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CLI pro Poslušně hlásím: sync, build, export-pages, review."""

import sys

if sys.version_info < (3, 10):
    raise SystemExit(
        "Potřebuješ Python 3.10+, máš {}.\n"
        "Spusť:  ./run-svejk.sh export-pages --obdobi 2025 --out site".format(
            sys.version.split()[0]
        )
    )

import argparse
import json
from pathlib import Path


def _timeline_z_cache(args: argparse.Namespace, fmt: str) -> str | None:
    """Načte hotový výstup z processed/, pokud existuje."""
    from svejk.paths import SchuzePaths
    from svejk.timeline import resolve_schuze_den

    paths = SchuzePaths.create(args.obdobi, args.schuze)
    out_dir = paths.noviny_dlouhe_dir()
    ext = "html" if fmt == "noviny-html" else "md"
    if fmt not in ("noviny-dlouhe", "noviny-html"):
        return None

    if args.den:
        d_unl, _ = resolve_schuze_den(paths, args.den)
        if fmt == "noviny-html":
            out = paths.noviny_dlouhe_html(d_unl)
        else:
            out = paths.noviny_dlouhe_md(d_unl)
        if out.is_file():
            return out.read_text(encoding="utf-8")
        return None
    if not out_dir.is_dir():
        return None
    files = sorted(out_dir.glob(f"*.{ext}"))
    if not files:
        return None
    parts = [f.read_text(encoding="utf-8") for f in files]
    return "\n\n---\n\n".join(parts)


def cmd_build(args: argparse.Namespace) -> int:
    from svejk.build import refresh_compose_manifest, run_build, run_build_obdobi
    from svejk.paths import SchuzePaths, processed_root

    if args.refresh_manifest:
        if args.den:
            print("Chyba: --refresh-manifest nelze s --den.", file=sys.stderr)
            return 1
        if args.schuze is not None:
            cisla = [args.schuze]
        elif args.vsechny_schuze:
            cisla = list(range(args.od, args.do + 1))
        else:
            cisla = sorted(
                int(p.name.split("-s", 1)[1])
                for p in processed_root().glob(f"{args.obdobi}-s*")
                if p.is_dir() and p.name.split("-s", 1)[1].isdigit()
            )
        if not cisla:
            print("Chyba: žádná schůze k obnově manifestu.", file=sys.stderr)
            return 1
        for cislo in cisla:
            paths = SchuzePaths.create(args.obdobi, cislo)
            if not paths.noviny_dlouhe_dir().is_dir():
                if not args.quiet:
                    print(f"s{cislo}: přeskočeno (chybí out/)", flush=True)
                continue
            compose = refresh_compose_manifest(paths)
            if not args.quiet:
                print(f"s{cislo}: manifest compose → {compose['days']} dní", flush=True)
        return 0

    only = None
    if args.only:
        only = tuple(s.strip() for s in args.only.split(",") if s.strip())
    if args.den and args.vsechny_schuze:
        print("Chyba: --den nelze s --vsechny-schuze.", file=sys.stderr)
        return 1
    try:
        if args.vsechny_schuze:
            summary = run_build_obdobi(
                args.obdobi,
                schuze_od=args.od,
                schuze_do=args.do,
                only=only,
                max_steno=args.max_steno or None,
                skip_steno=args.skip_steno,
                preskocit_hotove=args.preskocit_hotove,
                verbose=not args.quiet,
            )
            if summary.get("failed"):
                return 1
            return 0
        if args.schuze is None:
            print("Chyba: uveď --schuze N nebo --vsechny-schuze.", file=sys.stderr)
            return 1
        paths = run_build(
            args.obdobi,
            args.schuze,
            only=only,
            den=args.den,
            max_steno=args.max_steno or None,
            skip_steno=args.skip_steno,
            verbose=not args.quiet,
        )
    except (ValueError, OSError, FileNotFoundError) as e:
        print(f"Chyba: {e}", file=sys.stderr)
        return 1
    print(f"Artefakty: {paths.root}", file=sys.stderr)
    return 0


def cmd_compose_changed(args: argparse.Namespace) -> int:
    from svejk.build import run_compose_changed

    schuze_list = None
    if args.schuze:
        schuze_list = [int(x.strip()) for x in args.schuze.split(",") if x.strip()]
    try:
        summary = run_compose_changed(args.obdobi, schuze_list=schuze_list, verbose=not args.quiet)
    except (ValueError, OSError, FileNotFoundError) as e:
        print(f"Chyba: {e}", file=sys.stderr)
        return 1
    if summary.get("failed"):
        return 1
    if not schuze_list and not (summary.get("ok") or summary.get("vysledky")):
        return 1
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    from svejk.build.sync import run_sync

    schuze_list = None
    if args.schuze:
        schuze_list = [int(x.strip()) for x in args.schuze.split(",") if x.strip()]
    try:
        summary = run_sync(
            args.obdobi,
            schuze_od=args.od,
            schuze_do=args.do,
            schuze_list=schuze_list,
            skip_steno=args.skip_steno,
            force_unl=args.force_unl,
            check_only=args.check_only,
            verbose=not args.quiet,
        )
    except OSError as e:
        print(f"Chyba: {e}", file=sys.stderr)
        return 1
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    updated = summary.get("updated_schuze") or []
    if updated and not summary.get("check_only") and not args.quiet:
        print(
            f"Staženo raw/ pro schůze {updated}. Facts ručně, pak např.: "
            f"./run-svejk.sh build --schuze N --only align,extract,compose",
            file=sys.stderr,
        )
    if summary.get("errors"):
        return 1
    if getattr(args, "fail_if_pending", False):
        if summary.get("check_only"):
            pending = int(summary.get("would_update") or 0)
        else:
            pending = int(summary.get("updated") or 0)
        unl_changed = bool(summary.get("unl", {}).get("changed"))
        if pending > 0 or unl_changed:
            schuze = [
                r["schuze"]
                for r in summary.get("vysledky", [])
                if r.get("action") in ("would_update", "update")
            ]
            print(
                f"Nová data PSP: pending={pending}, unl_changed={unl_changed}, "
                f"schůze={schuze}",
                file=sys.stderr,
            )
            return 1
    return 0


def cmd_timeline(args: argparse.Namespace) -> int:
    from datetime import datetime

    from svejk.config import PSP_DATA_DIR, PSP_ORGAN_ID
    from svejk.listy import render_den_listy, render_schuze_listy
    from svejk.noviny import render_den_noviny, render_schuze_noviny
    from svejk.timeline import SvejkTimelineGenerator, normalize_day, render_cela_schuze, render_den

    fmt = getattr(args, "format", "noviny")
    cached = _timeline_z_cache(args, fmt)
    if cached is not None and not getattr(args, "live", False):
        print(cached)
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(cached, encoding="utf-8")
            print(f"Ulozeno: {args.out}", file=sys.stderr)
        return 0

    gen = SvejkTimelineGenerator(PSP_DATA_DIR, PSP_ORGAN_ID)
    sch = gen.for_schuze(args.obdobi, args.schuze)
    if args.den:
        target = normalize_day(args.den)
        sch.dny = [d for d in sch.dny if d.datum == target]
    if not sch.dny:
        target = normalize_day(args.den) if args.den else "(žádný)"
        msg = f"Pro schůzi {args.schuze} není den {target} v datech."
        if args.den:
            try:
                d = datetime.strptime(normalize_day(args.den), "%d.%m.%Y").date()
                jine = [
                    n for n in gen.analyzer.find_schuze_by_date(args.obdobi, d)
                    if n != args.schuze
                ]
                if jine:
                    msg += f" Tento den je ve schůzi {', '.join(map(str, jine))}."
            except ValueError:
                pass
        print(msg, file=sys.stderr)
        return 1

    if fmt == "noviny":
        text = render_den_noviny(sch.dny[0]) if len(sch.dny) == 1 else render_schuze_noviny(sch)
    elif fmt == "noviny-dlouhe":
        text = (
            render_den_listy(sch.dny[0])
            if len(sch.dny) == 1
            else render_schuze_listy(sch)
        )
    elif len(sch.dny) == 1:
        text = render_den(sch.dny[0])
    else:
        text = render_cela_schuze(sch)
    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"Ulozeno: {args.out}", file=sys.stderr)
    return 0


def cmd_publish_check(args: argparse.Namespace) -> int:
    from svejk.build.publish import run_publish_check

    result = run_publish_check(args.obdobi)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result.get("ok"):
        blocked = result.get("blocked") or []
        held = result.get("held_missing_snapshots") or []
        print(
            f"Publish gate: {len(blocked)} neblokovaných vydání, "
            f"{len(held)} held bez snapshotu.",
            file=sys.stderr,
        )
        for item in blocked:
            print(f"  blocked: {item['key']}", file=sys.stderr)
        for item in held:
            print(f"  held bez snapshotu: {item['key']}", file=sys.stderr)
        return 1
    print("Publish gate: OK.", file=sys.stderr)
    return 0


def cmd_publish_snapshot_fetch(args: argparse.Namespace) -> int:
    from svejk.build.publish import fetch_production_snapshot

    try:
        dest = fetch_production_snapshot(
            args.edition,
            site_url=args.site_url,
            overwrite=args.overwrite,
        )
    except (ValueError, OSError, FileNotFoundError) as e:
        print(f"Chyba: {e}", file=sys.stderr)
        return 1
    print(json.dumps({"edition": args.edition, "path": str(dest)}, ensure_ascii=False, indent=2))
    return 0


def cmd_export_pages(args: argparse.Namespace) -> int:
    from svejk.build.export_pages import run_export_pages

    try:
        result = run_export_pages(
            args.obdobi,
            args.out,
            base_path=args.base_path or None,
            cname=args.cname if args.cname != "" else None,
        )
    except (ValueError, OSError, FileNotFoundError) as e:
        print(f"Chyba: {e}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"Export: {result['out_dir']} ({result['pages']} vydání)", file=sys.stderr)
    return 0


def cmd_newsletter_notify(args: argparse.Namespace) -> int:
    from svejk.newsletter.notify import run_newsletter_notify

    try:
        result = run_newsletter_notify(
            args.obdobi,
            schuze=args.schuze or None,
            den=args.den or None,
            dry_run=args.dry_run,
            force=args.force,
            base_path=(args.base_path or "").rstrip("/"),
            out_dir=args.out or None,
        )
    except (ValueError, OSError, FileNotFoundError, RuntimeError) as e:
        print(f"Chyba: {e}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("drafted"):
        print("Koncept kampaně vytvořen v Ecomailu, odeslání ručně v UI.", file=sys.stderr)
    elif result.get("skipped"):
        print(f"Přeskočeno: {result.get('reason', '?')}", file=sys.stderr)
    return 0


def cmd_newsletter_doi_template(args: argparse.Namespace) -> int:
    from svejk.newsletter.doi import export_doi_template

    try:
        result = export_doi_template(
            args.out,
            base_path=(args.base_path or "").rstrip("/"),
        )
    except OSError as e:
        print(f"Chyba: {e}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"Šablona DOI: {result['html']}", file=sys.stderr)
    print(f"Předmět: {result['subject']}", file=sys.stderr)
    return 0


def cmd_newsletter_doi_sync(args: argparse.Namespace) -> int:
    from svejk.newsletter.doi import sync_doi_to_ecomail

    try:
        result = sync_doi_to_ecomail(
            base_path=(args.base_path or "").rstrip("/"),
            apply=args.apply,
            enable_double_optin=args.enable_double_optin,
            sync_template=not args.no_template,
        )
    except RuntimeError as e:
        print(f"Chyba: {e}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("skipped"):
        print(f"Přeskočeno: {result.get('reason', '?')}", file=sys.stderr)
        return 1 if result.get("reason", "").startswith("chybí") else 0
    if result.get("synced"):
        print("DOI šablona nahrána do Ecomailu.", file=sys.stderr)
    elif result.get("dry_run"):
        print("Náhled, pro zápis přidej --apply", file=sys.stderr)
    return 0


def cmd_newsletter_subscribers(_args: argparse.Namespace) -> int:
    from svejk.newsletter.api import (
        api_key_from_env,
        list_subscribers,
        subscribe_list_id_from_env,
    )

    api_key = api_key_from_env()
    list_id = subscribe_list_id_from_env()
    if not api_key:
        print("Chyba: ECOMAIL_API_KEY není nastaven", file=sys.stderr)
        return 1
    if not list_id:
        print("Chyba: ECOMAIL_SUBSCRIBE_LIST_ID není nastaven", file=sys.stderr)
        return 1
    try:
        data = list_subscribers(api_key, list_id)
    except RuntimeError as e:
        print(f"Chyba: {e}", file=sys.stderr)
        return 1
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


def _serve_export_site(args: argparse.Namespace) -> dict | None:
    from svejk.build.export_pages import run_export_pages

    try:
        return run_export_pages(
            args.obdobi,
            args.out,
            base_path=args.base_path or None,
            cname=args.cname if args.cname != "" else None,
        )
    except (ValueError, OSError, FileNotFoundError) as e:
        print(f"Chyba: {e}", file=sys.stderr)
        return None


def cmd_serve(args: argparse.Namespace) -> int:
    import functools
    import http.server

    site_dir = args.out.resolve()
    if not args.skip_export:
        result = _serve_export_site(args)
        if result is None:
            return 1
        print(
            f"Export: {result['out_dir']} ({result['pages']} vydání)",
            file=sys.stderr,
        )
    elif not site_dir.is_dir():
        print(
            f"Chyba: {site_dir} neexistuje — spusť export-pages nebo serve s exportem",
            file=sys.stderr,
        )
        return 1

    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler,
        directory=str(site_dir),
    )
    with http.server.ThreadingHTTPServer((args.host, args.port), handler) as httpd:
        print(f"Server: http://{args.host}:{args.port}/", file=sys.stderr)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nUkončeno.", file=sys.stderr)
    return 0


def cmd_jazykolam(args: argparse.Namespace) -> int:
    from datetime import datetime

    from svejk.build.jazykolam import kandidati_pro_schuze
    from svejk.paths import SchuzePaths, processed_root

    def _iso(den: str) -> str:
        den = den.strip()
        if "-" in den:
            return den
        return datetime.strptime(den, "%d.%m.%Y").strftime("%Y-%m-%d")

    paths = SchuzePaths.create(args.obdobi, args.schuze)
    lines: list[str] = []

    if args.den:
        iso = _iso(args.den)
        cands = kandidati_pro_schuze(paths, iso, limit=args.limit)
        lines.append(f"=== {iso} (s{args.schuze}) ===")
        if not cands:
            lines.append("  (žádný kandidát)")
        for i, c in enumerate(cands, 1):
            lines.append(f"\n{i}. [{c.skore}] {c.recnik}")
            lines.append(f"   {c.text}")
            lines.append(f"   steno: {c.steno_id}  |  téma: {c.tema}")
    else:
        root = processed_root()
        for day_path in sorted(root.glob(f"{args.obdobi}-s{args.schuze}/facts/by_day/*.json")):
            day = json.loads(day_path.read_text(encoding="utf-8"))
            if not day.get("steno_zdroje"):
                continue
            iso = day_path.stem
            cands = kandidati_pro_schuze(paths, iso, limit=args.limit)
            lines.append(f"\n=== {iso} ({day.get('datum', '')}) ===")
            if not cands:
                lines.append("  (žádný kandidát)")
                continue
            c = cands[0]
            lines.append(f"  [{c.skore}] {c.recnik}: {c.text[:140]}{'…' if len(c.text) > 140 else ''}")

    text = "\n".join(lines).strip() + "\n"
    print(text, end="")
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"Ulozeno: {args.out}", file=sys.stderr)
    return 0


def cmd_review(args: argparse.Namespace) -> int:
    from svejk.paths import SchuzePaths
    from svejk.review import (
        audit_weak_facts,
        format_audit_report,
        format_day_review,
        format_topic_review,
        review_day,
        review_topic,
    )

    paths = SchuzePaths.create(args.obdobi, args.schuze)
    weak: list = []
    topics: list = []

    if args.slug:
        tr = review_topic(paths, args.slug)
        if not tr:
            print(f"Chyba: chybí facts pro slug {args.slug}", file=sys.stderr)
            return 1
        topics = [tr]
        text = format_topic_review(tr, paths, show_votes=args.votes)
    elif args.audit:
        weak = audit_weak_facts(paths)
        text = format_audit_report(weak, paths)
    elif args.den:
        topics = review_day(paths, args.den)
        text = format_day_review(paths, args.den, show_votes=args.votes)
    else:
        print("Chyba: uveď --den, --slug nebo --audit.", file=sys.stderr)
        return 1

    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"Ulozeno: {args.out}", file=sys.stderr)
    if args.audit:
        return 1 if weak else 0
    has_warn = any(i.level == "warn" for t in topics for i in t.issues)
    return 1 if has_warn else 0


def cmd_glossary_audit(args: argparse.Namespace) -> int:
    from svejk.glossary_audit import audit_obdobi, format_report

    gaps = audit_obdobi(args.obdobi, args.od, args.do, export_only=args.export_only)
    report = format_report(gaps, limit=args.limit)
    print(report)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report, encoding="utf-8")
        print(f"Uloženo: {args.out}", file=sys.stderr)
    return 1 if gaps else 0


def cmd_poslanci_export(args: argparse.Namespace) -> int:
    from svejk.config import ROOT
    from psp.kluby_table import (
        build_poslanci_table,
        export_csv,
        export_markdown,
        format_csv,
        format_markdown,
    )

    rows = build_poslanci_table(data_dir=ROOT / "data")
    if args.stdout:
        text = format_markdown(rows) if args.format == "md" else format_csv(rows)
        print(text)
        return 0
    out = args.out or (ROOT / "data" / f"poslanci-kluby.{args.format}")
    if args.format == "md":
        export_markdown(out, data_dir=ROOT / "data")
    else:
        export_csv(out, data_dir=ROOT / "data")
    print(f"Exportováno {len(rows)} poslanců: {out}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Poslušně hlásím — build a export")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_timeline = sub.add_parser("timeline", help="Shrnuti schuze ve stylu Svejka (bez API)")
    p_timeline.add_argument("--schuze", type=int, required=True)
    p_timeline.add_argument("--obdobi", type=int, default=2025)
    p_timeline.add_argument("--den", help="Jen jeden den (YYYY-MM-DD nebo DD.MM.RRRR)")
    p_timeline.add_argument(
        "--format",
        choices=("noviny", "noviny-dlouhe", "noviny-html", "timeline"),
        default="noviny-dlouhe",
        help="noviny-dlouhe = plny text + nadpisy (default), noviny-html = design varianta C, noviny = bez nadpisu, timeline = casova osa",
    )
    p_timeline.add_argument("-o", "--out", type=Path, help="Ulozit do souboru")
    p_timeline.set_defaults(func=cmd_timeline)
    p_timeline.add_argument(
        "--live",
        action="store_true",
        help="Ignoruj processed/ a generuj z UNL (listy)",
    )

    p_build = sub.add_parser(
        "build",
        help="File-based pipeline: fetch → align → compose (extract jen s --only extract)",
    )
    p_build.add_argument("--schuze", type=int, help="Číslo schůze (nebo použij --vsechny-schuze)")
    p_build.add_argument("--obdobi", type=int, default=2025)
    p_build.add_argument(
        "--vsechny-schuze",
        action="store_true",
        help="Build pro všechny schůze v období z UNL (hl{obdobi}s.unl)",
    )
    p_build.add_argument("--od", type=int, default=1, help="S --vsechny-schuze: od čísla schůze")
    p_build.add_argument("--do", type=int, default=99, help="S --vsechny-schuze: do čísla schůze")
    p_build.add_argument(
        "--preskocit-hotove",
        action="store_true",
        help="Přeskoč schůze, které už mají hotový fetch v processed/",
    )
    p_build.add_argument("--den", help="Jen compose pro jeden den (DD.MM. nebo YYYY-MM-DD)")
    p_build.add_argument(
        "--refresh-manifest",
        action="store_true",
        help="Jen opravit steps.compose v manifestu podle out/ (bez compose)",
    )
    p_build.add_argument(
        "--only",
        help="Kroky oddělené čárkou: fetch,align,extract,compose (výchozí fetch+align+compose, extract jen explicitně)",
    )
    p_build.add_argument(
        "--max-steno",
        type=int,
        default=0,
        help="Limit stenozáznamů z Hlídače (0 = celá schůze)",
    )
    p_build.add_argument(
        "--skip-steno",
        action="store_true",
        help="Nestahovat steno (jen UNL)",
    )
    p_build.add_argument("-q", "--quiet", action="store_true")
    p_build.set_defaults(func=cmd_build)

    p_sync = sub.add_parser(
        "sync",
        help="Stažení UNL (PSP) + steno (Hlídač) do raw/ — bez align/extract/facts",
    )
    p_sync.add_argument("--obdobi", type=int, default=2025)
    p_sync.add_argument("--schuze", help="Jen vybrané schůze, čárkou: 18,20")
    p_sync.add_argument("--od", type=int, default=1, help="Od čísla schůze")
    p_sync.add_argument("--do", type=int, default=99, help="Do čísla schůze")
    p_sync.add_argument(
        "--check-only",
        action="store_true",
        help="Jen zjistit, co by se stáhlo (bez zápisu)",
    )
    p_sync.add_argument(
        "--force-unl",
        action="store_true",
        help="Vždy stáhnout hl{obdobi}s.unl z PSP",
    )
    p_sync.add_argument(
        "--skip-steno",
        action="store_true",
        help="Nestahovat steno z Hlídače",
    )
    p_sync.add_argument(
        "--fail-if-pending",
        action="store_true",
        help="Ukončit s chybou, pokud jsou nová data (pro CI notifikace)",
    )
    p_sync.add_argument("-q", "--quiet", action="store_true")
    p_sync.set_defaults(func=cmd_sync)

    p_cc = sub.add_parser(
        "compose-changed",
        help="Compose jen schůze ze syncu (last_updated_schuze), ne celé období",
    )
    p_cc.add_argument("--obdobi", type=int, default=2025)
    p_cc.add_argument(
        "--schuze",
        help="Přepsat seznam schůzí (čárkou), jinak last_updated_schuze ze sync-state",
    )
    p_cc.add_argument("-q", "--quiet", action="store_true")
    p_cc.set_defaults(func=cmd_compose_changed)

    p_pub_check = sub.add_parser(
        "publish-check",
        help="Kontrola, že nedoladěná vydání nemají cestu na web bez schválení",
    )
    p_pub_check.add_argument("--obdobi", type=int, default=2025)
    p_pub_check.set_defaults(func=cmd_publish_check)

    p_pub_snap = sub.add_parser(
        "publish-snapshot-fetch",
        help="Stáhne HTML vydání z produkce do processed/publish-snapshots/",
    )
    p_pub_snap.add_argument(
        "edition",
        help="Klíč vydání, např. 2025/22/11.06.2026",
    )
    p_pub_snap.add_argument(
        "--site-url",
        default="https://poslusnehlasim.cz",
        help="Základ URL produkčního webu",
    )
    p_pub_snap.add_argument(
        "--overwrite",
        action="store_true",
        help="Přepsat existující snapshot",
    )
    p_pub_snap.set_defaults(func=cmd_publish_snapshot_fetch)

    p_export = sub.add_parser(
        "export-pages",
        help="Statický web pro GitHub Pages (složka site/)",
    )
    p_export.add_argument("--obdobi", type=int, default=2025)
    p_export.add_argument("-o", "--out", type=Path, default=Path("site"))
    p_export.add_argument(
        "--base-path",
        default="",
        help="Prefix cest (např. /nazev-repa pro github.io/repo bez vlastní domény)",
    )
    p_export.add_argument(
        "--cname",
        default="poslusnehlasim.cz",
        help="Doména do souboru CNAME (prázdné = nevytvářet)",
    )
    p_export.set_defaults(func=cmd_export_pages)

    p_nwl = sub.add_parser(
        "newsletter-notify",
        help="Po novém vydání připravit koncept kampaně v Ecomailu (odeslání ručně)",
    )
    p_nwl.add_argument("--obdobi", type=int, default=2025)
    p_nwl.add_argument(
        "--schuze",
        type=int,
        default=0,
        help="Číslo konkrétní schůze; bez tohoto parametru se použije nejnovější schválené vydání",
    )
    p_nwl.add_argument(
        "--den",
        help="Konkrétní den vydání (DD.MM.RRRR nebo YYYY-MM-DD); vyžaduje --schuze",
    )
    p_nwl.add_argument(
        "--base-path",
        default="",
        help="Stejný prefix jako při export-pages (github.io/repo)",
    )
    p_nwl.add_argument(
        "--dry-run",
        action="store_true",
        help="Jen náhled subject/body, bez API",
    )
    p_nwl.add_argument(
        "--force",
        action="store_true",
        help="Znovu i když už je v newsletter-state.json",
    )
    p_nwl.add_argument(
        "--out",
        default="",
        help="Složka z export-pages, ověří, že stránka vydání v exportu existuje",
    )
    p_nwl.set_defaults(func=cmd_newsletter_notify)

    p_doi = sub.add_parser(
        "newsletter-doi-template",
        help="Export HTML šablony potvrzovacího e-mailu (double opt-in) pro Ecomail",
    )
    p_doi.add_argument(
        "-o",
        "--out",
        type=Path,
        default=Path("site/email"),
        help="Složka pro doi.html, doi.txt a README.txt",
    )
    p_doi.add_argument(
        "--base-path",
        default="",
        help="Stejný prefix jako při export-pages (github.io/repo)",
    )
    p_doi.set_defaults(func=cmd_newsletter_doi_template)

    p_doi_sync = sub.add_parser(
        "newsletter-doi-sync",
        help="Nahrát DOI šablonu do Ecomailu (seznam + knihovna šablon)",
    )
    p_doi_sync.add_argument(
        "--base-path",
        default="",
        help="Stejný prefix jako při export-pages (github.io/repo)",
    )
    p_doi_sync.add_argument(
        "--apply",
        action="store_true",
        help="Skutečně zapsat do Ecomailu (výchozí je jen náhled)",
    )
    p_doi_sync.add_argument(
        "--enable-double-optin",
        action="store_true",
        help="Zapnout double opt-in na seznamu (double_optin: true)",
    )
    p_doi_sync.add_argument(
        "--no-template",
        action="store_true",
        help="Neaktualizovat knihovnu šablon, jen nastavení seznamu",
    )
    p_doi_sync.set_defaults(func=cmd_newsletter_doi_sync)

    sub.add_parser(
        "newsletter-subscribers",
        help="Odběratelé ze sběrového seznamu (ECOMAIL_SUBSCRIBE_LIST_ID)",
    ).set_defaults(func=cmd_newsletter_subscribers)

    p_serve = sub.add_parser(
        "serve",
        help="Export do site/ a lokální preview (http.server)",
    )
    p_serve.add_argument("--obdobi", type=int, default=2025)
    p_serve.add_argument("-o", "--out", type=Path, default=Path("site"))
    p_serve.add_argument(
        "--base-path",
        default="",
        help="Prefix cest (např. /nazev-repa pro github.io/repo bez vlastní domény)",
    )
    p_serve.add_argument(
        "--cname",
        default="poslusnehlasim.cz",
        help="Doména do souboru CNAME (prázdné = nevytvářet)",
    )
    p_serve.add_argument(
        "--skip-export",
        action="store_true",
        help="Nepřegenerovat site/ — jen spustit server nad existujícím exportem",
    )
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8000)
    p_serve.set_defaults(func=cmd_serve)

    p_jazykolam = sub.add_parser(
        "jazykolam",
        help="Kandidáti na jazykolam dne ze stenoprotokolu",
    )
    p_jazykolam.add_argument("--schuze", type=int, required=True)
    p_jazykolam.add_argument("--obdobi", type=int, default=2025)
    p_jazykolam.add_argument(
        "--den",
        help="Jen jeden den (DD.MM.RRRR nebo YYYY-MM-DD); bez něj celá schůze",
    )
    p_jazykolam.add_argument("--limit", type=int, default=5, help="Kolik kandidátů na den")
    p_jazykolam.add_argument("-o", "--out", type=Path, help="Uložit report")
    p_jazykolam.set_defaults(func=cmd_jazykolam)

    p_review = sub.add_parser(
        "review",
        help="Porovnání raw / aligned / facts / export (doladění textů)",
    )
    p_review.add_argument("--schuze", type=int, required=True)
    p_review.add_argument("--obdobi", type=int, default=2025)
    p_review.add_argument("--den", help="Den (DD.MM.RRRR nebo YYYY-MM-DD)")
    p_review.add_argument("--slug", help="Jedno téma podle slug")
    p_review.add_argument(
        "--audit",
        action="store_true",
        help="Seznam všech publikovaných témat se varováními",
    )
    p_review.add_argument(
        "--votes",
        type=int,
        default=5,
        help="Kolik řádků raw hlasování ukázat (default 5)",
    )
    p_review.add_argument("-o", "--out", type=Path, help="Uložit report")
    p_review.set_defaults(func=cmd_review)

    p_gloss = sub.add_parser(
        "glossary-audit",
        help="Pojmy ve facts/steno bez tooltipu v glosáři",
    )
    p_gloss.add_argument("--obdobi", type=int, default=2025)
    p_gloss.add_argument("--od", type=int, default=1)
    p_gloss.add_argument("--do", type=int, default=21)
    p_gloss.add_argument(
        "--export-only",
        action="store_true",
        help="Jen text, který jde na web (lead/mean/fakty), ne celé steno",
    )
    p_gloss.add_argument("--limit", type=int, default=40, help="Max. počet pojmů v reportu")
    p_gloss.add_argument("-o", "--out", type=Path, help="Uložit report")
    p_gloss.set_defaults(func=cmd_glossary_audit)

    p_posl = sub.add_parser("poslanci", help="Poslanci a kluby (PSP open data)")
    posl_sub = p_posl.add_subparsers(dest="poslanci_cmd", required=True)
    p_posl_export = posl_sub.add_parser("export", help="Tabulka jméno → klub")
    p_posl_export.add_argument(
        "--format",
        choices=("csv", "md"),
        default="csv",
        help="csv (default) nebo md",
    )
    p_posl_export.add_argument(
        "-o",
        "--out",
        type=Path,
        help="Výstupní soubor (default data/poslanci-kluby.{csv,md})",
    )
    p_posl_export.add_argument(
        "--stdout",
        action="store_true",
        help="Vypsat na stdout místo zápisu do souboru",
    )
    p_posl_export.set_defaults(func=cmd_poslanci_export)

    from svejk.edition.commands import register_edition_parser

    register_edition_parser(sub)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
