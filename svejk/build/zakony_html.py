"""HTML stránek zákonů (`/zakony/`, `/zakony/{slug}/`)."""

from __future__ import annotations

from typing import Any

from svejk.build.html import (
    _jinja_env,
    _og_context,
    _page_path_from_canonical,
    _ph_fav_href,
    _site_ctx,
    _site_footer_ctx,
    _site_nav_ctx,
    css_asset_version,
    fonts_asset_version,
    static_css_path,
    static_favicon_paths,
    static_fonts_css_path,
)
from svejk.build.nav import soukromi_pages_href, zakony_pages_href
from svejk.build.seo import SITE_NAME, breadcrumb_page_ctx, _home_href
from svejk.build.zakony import list_zakony
from svejk.newsletter.config import NewsletterConfig
from svejk.strings import load_strings

INDEX_TITLE = "Zákony"
INDEX_GLOSS = (
    "Jak zákon putuje Sněmovnou: od prvního čtení po podpis. "
    "Uprostřed co prošlo a v jakém znění, po stranách co k tomu řekla vláda a opozice."
)


def _common_ctx(
    obdobi: int,
    *,
    canonical_href: str,
    title: str,
    description: str,
    css_href: str | None,
    fonts_css_href: str | None,
    base_path: str,
    closing_seed: str,
) -> dict[str, Any]:
    if css_href is None:
        css_href = static_css_path(base_path, version=css_asset_version())
    if fonts_css_href is None:
        fonts_css_href = static_fonts_css_path(base_path, version=fonts_asset_version())
    cfg = NewsletterConfig.from_env()
    canonical_url = f"{cfg.site_url.rstrip('/')}{canonical_href}"
    page_path = _page_path_from_canonical(canonical_url, cfg.site_url)
    return {
        "canonical_url": canonical_url,
        "title": title,
        "meta_description": description,
        **_og_context(
            site_url=cfg.site_url,
            base_path=base_path,
            title=title,
            description=description,
        ),
        "inline_css": False,
        "css": "",
        "css_href": css_href,
        "fonts_css_href": fonts_css_href,
        "cookie_privacy_url": soukromi_pages_href(base_path),
        **_site_ctx(site_url=cfg.site_url, base_path=base_path, page_path=page_path),
        **_site_nav_ctx(obdobi, base_path),
        **_site_footer_ctx(base_path, obdobi=obdobi, closing_seed=closing_seed),
        **static_favicon_paths(base_path),
        "ph_fav_href": _ph_fav_href(base_path),
        "t": load_strings(),
    }


def render_zakony_index_html(
    obdobi: int,
    *,
    css_href: str | None = None,
    fonts_css_href: str | None = None,
    base_path: str = "",
) -> str:
    cfg = NewsletterConfig.from_env()
    ctx = _common_ctx(
        obdobi,
        canonical_href=zakony_pages_href(base_path),
        title=f"{INDEX_TITLE} · {SITE_NAME}",
        description=INDEX_GLOSS,
        css_href=css_href,
        fonts_css_href=fonts_css_href,
        base_path=base_path,
        closing_seed="zakony",
    )
    ctx.update(
        breadcrumb_page_ctx(
            site_url=cfg.site_url,
            items=((SITE_NAME, _home_href(base_path)), (INDEX_TITLE, None)),
        )
    )
    return (
        _jinja_env()
        .get_template("zakony-stranka.html")
        .render(
            zakony=list_zakony(base_path),
            page_heading=INDEX_TITLE,
            page_intro=INDEX_GLOSS,
            **ctx,
        )
    )


def render_zakon_html(
    obdobi: int,
    zakon: dict[str, Any],
    *,
    css_href: str | None = None,
    fonts_css_href: str | None = None,
    base_path: str = "",
) -> str:
    cfg = NewsletterConfig.from_env()
    title = f"{zakon.get('nazev', '')} · {SITE_NAME}"
    ctx = _common_ctx(
        obdobi,
        canonical_href=zakon["href"],
        title=title,
        description=zakon.get("meta") or zakon.get("perex", ""),
        css_href=css_href,
        fonts_css_href=fonts_css_href,
        base_path=base_path,
        closing_seed=f"zakony/{zakon['slug']}",
    )
    ctx.update(
        breadcrumb_page_ctx(
            site_url=cfg.site_url,
            items=(
                (SITE_NAME, _home_href(base_path)),
                (INDEX_TITLE, zakony_pages_href(base_path)),
                (zakon.get("nazev_kratky") or zakon.get("nazev", ""), None),
            ),
        )
    )
    return (
        _jinja_env()
        .get_template("zakon-stranka.html")
        .render(z=zakon, zakony_index_href=zakony_pages_href(base_path), **ctx)
    )


def export_zakony_pages(
    obdobi: int,
    *,
    css_href: str | None,
    fonts_css_href: str | None,
    base_path: str,
) -> list[tuple[str, str]]:
    """[(rel_path, html)] pro rozcestník a všechny publikované zákony."""
    pages = [
        (
            "zakony/index.html",
            render_zakony_index_html(
                obdobi, css_href=css_href, fonts_css_href=fonts_css_href, base_path=base_path
            ),
        )
    ]
    for z in list_zakony(base_path):
        pages.append(
            (
                f"zakony/{z['slug']}/index.html",
                render_zakon_html(
                    obdobi,
                    z,
                    css_href=css_href,
                    fonts_css_href=fonts_css_href,
                    base_path=base_path,
                ),
            )
        )
    return pages
