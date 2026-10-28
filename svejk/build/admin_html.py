"""Interní admin přehled vydání.

Vyčleněno z html.py (dřív 2 457 řádků)."""

from __future__ import annotations

from functools import lru_cache

import copy
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, pass_context, select_autoescape
from markupsafe import Markup

from svejk.build.day_content import DenContent, build_den_content, datum_day_month, datum_design
from svejk.build.io import read_json
from svejk.build.seo import SITE_NAME, edition_published_iso, site_meta_description
from svejk.build.steno_sources import steno_sources_href
from svejk.glossary import slovnicek_anchor, slovnicek_display_term, slovnicek_entries, slovnicek_term_label
from svejk.build.publish import list_site_editions
from svejk.strings import footer_closings, footer_stats_line, load_strings, schuze_count_label
from svejk.build.nav import (
    Edition,
    archiv_pages_href,
    archive_by_month,
    archive_text_list,
    build_session_calendar,
    edition_nav,
    edition_pages_href,
    o_webu_pages_href,
    pivo_pages_href,
    dekuju_pages_href,
    podminky_pages_href,
    podpora_pages_href,
    subscribe_pages_href,
    slovnicek_pages_href,
    slovnicek_term_pages_href,
    soukromi_pages_href,
    vyznamenani_pages_href,
    steno_sources_pages_href,
    smlouvy_pages_href,
    recnici_pages_href,
)

# Stripe Payment Links — redirect ve Stripe Dashboardu → /dekuju.html
STRIPE_PIVO_URL = "https://donate.stripe.com/14A7sNekE1pP8cEfb83Je00"
STRIPE_RUM_URL = "https://donate.stripe.com/4gM00l0tO3xX0Kc1ki3Je01"
STRIPE_STAMGAST_URL = "https://donate.stripe.com/5kQ14pa4o8ShfF66EC3Je02"
STRIPE_PORTAL_URL = "https://billing.stripe.com/p/login/14A7sNekE1pP8cEfb83Je00"


def _stripe_url(env_key: str, default: str) -> str:
    return os.environ.get(env_key, default).strip() or default


def pivo_tiers() -> list[dict[str, Any]]:
    """Hospodský ceník — tři položky, pay_href vede na Stripe Payment Links."""
    pt = load_strings().get("pivo_tiers", {})
    monthly_badge = pt.get("monthly_badge", "MĚSÍČNĚ")
    return [
        {
            "id": "velke",
            "kind": "once",
            "name": pt.get("velke_name", "Velké pivo"),
            "price": "65 Kč",
            "note": pt.get("velke_note", "starý osvědčený prostředek proti trudnomyslnosti"),
            "cta": pt.get("velke_cta", "Přispět jednorázově"),
            "pay_href": _stripe_url("STRIPE_PIVO_URL", STRIPE_PIVO_URL),
        },
        {
            "id": "rum",
            "kind": "once",
            "name": pt.get("rum_name", "Rum"),
            "price": "95 Kč",
            "note": pt.get("rum_note", "Kořalku nepiju, jen rum."),
            "cta": pt.get("rum_cta", "Přispět jednorázově"),
            "pay_href": _stripe_url("STRIPE_RUM_URL", STRIPE_RUM_URL),
        },
        {
            "id": "stamgast",
            "kind": "monthly",
            "name": pt.get("stamgast_name", "Štamgast"),
            "price": "65 Kč",
            "price_badge": monthly_badge,
            "note": pt.get("stamgast_note", "pro ty, kdo chodí pravidelně, i když zrovna není poplach"),
            "cta": pt.get("stamgast_cta", "Stát se Štamgastem"),
            "pay_href": _stripe_url("STRIPE_STAMGAST_URL", STRIPE_STAMGAST_URL),
        },
    ]


from svejk.build.vyznamenani_neprosli import (
    VyznamenaniKind,
    inject_mean_links,
    load_vyznamenani,
    page_explain,
    page_meta,
    resolve_vyznamenani_page_links,
    sibling_label,
    table_rows,
    vyznamenani_datum_label,
    vyznamenani_href,
    _load_votes_by_cislo,
)
from svejk.build.steno_sources import (
    apply_steno_links_to_content,
    collect_steno_sources,
    has_steno_sources,
)
from svejk.build.recnici import (
    load_recnici,
    recnici_datum_label,
    recnici_href,
    recnici_page_meta,
    recnici_rows,
    resolve_recnici_page_links,
)
from svejk.newsletter.config import NewsletterConfig
from svejk.paths import SchuzePaths
from svejk.timeline import den_v_tydnu

from svejk.build.html import (  # noqa: F401
    _inline_css_text,
    _jinja_env,
    _site_ctx,
    _site_footer_ctx,
    _site_nav_ctx,
    css_asset_version,
    fonts_asset_version,
    static_admin_css_path,
    static_css_path,
    static_favicon_paths,
    static_fonts_css_path,
)


def _admin_shell_ctx(
    obdobi: int,
    *,
    inline_css: bool = False,
    css_href: str | None = None,
    fonts_css_href: str | None = None,
    base_path: str = "",
) -> dict[str, Any]:
    css = _inline_css_text(admin=True) if inline_css else ""
    css_version = css_asset_version()
    if css_href is None:
        css_href = static_css_path(base_path, version=css_version)
    if fonts_css_href is None:
        fonts_css_href = static_fonts_css_path(base_path, version=fonts_asset_version())
    favicons = static_favicon_paths(base_path)
    cfg = NewsletterConfig.from_env()
    return {
        "inline_css": inline_css,
        "css": css,
        "css_href": css_href,
        "admin_css_href": None if inline_css else static_admin_css_path(base_path, version=css_version),
        "fonts_css_href": fonts_css_href,
        "cookie_privacy_url": soukromi_pages_href(base_path),
        **_site_ctx(site_url=cfg.site_url, base_path=base_path, page_path="/admin"),
        **_site_nav_ctx(obdobi, base_path),
        **_site_footer_ctx(base_path, obdobi=obdobi, closing_seed="admin"),
        **favicons,
    }


def render_admin_html(
    obdobi: int,
    items: list[dict[str, Any]] | None = None,
    **kwargs: Any,
) -> str:
    """Interní seznam zápisů (noindex, mimo export)."""
    tpl = _jinja_env().get_template("admin.html")
    return tpl.render(items=items or [], **_admin_shell_ctx(obdobi, **kwargs))


def render_admin_detail_html(
    obdobi: int,
    *,
    zapisek: dict[str, Any],
    bod: dict[str, Any],
    schuze: dict[str, Any],
    statistiky: dict[str, Any] | None = None,
    **kwargs: Any,
) -> str:
    """Interní náhled jednoho zápisu (noindex, mimo export)."""
    tpl = _jinja_env().get_template("admin_detail.html")
    return tpl.render(
        zapisek=zapisek,
        bod=bod,
        schuze=schuze,
        statistiky=statistiky or {},
        **_admin_shell_ctx(obdobi, **kwargs),
    )
