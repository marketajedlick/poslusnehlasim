"""Export statického webu pro GitHub Pages."""

from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from svejk.build.day_content import build_den_content
from svejk.build.html import (
    css_asset_version,
    fonts_asset_version,
    render_archiv_html,
    render_den_html,
    render_potvrzeno_html,
    render_slovnicek_html,
    render_soukromi_html,
    render_vyznamenani_table_html,
    static_css_path,
    static_fonts_css_path,
)
from svejk.build.vyznamenani_neprosli import load_vyznamenani
from svejk.build.nav import (
    clear_edition_cache,
    edition_pages_href,
    list_obdobi_editions,
    resolve_edition,
)
from svejk.build.seo import write_llms_txt, write_robots_txt, write_sitemap_xml
from svejk.newsletter.config import NewsletterConfig
from svejk.newsletter.doi import export_doi_template
from svejk.newsletter.feed import write_feed_xml
from svejk.paths import SchuzePaths, processed_root

_STATIC = Path(__file__).resolve().parent.parent / "static"
_CSS = _STATIC / "noviny-dlouhe.css"
_FONTS_CSS = _STATIC / "fonts.css"
_FONTS_DIR = _STATIC / "fonts"
_FAVICON_PNG = _STATIC / "svejk-terra.png"
_FAVICON_SVG = _STATIC / "svejk.svg"


def _base_path() -> str:
    return os.environ.get("SVEJK_BASE_PATH", "").rstrip("/")


def _redirect_html(target: str) -> str:
    return (
        "<!DOCTYPE html>\n"
        '<html lang="cs">\n'
        '<head>\n'
        '<meta charset="utf-8" />\n'
        f'<meta http-equiv="refresh" content="0;url={target}" />\n'
        f'<link rel="canonical" href="{target}" />\n'
        "<title>Přesměrování…</title>\n"
        "</head>\n"
        f'<body></body>\n'
        "</html>\n"
    )


def _render_edition_html(
    edition,
    obdobi: int,
    *,
    base: str,
    css_href: str,
    fonts_css_href: str,
) -> str | None:
    paths = SchuzePaths.create(edition.obdobi, edition.schuze)
    d = datetime.strptime(edition.datum_unl, "%d.%m.%Y")
    day_path = paths.facts_by_day / f"{d.strftime('%Y-%m-%d')}.json"
    if not day_path.is_file():
        return None
    content = build_den_content(day_path, paths)
    return render_den_html(
        content,
        paths,
        day_path,
        inline_css=False,
        css_href=css_href,
        fonts_css_href=fonts_css_href,
        link_mode="pages",
        obdobi=obdobi,
        base_path=base,
    )


