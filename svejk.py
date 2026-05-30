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

"""CLI pro Svejk do snemovny — ingest, generovani, web."""

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
    """SQLite/ORM vrstva — volitelná; build a export-pages ji nepotřebují."""
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
    from svejk.timeline import normalize_day

    paths = SchuzePaths.create(args.obdobi, args.schuze)
    out_dir = paths.noviny_dlouhe_dir()
    ext = "html" if fmt == "noviny-html" else "md"
    if fmt not in ("noviny-dlouhe", "noviny-html"):
        return None

    if args.den:
        d_unl = normalize_day(args.den)
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
    from svejk.build import run_build, run_build_obdobi

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
    """Demo data bez API — pro lokální test webu."""
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
                    "o penězích — jenže tam šlo o cigarety, ne o pojistné. Tady poslanci hlasovali "
                    "o tom, že živnostník ušetří sedm set korun měsíčně. Zaměstnanec u piva? "
                    "To se vás netýká — vy máte mzdu a oni mají faktury."
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


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn
    uvicorn.run("svejk.app:app", host=args.host, port=args.port, reload=args.reload)
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
        print("(HLIDAC_TOKEN není nastaven — ingest nebude fungovat)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Švejk do sněmovny — MVP")
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

    p_seed = sub.add_parser("seed", help="Demo data pro lokální test")
    p_seed.add_argument("--schuze", type=int, default=20)
    p_seed.add_argument("--obdobi", type=int, default=2025)
    p_seed.add_argument("--schvalit", action="store_true", help="Rovnou vlož schválený zápis")
    p_seed.set_defaults(func=cmd_seed)

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

    p_serve = sub.add_parser("serve", help="Spusť web")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8000)
    p_serve.add_argument("--reload", action="store_true")
    p_serve.set_defaults(func=cmd_serve)

    sub.add_parser("status", help="Stav DB").set_defaults(func=cmd_status)

    p_audit = sub.add_parser("audit", help="Inventar temat bez obcanskych glos")
    p_audit.add_argument("--obdobi", type=int, default=2025)
    p_audit.add_argument("--od", type=int, default=1, help="Cislo schuze od")
    p_audit.add_argument("--do", type=int, default=21, help="Cislo schuze do")
    p_audit.add_argument("-o", "--out", type=Path, help="Ulozit report do souboru")
    p_audit.set_defaults(func=cmd_audit)

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
