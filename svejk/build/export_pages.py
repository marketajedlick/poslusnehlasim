"""Export statického webu pro GitHub Pages."""

from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from svejk.text_norm import ma_dlouhou_pomlcku
from svejk.build.day_content import build_den_content
from svejk.build.html import (
    css_asset_version,
    fonts_asset_version,
    inject_site_footer,
    render_archiv_html,
    render_404_html,
    render_den_html,
    render_dekuju_html,
    render_podminky_html,
    render_podpora_html,
    render_pivo_html,
    render_potvrzeno_html,
    render_slovnicek_html,
    render_soukromi_html,
    render_vyznamenani_table_html,
    static_css_path,
    static_fonts_css_path,
)
from svejk.build.og_image import (
    OG_HEIGHT,
    OG_WIDTH,
    edition_og_headline,
    edition_og_title,
    inject_og_image,
    og_image_abs_url,
    og_image_filename,
    render_edition_og_image,
)
from svejk.build.vyznamenani_neprosli import load_vyznamenani
from svejk.build.nav import (
    clear_edition_cache,
    edition_pages_href,
    resolve_edition,
)
from svejk.build.publish import (
    clear_publish_cache,
    edition_source,
    list_approved_editions,
    list_site_editions,
    snapshot_path,
)
from svejk.build.seo import write_llms_txt, write_robots_txt, write_sitemap_xml
from svejk.locale import SUPPORTED_LOCALES, localized_path, normalize_locale
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
_OG_SHARE = _STATIC / "og-share.png"


def _write_html(path: Path, html: str) -> None:
    if ma_dlouhou_pomlcku(html):
        raise ValueError(
            f"Zakázaná dlouhá pomlčka (—/–) ve výstupu {path}, oprav zdrojové texty."
        )
    path.write_text(html, encoding="utf-8")


def _locale_site_subdir(locale: str) -> Path:
    return Path("en") if normalize_locale(locale) == "en" else Path(".")


def _write_locale_html(out: Path, rel_path: str, html: str, locale: str) -> str:
    sub = _locale_site_subdir(locale)
    dest = out / sub / rel_path if sub != Path(".") else out / rel_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    _write_html(dest, html)
    return str(dest.relative_to(out))


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


def _edition_day_path(edition) -> Path | None:
    paths = SchuzePaths.create(edition.obdobi, edition.schuze)
    d = datetime.strptime(edition.datum_unl, "%d.%m.%Y")
    day_path = paths.facts_by_day / f"{d.strftime('%Y-%m-%d')}.json"
    return day_path if day_path.is_file() else None


def _edition_og_fields(edition, *, snapshot_html: str = "", locale: str = "cs") -> dict[str, str | int]:
    day_path = _edition_day_path(edition)
    if day_path is not None:
        paths = SchuzePaths.create(edition.obdobi, edition.schuze)
        content = build_den_content(day_path, paths, locale=locale)
        return {
            "den": content.den,
            "dnesni_ucet": content.dnesni_ucet,
            "first_item_nadpis": content.items[0].nadpis if content.items else "",
            "proslo": content.proslo,
            "zamitnuto": content.zamitnuto,
        }
    import re

    desc = ""
    if snapshot_html:
        match = re.search(r'<meta name="description" content="([^"]*)"', snapshot_html)
        if match:
            desc = match.group(1)
    return {
        "den": "",
        "dnesni_ucet": desc,
        "first_item_nadpis": "",
        "proslo": 0,
        "zamitnuto": 0,
    }


def _inject_edition_og(html: str, edition, *, base: str, site_url: str) -> str:
    fields = _edition_og_fields(edition)
    og_title = edition_og_title(edition.datum_unl, str(fields["den"]))
    og_headline = edition_og_headline(
        dnesni_ucet=str(fields["dnesni_ucet"]),
        first_item_nadpis=str(fields["first_item_nadpis"]),
        datum_unl=edition.datum_unl,
        den=str(fields["den"]),
    )
    return inject_og_image(
        html,
        og_image_url=og_image_abs_url(site_url, base, edition.datum_unl),
        og_image_width=OG_WIDTH,
        og_image_height=OG_HEIGHT,
        og_image_alt=og_headline,
        og_title=og_title,
    )


