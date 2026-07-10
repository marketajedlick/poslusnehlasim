"""Export statického webu pro GitHub Pages."""

from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from svejk.text_norm import ma_dlouhou_pomlcku
from svejk.build.day_content import build_den_content, clear_den_content_cache
from svejk.glossary import slovnicek_entries, slovnicek_term_slug
from svejk.build.slovnicek_index import build_slovnicek_mentions_index, term_mentions
from svejk.build.html import (
    css_asset_version,
    fonts_asset_version,
    inject_site_footer,
    render_archiv_html,
    render_404_html,
    render_den_html,
    render_dekuju_html,
    render_o_webu_html,
    render_podminky_html,
    render_podpora_html,
    render_pivo_html,
    render_potvrzeno_html,
    render_slovnicek_html,
    render_slovnicek_term_html,
    render_soukromi_html,
    render_vyznamenani_table_html,
    render_steno_sources_html,
    render_smlouvy_html,
    render_recnici_table_html,
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
    render_edition_share_hero_image,
    share_hero_filename,
)
from svejk.strings import load_strings
from svejk.build.vyznamenani_neprosli import load_vyznamenani
from svejk.build.steno_sources import has_steno_sources
from svejk.build.recnici import has_recnici
from svejk.build.mezin_smlouvy import has_smlouvy
from svejk.build.nav import (
    archiv_pages_href,
    clear_edition_cache,
    edition_pages_href,
    recnici_pages_href,
    resolve_edition,
    slovnicek_pages_href,
    smlouvy_pages_href,
    steno_sources_pages_href,
    vyznamenani_pages_href,
)
from svejk.build.urls import (
    datum_unl_to_iso,
    edition_export_relpath,
    edition_subpage_export_relpath,
)
from svejk.build.publish import (
    clear_publish_cache,
    edition_source,
    list_approved_editions,
    list_site_editions,
    snapshot_path,
)
from svejk.build.seo import (
    write_llms_txt,
    write_robots_txt,
    write_security_txt,
    write_sitemap_xml,
)
from svejk.newsletter.config import NewsletterConfig
from svejk.newsletter.doi import export_doi_template
from svejk.newsletter.feed import write_feed_xml
from svejk.paths import SchuzePaths, processed_root

_STATIC = Path(__file__).resolve().parent.parent / "static"
_CSS = _STATIC / "noviny-dlouhe.css"
_FONTS_CSS = _STATIC / "fonts.css"
_FONTS_DIR = _STATIC / "fonts"
_FAVICON_PNG = _STATIC / "ph-fav.png"
_FAVICON_SVG = _STATIC / "ph-fav.svg"
_OG_SHARE = _STATIC / "og-share.png"
_SVEJK_TERRA = _STATIC / "svejk-terra.png"


def _write_html(path: Path, html: str) -> None:
    if ma_dlouhou_pomlcku(html):
        raise ValueError(
            f"Zakázaná dlouhá pomlčka (—/–) ve výstupu {path}, oprav zdrojové texty."
        )
    path.write_text(html, encoding="utf-8")


def _write_page_html(out: Path, rel_path: str, html: str) -> str:
    dest = out / rel_path
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


def _write_redirect_page(out: Path, rel_path: str, target_href: str, *, site_url: str) -> str:
    target = target_href if target_href.startswith("http") else f"{site_url}{target_href}"
    return _write_page_html(out, rel_path, _redirect_html(target))


def _edition_day_path(edition) -> Path | None:
    paths = SchuzePaths.create(edition.obdobi, edition.schuze)
    d = datetime.strptime(edition.datum_unl, "%d.%m.%Y")
    day_path = paths.facts_by_day / f"{d.strftime('%Y-%m-%d')}.json"
    return day_path if day_path.is_file() else None


def _edition_og_fields(edition, *, snapshot_html: str = "") -> dict[str, str | int]:
    day_path = _edition_day_path(edition)
    if day_path is not None:
        from svejk.build.day_content import _topics_by_slug, split_zaver
        from svejk.build.io import read_json
        from svejk.text_norm import lcfirst_preserve_proper

        paths = SchuzePaths.create(edition.obdobi, edition.schuze)
        day = read_json(day_path)
        stats = day.get("stats") or {}
        override = (day.get("zaver") or "").strip()
        if override:
            zaver = (
                override
                if override.lower().startswith("poslušně")
                else f"Poslušně hlásím, {lcfirst_preserve_proper(override)}"
            )
        else:
            zaver = ""
        zaver_key, zaver_body = split_zaver(zaver)
        topics = _topics_by_slug(paths)
        slugs = day.get("topic_slugs") or []
        first_nadpis = ""
        if slugs and slugs[0] in topics:
            first_nadpis = str(topics[slugs[0]].get("nadpis") or "")
        return {
            "den": str(day.get("den") or ""),
            "dnesni_ucet": str(day.get("dnesni_ucet") or ""),
            "nadpis_vydani": "",
            "first_item_nadpis": first_nadpis,
            "proslo": int(stats.get("proslo") or 0),
            "zamitnuto": int(stats.get("zamitnuto") or 0),
            "zaver_key": zaver_key,
            "zaver_body": zaver_body,
            "zaver": zaver,
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
        "zaver_key": "",
        "zaver_body": "",
        "zaver": "",
    }