def run_export_pages(
    obdobi: int,
    out_dir: Path | str,
    *,
    base_path: str | None = None,
    cname: str | None = None,
) -> dict[str, Any]:
    """Vyexportuje všechna vydání období do složky pro GitHub Pages."""
    clear_edition_cache()
    base = _base_path() if base_path is None else base_path.rstrip("/")
    out = Path(out_dir)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    (out / ".nojekyll").touch()
    domain = cname if cname is not None else os.environ.get("SVEJK_PAGES_CNAME", "poslusnehlasim.cz")
    if domain:
        (out / "CNAME").write_text(domain.strip() + "\n", encoding="utf-8")

    static_dir = out / "static"
    static_dir.mkdir()
    shutil.copy2(_CSS, static_dir / "noviny-dlouhe.css")
    shutil.copy2(_FONTS_CSS, static_dir / "fonts.css")
    shutil.copytree(_FONTS_DIR, static_dir / "fonts")
    if _FAVICON_SVG.is_file():
        shutil.copy2(_FAVICON_SVG, static_dir / "favicon.svg")
    if _FAVICON_PNG.is_file():
        shutil.copy2(_FAVICON_PNG, static_dir / "favicon.png")
        shutil.copy2(_FAVICON_PNG, static_dir / "apple-touch-icon.png")
        shutil.copy2(_FAVICON_PNG, out / "favicon.ico")
    css_href = static_css_path(base, version=css_asset_version())
    fonts_css_href = static_fonts_css_path(base, version=fonts_asset_version())

    editions = list_obdobi_editions(obdobi)
    if not editions:
        raise FileNotFoundError(
            f"Žádná vydání v {processed_root()}/{obdobi}-s*, spusť build pro období {obdobi}."
        )

    written: list[str] = []
    for edition in editions:
        html = _render_edition_html(
            edition, obdobi, base=base, css_href=css_href, fonts_css_href=fonts_css_href
        )
        if html is None:
            continue
        dest = out / "noviny" / str(edition.obdobi) / str(edition.schuze) / f"{edition.datum_unl}.html"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(html, encoding="utf-8")
        written.append(str(dest.relative_to(out)))

        paths = SchuzePaths.create(edition.obdobi, edition.schuze)
        for kind in ("neprosli", "prosli", "zvoleni"):
            if not load_vyznamenani(paths, edition.datum_unl, kind):
                continue
            table_html = render_vyznamenani_table_html(
                paths,
                edition.datum_unl,
                kind,
                css_href=css_href,
                fonts_css_href=fonts_css_href,
                base_path=base,
                link_mode="pages",
            )
            if not table_html:
                continue
            table_dest = (
                out
                / "noviny"
                / str(edition.obdobi)
                / str(edition.schuze)
                / f"{edition.datum_unl}-{kind}.html"
            )
            table_dest.parent.mkdir(parents=True, exist_ok=True)
            table_dest.write_text(table_html, encoding="utf-8")
            written.append(str(table_dest.relative_to(out)))

    seen_dates: set[str] = set()
    for edition in editions:
        if edition.datum_unl in seen_dates:
            continue
        seen_dates.add(edition.datum_unl)
        resolved = resolve_edition(obdobi, edition.datum_unl)
        if not resolved:
            continue
        html = _render_edition_html(
            resolved, obdobi, base=base, css_href=css_href, fonts_css_href=fonts_css_href
        )
        if html is None:
            continue
        short = out / "noviny" / str(obdobi) / f"{edition.datum_unl}.html"
        short.parent.mkdir(parents=True, exist_ok=True)
        short.write_text(html, encoding="utf-8")
        written.append(str(short.relative_to(out)))

    latest = editions[-1]
    latest_href = edition_pages_href(latest.obdobi, latest.schuze, latest.datum_unl, base)
    cfg = NewsletterConfig.from_env()
    site = cfg.site_url.rstrip("/")
    paths = SchuzePaths.create(latest.obdobi, latest.schuze)
    d = datetime.strptime(latest.datum_unl, "%d.%m.%Y")
    day_path = paths.facts_by_day / f"{d.strftime('%Y-%m-%d')}.json"
    if not day_path.is_file():
        (out / "index.html").write_text(_redirect_html(f"{site}{latest_href}"), encoding="utf-8")
    else:
        content = build_den_content(day_path, paths)
        index_html = render_den_html(
            content,
            paths,
            day_path,
            inline_css=False,
            css_href=css_href,
            fonts_css_href=fonts_css_href,
            link_mode="pages",
            obdobi=obdobi,
            base_path=base,
            canonical_url=f"{site}/",
        )
        (out / "index.html").write_text(index_html, encoding="utf-8")

    page_count = sum(1 for p in written if p.endswith(".html") and p.count("/") >= 3)

    archiv_html = render_archiv_html(
        obdobi, css_href=css_href, fonts_css_href=fonts_css_href, base_path=base
    )
    (out / "archiv.html").write_text(archiv_html, encoding="utf-8")
    written.append("archiv.html")

    slovnicek_html = render_slovnicek_html(
        obdobi, css_href=css_href, fonts_css_href=fonts_css_href, base_path=base
    )
    (out / "slovnicek.html").write_text(slovnicek_html, encoding="utf-8")
    written.append("slovnicek.html")

    potvrzeno_html = render_potvrzeno_html(
        obdobi, css_href=css_href, fonts_css_href=fonts_css_href, base_path=base
    )
    potvrzeno_dir = out / "potvrzeno"
    potvrzeno_dir.mkdir(parents=True, exist_ok=True)
    (potvrzeno_dir / "index.html").write_text(potvrzeno_html, encoding="utf-8")
    written.append("potvrzeno/index.html")

    soukromi_html = render_soukromi_html(
        obdobi, css_href=css_href, fonts_css_href=fonts_css_href, base_path=base
    )
    soukromi_dir = out / "soukromi"
    soukromi_dir.mkdir(parents=True, exist_ok=True)
    (soukromi_dir / "index.html").write_text(soukromi_html, encoding="utf-8")
    written.append("soukromi/index.html")

    doi_export = export_doi_template(out / "email", base_path=base)
    written.append("email/doi.html")

    feed_path = write_feed_xml(obdobi, out / "feed.xml", config=cfg, base_path=base)
    robots_path = write_robots_txt(out, site_url=site)
    sitemap_path = write_sitemap_xml(out, editions, site_url=site, base_path=base)
    llms_path, llms_full_path = write_llms_txt(
        out, list(editions), site_url=site, base_path=base, obdobi=obdobi
    )

    return {
        "obdobi": obdobi,
        "files": len(written) + 2,
        "pages": page_count,
        "latest": latest_href,
        "feed": str(feed_path.relative_to(out)),
        "robots": str(robots_path.relative_to(out)),
        "sitemap": str(sitemap_path.relative_to(out)),
        "llms": str(llms_path.relative_to(out)),
        "llms_full": str(llms_full_path.relative_to(out)),
        "newsletter": cfg.enabled,
        "doi_template": doi_export["html"],
        "doi_subject": doi_export["subject"],
        "out_dir": str(out),
    }
