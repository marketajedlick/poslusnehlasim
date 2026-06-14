#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys

if sys.version_info[0] < 3:
    sys.stderr.write(
        "Tento skript vyzaduje Python 3 (tvuj 'python' je Python 2).\n\n"
        "Spust:\n"
        "  ./run-svejk.sh db init\n"
        "Nebo:\n"
        "  source .venv/bin/activate && python svejk.py db init\n"
    )
    sys.exit(1)

"""CLI pro Svejk do snemovny, ingest, generovani, web."""

if sys.version_info < (3, 10):
    raise SystemExit(
        "Potrebujes Python 3.10+, mas {}.\n"
        "Spust:  ./run-svejk.sh db init\n"
        "Nebo:   source .venv/bin/activate && python svejk.py db init".format(
            sys.version.split()[0]
        )
    )

import argparse
import json
from pathlib import Path

from svejk.config import HLIDAC_TOKEN


def _require_db():
    """SQLite/ORM vrstva, volitelná; build a export-pages ji nepotřebují."""
    try:
        from svejk.db import Bod, Schuze, StavZapisu, Zapisek, get_session, init_db
    except ModuleNotFoundError as e:
        if e.name == "svejk.db":
            raise SystemExit(
                "Příkaz vyžaduje modul svejk.db (lokální admin DB), který v tomto repu není.\n"
                "Pro GitHub Pages použij: build, export-pages, timeline."
            ) from e
        raise
    return Bod, Schuze, StavZapisu, Zapisek, get_session, init_db


def _require_ingest():
    try:
        from svejk.ingest import ingest_schuze
    except ModuleNotFoundError as e:
        if e.name in ("svejk.ingest", "svejk.db"):
            raise SystemExit(
                "Příkaz ingest není v tomto repu k dispozici (chybí svejk.ingest / svejk.db)."
            ) from e
        raise
    return ingest_schuze


def _require_generate():
    try:
        from svejk.generate import generate_for_bod, generate_pending
    except ModuleNotFoundError as e:
        if e.name in ("svejk.generate", "svejk.db"):
            raise SystemExit(
                "Příkaz generate není v tomto repu k dispozici (chybí svejk.generate / svejk.db)."
            ) from e
        raise
    return generate_for_bod, generate_pending