def _inject_edition_og(
    html: str,
    edition,
    *,
    base: str,
    site_url: str,
) -> str:
    fields = _edition_og_fields(edition)
    og_title = edition_og_title(edition.datum_unl, str(fields["den"]))
    og_headline = edition_og_headline(
        dnesni_ucet=str(fields["dnesni_ucet"]),
        nadpis_vydani=str(fields.get("nadpis_vydani") or ""),
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
) -> str | None:
    paths = SchuzePaths.create(edition.obdobi, edition.schuze)
    d = datetime.strptime(edition.datum_unl, "%d.%m.%Y")
    day_path = paths.facts_by_day / f"{d.strftime('%Y-%m-%d')}.json"
    if not day_path.is_file():
        return None
    content = build_den_content(
        day_path, paths, link_mode="pages", base_path=base
    )
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
    """Vyexportuje schválená vydání období do složky pro GitHub Pages."""
    clear_edition_cache()
    clear_publish_cache()
    clear_den_content_cache()
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
        shutil.copy2(_FAVICON_SVG, static_dir / "ph-fav.svg")
    if _FAVICON_PNG.is_file():
        shutil.copy2(_FAVICON_PNG, static_dir / "favicon.png")
        shutil.copy2(_FAVICON_PNG, static_dir / "apple-touch-icon.png")
        shutil.copy2(_FAVICON_PNG, out / "favicon.ico")
    if _OG_SHARE.is_file():
        shutil.copy2(_OG_SHARE, static_dir / "og-share.png")
    if _SVEJK_TERRA.is_file():
        shutil.copy2(_SVEJK_TERRA, static_dir / "svejk-terra.png")

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
        key = edition.datum_unl
        if key in og_dates:
            continue
        og_dates.add(key)
        snapshot_html = ""
        if edition_source(edition) == "snapshot":
            snapshot_html = snapshot_path(edition).read_text(encoding="utf-8")
        fields = _edition_og_fields(edition, snapshot_html=snapshot_html)
        og_subdir = out / "og"
        og_subdir.mkdir(parents=True, exist_ok=True)
        sign = load_strings().get("edition", {}).get(
            "sign", "- Váš dobrý voják Švejk -"
        )
        render_edition_og_image(
            og_subdir,
            datum_unl=edition.datum_unl,
            den=str(fields["den"]),
            dnesni_ucet=str(fields["dnesni_ucet"]),
            nadpis_vydani=str(fields.get("nadpis_vydani") or ""),
            first_item_nadpis=str(fields["first_item_nadpis"]),
            zaver_key=str(fields.get("zaver_key") or ""),
            zaver_body=str(fields.get("zaver_body") or ""),
            zaver=str(fields.get("zaver") or ""),
            sign=sign,
        )
        written.append(f"og/{og_image_filename(edition.datum_unl)}")

        share_subdir = out / "share"
        share_subdir.mkdir(parents=True, exist_ok=True)
        if render_edition_share_hero_image(
            share_subdir,
            datum_unl=edition.datum_unl,
            zaver_key=str(fields.get("zaver_key") or ""),
            zaver_body=str(fields.get("zaver_body") or ""),
            zaver=str(fields.get("zaver") or ""),
            sign=sign,
        ):
            written.append(f"share/{share_hero_filename(edition.datum_unl)}")

    def _export_edition_page(
        edition,
        rel_path: str,
    ) -> str | None:
        src = edition_source(edition)
        if src == "snapshot":
            raw = snapshot_path(edition).read_text(encoding="utf-8")
            raw = inject_site_footer(raw, base)
            raw = _inject_edition_og(raw, edition, base=base, site_url=site)
            return _write_page_html(out, rel_path, raw)
        html = _render_edition_html(
            edition,
            obdobi,
            base=base,
            css_href=css_href,
            fonts_css_href=fonts_css_href,
        )
        if html is None:
            return None
        return _write_page_html(out, rel_path, html)

    exported_rels: set[str] = set()
    for edition in editions:
        if edition_source(edition) is None:
            continue
        canonical = resolve_edition(obdobi, edition.datum_unl)
        siblings = tuple(e for e in editions if e.datum_unl == edition.datum_unl)
        if len(siblings) > 1 and canonical and edition.schuze != canonical.schuze:
            rel = edition_export_relpath(edition.datum_unl, edition.schuze)
        else:
            rel = edition_export_relpath(edition.datum_unl)
        if rel in exported_rels:
            continue
        exported_rels.add(rel)

        rel_written = _export_edition_page(edition, rel)
        if rel_written:
            written.append(rel_written)

        if edition_source(edition) == "snapshot":
            continue

        if canonical and edition.schuze != canonical.schuze:
            continue

        paths = SchuzePaths.create(edition.obdobi, edition.schuze)
        for kind in ("neprosli", "prosli", "zvoleni"):
            if not load_vyznamenani(paths, edition.datum_unl, kind):
                continue
            table_rel = edition_subpage_export_relpath(edition.datum_unl, kind)
            table_html = render_vyznamenani_table_html(
                paths,
                edition.datum_unl,
                kind,
                css_href=css_href,
                fonts_css_href=fonts_css_href,
                base_path=base,
                link_mode="pages",
            )
            if table_html:
                written.append(_write_page_html(out, table_rel, table_html))

        if has_steno_sources(paths, edition.datum_unl):
            steno_rel = edition_subpage_export_relpath(edition.datum_unl, "steno")
            steno_html = render_steno_sources_html(
                paths,
                edition.datum_unl,
                css_href=css_href,
                fonts_css_href=fonts_css_href,
                base_path=base,
                link_mode="pages",
            )
            if steno_html:
                written.append(_write_page_html(out, steno_rel, steno_html))

        if has_recnici(paths, edition.datum_unl):
            recnici_rel = edition_subpage_export_relpath(edition.datum_unl, "recnici")
            recnici_html = render_recnici_table_html(
                paths,
                edition.datum_unl,
                css_href=css_href,
                fonts_css_href=fonts_css_href,
                base_path=base,
                link_mode="pages",
            )
            if recnici_html:
                written.append(_write_page_html(out, recnici_rel, recnici_html))

        if has_smlouvy(paths, edition.datum_unl):
            smlouvy_rel = edition_subpage_export_relpath(edition.datum_unl, "smlouvy")
            smlouvy_html = render_smlouvy_html(
                paths,
                edition.datum_unl,
                css_href=css_href,
                fonts_css_href=fonts_css_href,
                base_path=base,
                link_mode="pages",
            )
            if smlouvy_html:
                written.append(_write_page_html(out, smlouvy_rel, smlouvy_html))

    for edition in editions:
        if edition_source(edition) is None:
            continue
        target = edition_pages_href(
            edition.obdobi, edition.schuze, edition.datum_unl, base
        )
        written.append(
            _write_redirect_page(
                out,
                f"noviny/{edition.obdobi}/{edition.schuze}/{edition.datum_unl}.html",
                target,
                site_url=site,
            )
        )
        paths = SchuzePaths.create(edition.obdobi, edition.schuze)
        for kind in ("neprosli", "prosli", "zvoleni"):
            if not load_vyznamenani(paths, edition.datum_unl, kind):
                continue
            sub_target = vyznamenani_pages_href(
                edition.obdobi, edition.schuze, edition.datum_unl, kind, base
            )
            written.append(
                _write_redirect_page(
                    out,
                    f"noviny/{edition.obdobi}/{edition.schuze}/{edition.datum_unl}-{kind}.html",
                    sub_target,
                    site_url=site,
                )
            )
        if has_steno_sources(paths, edition.datum_unl):
            written.append(
                _write_redirect_page(
                    out,
                    f"noviny/{edition.obdobi}/{edition.schuze}/{edition.datum_unl}-steno.html",
                    steno_sources_pages_href(
                        edition.obdobi, edition.schuze, edition.datum_unl, base
                    ),
                    site_url=site,
                )
            )
        if has_recnici(paths, edition.datum_unl):
            written.append(
                _write_redirect_page(
                    out,
                    f"noviny/{edition.obdobi}/{edition.schuze}/{edition.datum_unl}-recnici.html",
                    recnici_pages_href(
                        edition.obdobi, edition.schuze, edition.datum_unl, base
                    ),
                    site_url=site,
                )
            )
        if has_smlouvy(paths, edition.datum_unl):
            written.append(
                _write_redirect_page(
                    out,
                    f"noviny/{edition.obdobi}/{edition.schuze}/{edition.datum_unl}-smlouvy.html",
                    smlouvy_pages_href(
                        edition.obdobi, edition.schuze, edition.datum_unl, base
                    ),
                    site_url=site,
                )
            )

    seen_short_dates: set[str] = set()
    for edition in editions:
        if edition.datum_unl in seen_short_dates:
            continue
        seen_short_dates.add(edition.datum_unl)
        resolved = resolve_edition(obdobi, edition.datum_unl)
        if not resolved or edition_source(resolved) is None:
            continue
        target = edition_pages_href(
            resolved.obdobi, resolved.schuze, resolved.datum_unl, base
        )
        written.append(
            _write_redirect_page(
                out,
                f"noviny/{obdobi}/{edition.datum_unl}.html",
                target,
                site_url=site,
            )
        )

    approved = list_approved_editions(obdobi)
    latest = editions[-1]
    homepage_edition = approved[-1] if approved else latest
    paths = SchuzePaths.create(homepage_edition.obdobi, homepage_edition.schuze)
    d = datetime.strptime(homepage_edition.datum_unl, "%d.%m.%Y")
    day_path = paths.facts_by_day / f"{d.strftime('%Y-%m-%d')}.json"
    latest_href = edition_pages_href(
        latest.obdobi, latest.schuze, latest.datum_unl, base
    )
    if edition_source(homepage_edition) == "snapshot" or not day_path.is_file():
        home_target = f"{site}{latest_href}"
        written.append(_write_page_html(out, "index.html", _redirect_html(home_target)))
    else:
        content = build_den_content(
            day_path, paths, link_mode="pages", base_path=base
        )
        home_canonical = f"{site}/"
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
        )
        written.append(_write_page_html(out, "index.html", index_html))

    latest_href = edition_pages_href(latest.obdobi, latest.schuze, latest.datum_unl, base)

    page_count = sum(1 for p in written if p.endswith(".html") and p.count("/") >= 3)

    static_pages: list[tuple[str, str]] = [
        ("archiv/index.html", "archiv"),
        ("404.html", "404"),
        ("slovnicek/index.html", "slovnicek"),
        ("pivo.html", "pivo"),
        ("dekuju.html", "dekuju"),
        ("podminky/index.html", "podminky"),
        ("o-webu/index.html", "o-webu"),
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
        "o-webu": render_o_webu_html,
        "podminky": render_podminky_html,
        "podpora": render_podpora_html,
        "potvrzeno": render_potvrzeno_html,
        "soukromi": render_soukromi_html,
    }
    for rel_path, key in static_pages:
        html = render_map[key](
            obdobi,
            css_href=css_href,
            fonts_css_href=fonts_css_href,
            base_path=base,
        )
        written.append(_write_page_html(out, rel_path, html))

    mentions_index = build_slovnicek_mentions_index(obdobi, base_path=base)
    for term, answer in slovnicek_entries():
        slug = slovnicek_term_slug(term)
        term_html = render_slovnicek_term_html(
            obdobi,
            term=term,
            answer=answer,
            slug=slug,
            mentions=term_mentions(term, mentions_index),
            css_href=css_href,
            fonts_css_href=fonts_css_href,
            base_path=base,
        )
        written.append(_write_page_html(out, f"slovnicek/{slug}/index.html", term_html))

    written.append(
        _write_redirect_page(
            out, "archiv.html", archiv_pages_href(base), site_url=site
        )
    )
    written.append(
        _write_redirect_page(
            out, "slovnicek.html", slovnicek_pages_href(base), site_url=site
        )
    )

    doi_export = export_doi_template(out / "email", base_path=base)
    written.append("email/doi.html")

    feed_path = write_feed_xml(obdobi, out / "feed.xml", config=cfg, base_path=base)
    robots_path = write_robots_txt(out, site_url=site)
    security_path = write_security_txt(out, site_url=site)
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
        "security_txt": str(security_path.relative_to(out)),
        "sitemap": str(sitemap_path.relative_to(out)),
        "llms": str(llms_path.relative_to(out)),
        "llms_full": str(llms_full_path.relative_to(out)),
        "newsletter": cfg.enabled,
        "doi_template": doi_export["html"],
        "doi_subject": doi_export["subject"],
        "out_dir": str(out),
    }