def _render_edition_html(
    edition,
    obdobi: int,
    *,
    base: str,
    css_href: str,
    fonts_css_href: str,
    locale: str = "cs",
) -> str | None:
    paths = SchuzePaths.create(edition.obdobi, edition.schuze)
    d = datetime.strptime(edition.datum_unl, "%d.%m.%Y")
    day_path = paths.facts_by_day / f"{d.strftime('%Y-%m-%d')}.json"
    if not day_path.is_file():
        return None
    content = build_den_content(day_path, paths, locale=locale)
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
        locale=locale,
        show_locale_notice=False,
    )


def run_export_pages(
    obdobi: int,
    out_dir: Path | str,
    *,
    base_path: str | None = None,
    cname: str | None = None,
) -> dict[str, Any]:
    """Vyexportuje schválená vydání období do složky pro GitHub Pages."""
    clear_edition_cache()
    clear_publish_cache()
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
    if _OG_SHARE.is_file():
        shutil.copy2(_OG_SHARE, static_dir / "og-share.png")

    og_dir = out / "og"
    og_dir.mkdir()
    cfg = NewsletterConfig.from_env()
    site = cfg.site_url.rstrip("/")
    css_href = static_css_path(base, version=css_asset_version())
    fonts_css_href = static_fonts_css_path(base, version=fonts_asset_version())

    editions = list_site_editions(obdobi)
    if not editions:
        raise FileNotFoundError(
            f"Žádná schválená vydání v {processed_root()}/{obdobi}-s* "
            f"(zkontroluj publish-approved.json a publish-snapshots/)."
        )

    written: list[str] = []
    og_dates: set[str] = set()
    for edition in editions:
        if edition.datum_unl in og_dates:
            continue
        og_dates.add(edition.datum_unl)
        snapshot_html = ""
        if edition_source(edition) == "snapshot":
            snapshot_html = snapshot_path(edition).read_text(encoding="utf-8")
        fields = _edition_og_fields(edition, snapshot_html=snapshot_html)
        render_edition_og_image(
            og_dir,
            datum_unl=edition.datum_unl,
            den=str(fields["den"]),
            dnesni_ucet=str(fields["dnesni_ucet"]),
            first_item_nadpis=str(fields["first_item_nadpis"]),
            proslo=int(fields["proslo"]),
            zamitnuto=int(fields["zamitnuto"]),
        )
        written.append(f"og/{og_image_filename(edition.datum_unl)}")

    def _export_edition_page(
        edition,
        rel_path: str,
        *,
        locale: str = "cs",
    ) -> str | None:
        loc = normalize_locale(locale)
        src = edition_source(edition)
        if src == "snapshot" and loc == "cs":
            raw = snapshot_path(edition).read_text(encoding="utf-8")
            raw = inject_site_footer(raw, base)
            raw = _inject_edition_og(raw, edition, base=base, site_url=site)
            return _write_locale_html(out, rel_path, raw, loc)
        html = _render_edition_html(
            edition,
            obdobi,
            base=base,
            css_href=css_href,
            fonts_css_href=fonts_css_href,
            locale=loc,
        )
        if html is None:
            return None
        return _write_locale_html(out, rel_path, html, loc)

    for edition in editions:
        rel = f"noviny/{edition.obdobi}/{edition.schuze}/{edition.datum_unl}.html"
        for locale in SUPPORTED_LOCALES:
            rel_written = _export_edition_page(edition, rel, locale=locale)
            if rel_written:
                written.append(rel_written)

        if edition_source(edition) == "snapshot":
            continue

        paths = SchuzePaths.create(edition.obdobi, edition.schuze)
        for kind in ("neprosli", "prosli", "zvoleni"):
            if not load_vyznamenani(paths, edition.datum_unl, kind):
                continue
            table_rel = (
                f"noviny/{edition.obdobi}/{edition.schuze}/{edition.datum_unl}-{kind}.html"
            )
            for locale in SUPPORTED_LOCALES:
                table_html = render_vyznamenani_table_html(
                    paths,
                    edition.datum_unl,
                    kind,
                    css_href=css_href,
                    fonts_css_href=fonts_css_href,
                    base_path=base,
                    link_mode="pages",
                    locale=locale,
                )
                if not table_html:
                    continue
                written.append(_write_locale_html(out, table_rel, table_html, locale))

    seen_dates: set[str] = set()
    for edition in editions:
        if edition.datum_unl in seen_dates:
            continue
        seen_dates.add(edition.datum_unl)
        resolved = resolve_edition(obdobi, edition.datum_unl)
        if not resolved or edition_source(resolved) is None:
            continue
        short_rel = f"noviny/{obdobi}/{edition.datum_unl}.html"
        for locale in SUPPORTED_LOCALES:
            rel_written = _export_edition_page(resolved, short_rel, locale=locale)
            if rel_written:
                written.append(rel_written)

    approved = list_approved_editions(obdobi)
    latest = editions[-1]
    homepage_edition = approved[-1] if approved else latest
    paths = SchuzePaths.create(homepage_edition.obdobi, homepage_edition.schuze)
    d = datetime.strptime(homepage_edition.datum_unl, "%d.%m.%Y")
    day_path = paths.facts_by_day / f"{d.strftime('%Y-%m-%d')}.json"
    for locale in SUPPORTED_LOCALES:
        loc = normalize_locale(locale)
        latest_href = edition_pages_href(
            latest.obdobi, latest.schuze, latest.datum_unl, base, loc
        )
        if edition_source(homepage_edition) == "snapshot" or not day_path.is_file():
            home_target = f"{site}{latest_href}"
            written.append(_write_locale_html(out, "index.html", _redirect_html(home_target), loc))
        else:
            content = build_den_content(day_path, paths, locale=locale)
            home_canonical = f"{site}{localized_path('/', loc)}"
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
                canonical_url=home_canonical,
                is_homepage=True,
                locale=loc,
                show_locale_notice=False,
            )
            written.append(_write_locale_html(out, "index.html", index_html, loc))

    latest_href = edition_pages_href(latest.obdobi, latest.schuze, latest.datum_unl, base)

    page_count = sum(1 for p in written if p.endswith(".html") and p.count("/") >= 3)

    static_pages: list[tuple[str, str]] = [
        ("archiv.html", "archiv"),
        ("404.html", "404"),
        ("slovnicek.html", "slovnicek"),
        ("pivo.html", "pivo"),
        ("dekuju.html", "dekuju"),
        ("podminky/index.html", "podminky"),
        ("podpora/index.html", "podpora"),
        ("potvrzeno/index.html", "potvrzeno"),
        ("soukromi/index.html", "soukromi"),
    ]
    render_map = {
        "archiv": render_archiv_html,
        "404": render_404_html,
        "slovnicek": render_slovnicek_html,
        "pivo": render_pivo_html,
        "dekuju": render_dekuju_html,
        "podminky": render_podminky_html,
        "podpora": render_podpora_html,
        "potvrzeno": render_potvrzeno_html,
        "soukromi": render_soukromi_html,
    }
    for rel_path, key in static_pages:
        for locale in SUPPORTED_LOCALES:
            html = render_map[key](
                obdobi,
                css_href=css_href,
                fonts_css_href=fonts_css_href,
                base_path=base,
                locale=locale,
            )
            written.append(_write_locale_html(out, rel_path, html, locale))

    doi_export = export_doi_template(out / "email", base_path=base)
    written.append("email/doi.html")
    written.append("email/doi-en.html")

    feed_path = write_feed_xml(obdobi, out / "feed.xml", config=cfg, base_path=base)
    feed_en_path = write_feed_xml(
        obdobi, out / "feed-en.xml", config=cfg, base_path=base, locale="en"
    )
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
        "feed_en": str(feed_en_path.relative_to(out)),
        "robots": str(robots_path.relative_to(out)),
        "sitemap": str(sitemap_path.relative_to(out)),
        "llms": str(llms_path.relative_to(out)),
        "llms_full": str(llms_full_path.relative_to(out)),
        "newsletter": cfg.enabled,
        "doi_template": doi_export["html"],
        "doi_subject": doi_export["subject"],
        "out_dir": str(out),
    }