def cmd_db_init(_: argparse.Namespace) -> int:
    *_, init_db = _require_db()
    init_db()
    print("Databáze inicializována.")
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    ingest_schuze = _require_ingest()
    try:
        result = ingest_schuze(
            args.obdobi,
            args.schuze,
            tema=args.tema,
            max_steno=args.max_steno,
            verbose=not args.quiet,
        )
    except (ValueError, OSError) as e:
        print(f"Chyba: {e}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_generate(args: argparse.Namespace) -> int:
    generate_for_bod, generate_pending = _require_generate()
    try:
        if args.bod_id:
            result = generate_for_bod(
                args.bod_id, dry_run=args.dry_run, use_claude=args.claude,
            )
        else:
            result = generate_pending(dry_run=args.dry_run, use_claude=args.claude)
    except ValueError as e:
        print(f"Chyba: {e}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


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
            f"Po syncu compose jen změněné schůze: "
            f"./run-svejk.sh compose-changed --obdobi {args.obdobi}",
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
    from svejk.noviny import (
        render_den_noviny,
        render_den_noviny_dlouhe,
        render_schuze_noviny,
        render_schuze_noviny_dlouhe,
    )
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
            render_den_noviny_dlouhe(sch.dny[0])
            if len(sch.dny) == 1
            else render_schuze_noviny_dlouhe(sch)
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


def cmd_seed(args: argparse.Namespace) -> int:
    """Demo data bez API, pro lokální test webu."""
    Bod, Schuze, StavZapisu, Zapisek, get_session, init_db = _require_db()
    init_db()
    with get_session() as session:
        schuze = Schuze(cislo_schuze=args.schuze, obdobi=args.obdobi, datum_od="2026-05-26", datum_do="2026-05-28")
        session.add(schuze)
        session.flush()

        bod = Bod(
            schuze_id=schuze.id,
            nazev="Pojistné na sociální zabezpečení",
            zdroj_url="https://www.psp.cz",
            surovy_text=(
                "--- Ing. Jan Novák (26.05.2026, poř. 142) ---\n"
                "Navrhujeme snížení minimálního pojistného pro OSVČ z 5720 na 5005 korun měsíčně, "
                "platnost od ledna 2026 se zpětným účinkem.\n\n"
                "--- PhDr. Marie Svobodová (26.05.2026, poř. 145) ---\n"
                "Opozice navrhuje zamítnutí, argumentuje nestabilitou systému.\n\n"
                "--- Mgr. Petr Dvořák (26.05.2026, poř. 148) ---\n"
                "Vládní koalice podporuje návrh, poukazuje na úsporu cca 715 Kč měsíčně."
            ),
        )
        bod.set_meta({"pocet_projevu": 3, "pocet_slov": 120, "steno_ids": [], "cisla_hlasovani": []})
        session.add(bod)
        session.flush()

        if args.schvalit:
            z = Zapisek(
                bod_id=bod.id,
                svejk_text=(
                    "Když jsem sloužil u 11. pěšího pluku, taky se občas mluvilo "
                    "o penězích, jenže tam šlo o cigarety, ne o pojistné. Tady poslanci hlasovali "
                    "o tom, že živnostník ušetří sedm set korun měsíčně. Zaměstnanec u piva? "
                    "To se vás netýká, vy máte mzdu a oni mají faktury."
                ),
                fakticke_shrnuti=(
                    "Poslanecká sněmovna schválila snížení minimálního pojistného na sociální "
                    "zabezpečení pro OSVČ z 5 720 Kč na 5 005 Kč měsíčně. Platí od ledna 2026 "
                    "se zpětným účinkem. Hlasování dopadlo 118:0."
                ),
                stav=StavZapisu.SCHVALENO.value,
            )
            z.set_statistiky({
                "pocet_recniku": 3,
                "pocet_projevu": 3,
                "pocet_slov": 120,
                "hlasovani": {
                    "cislo": 99,
                    "vysledek": "PŘIJATO",
                    "pro": 118,
                    "proti": 0,
                    "zdrzel": 0,
                    "nehlasoval": 0,
                    "pritomno": 118,
                },
            })
            from datetime import datetime, timezone
            z.schvaleno_kdy = datetime.now(timezone.utc)
            session.add(z)

        session.commit()
        print(f"Seed hotový: schuze_id={schuze.id}, bod_id={bod.id}")
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


def _serve_reload_watch(args: argparse.Namespace) -> None:
    try:
        from watchfiles import watch
    except ImportError:
        print(
            "Varování: --reload vyžaduje watchfiles (uvicorn[standard]); "
            "automatický re-export je vypnutý.",
            file=sys.stderr,
        )
        return

    root = Path.cwd()
    watch_paths = [p for p in (root / "svejk", root / "processed") if p.exists()]
    if not watch_paths:
        return

    print("Sleduji změny ve svejk/ a processed/ pro re-export…", file=sys.stderr)
    for _changes in watch(*watch_paths, recursive=True):
        result = _serve_export_site(args)
        if result is not None:
            print(
                f"Re-export: {result['out_dir']} ({result['pages']} vydání)",
                file=sys.stderr,
            )


def cmd_serve(args: argparse.Namespace) -> int:
    import functools
    import http.server
    import threading

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
            f"Chyba: {site_dir} neexistuje — spusť export-pages nebo serve bez --skip-export",
            file=sys.stderr,
        )
        return 1

    if args.reload:
        threading.Thread(
            target=_serve_reload_watch,
            args=(args,),
            daemon=True,
        ).start()

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


def cmd_validate(args: argparse.Namespace) -> int:
    from svejk.validate import format_validate_report, validate_obdobi

    if args.schuze:
        args.od = args.do = args.schuze
    report = validate_obdobi(
        args.obdobi,
        args.od,
        args.do,
        max_slov_odstavec=args.max_slov,
    )
    text = format_validate_report(report)
    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"Ulozeno: {args.out}", file=sys.stderr)
    return 1 if report.chyby else 0


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


def cmd_audit(args: argparse.Namespace) -> int:
    from svejk.audit import audit_obdobi, format_audit_report

    temata = audit_obdobi(args.obdobi, args.od, args.do)
    report = format_audit_report(temata)
    print(report)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report, encoding="utf-8")
        print(f"Ulozeno: {args.out}", file=sys.stderr)
    chybi = sum(1 for t in temata if t.proslo_alespon_jednou and not t.ma_glosu)
    return 1 if chybi else 0


def cmd_status(_: argparse.Namespace) -> int:
    from sqlalchemy import func, select

    Bod, Schuze, _, Zapisek, get_session, init_db = _require_db()
    init_db()
    with get_session() as session:
        schuze_count = session.scalar(select(func.count()).select_from(Schuze)) or 0
        bod_count = session.scalar(select(func.count()).select_from(Bod)) or 0
        zapisy = list(session.scalars(select(Zapisek)).all())
    print(f"Schůze: {schuze_count}, body: {bod_count}, zápisy: {len(zapisy)}")
    for z in zapisy:
        print(f"  #{z.id} bod={z.bod_id} stav={z.stav}")
    if not HLIDAC_TOKEN:
        print("(HLIDAC_TOKEN není nastaven, ingest nebude fungovat)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Švejk do sněmovny, MVP")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("db", help="Databáze")
    p_init_sub = p_init.add_subparsers(dest="db_cmd", required=True)
    p_init_sub.add_parser("init", help="Vytvoř tabulky").set_defaults(func=cmd_db_init)

    p_ingest = sub.add_parser("ingest", help="Stahni celou schuzi z Hlidace")
    p_ingest.add_argument("--schuze", type=int, required=True)
    p_ingest.add_argument("--obdobi", type=int, default=2025)
    p_ingest.add_argument("--tema", help="Volitelne: jen jedno tema misto cele schuze")
    p_ingest.add_argument("--max-steno", type=int, default=0,
                          help="Limit zaznamu (0 = stahni celou schuzi, ~3-5 min)")
    p_ingest.add_argument("-q", "--quiet", action="store_true", help="Bez prubezneho vypisu")
    p_ingest.set_defaults(func=cmd_ingest)

    p_gen = sub.add_parser("generate", help="Vygeneruj švejkovský zápis")
    p_gen.add_argument("--bod-id", type=int, help="Konkrétní bod")
    p_gen.add_argument("--dry-run", action="store_true", help="Bez ulozeni / mock bez API klice")
    p_gen.add_argument("--claude", action="store_true", help="Pouzij Claude API misto pravidlove casove osy")
    p_gen.set_defaults(func=cmd_generate)

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
        help="File-based pipeline: fetch → align → extract → compose",
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
        help="Kroky oddělené čárkou: fetch,align,extract,compose (výchozí vše)",
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
        help="Synchronizace UNL (PSP) + steno (Hlídač) → processed/ (align, extract)",
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

    p_seed = sub.add_parser("seed", help="Demo data pro lokální test")
    p_seed.add_argument("--schuze", type=int, default=20)
    p_seed.add_argument("--obdobi", type=int, default=2025)
    p_seed.add_argument("--schvalit", action="store_true", help="Rovnou vlož schválený zápis")
    p_seed.set_defaults(func=cmd_seed)

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
    p_serve.add_argument(
        "--reload",
        action="store_true",
        help="Při změně ve svejk/ nebo processed/ znovu spustit export-pages",
    )
    p_serve.set_defaults(func=cmd_serve)

    sub.add_parser("status", help="Stav DB").set_defaults(func=cmd_status)

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

    p_audit = sub.add_parser("audit", help="Inventar temat bez obcanskych glos")
    p_audit.add_argument("--obdobi", type=int, default=2025)
    p_audit.add_argument("--od", type=int, default=1, help="Cislo schuze od")
    p_audit.add_argument("--do", type=int, default=21, help="Cislo schuze do")
    p_audit.add_argument("-o", "--out", type=Path, help="Ulozit report do souboru")
    p_audit.set_defaults(func=cmd_audit)

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

    p_val = sub.add_parser("validate", help="Kontrola glos, casu a fakt z UNL")
    p_val.add_argument("--obdobi", type=int, default=2025)
    p_val.add_argument("--od", type=int, default=1)
    p_val.add_argument("--do", type=int, default=21)
    p_val.add_argument(
        "--max-slov",
        type=int,
        default=80,
        help="Varovani pokud plny odstavec v novinach ma vice slov",
    )
    p_val.add_argument("--schuze", type=int, help="Jen jedna schuze misto rozsahu")
    p_val.add_argument("-o", "--out", type=Path, help="Ulozit report")
    p_val.set_defaults(func=cmd_validate)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
