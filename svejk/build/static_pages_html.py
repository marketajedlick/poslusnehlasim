"""Statické stránky webu: archiv, 404, o webu, podpora, pivo, odběr, soukromí…

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
    STRIPE_PORTAL_URL,
    _inline_css_text,
    _jinja_env,
    _og_context,
    _page_path_from_canonical,
    _ph_fav_href,
    _site_ctx,
    _site_footer_ctx,
    _site_nav_ctx,
    _stripe_url,
    css_asset_version,
    fonts_asset_version,
    pivo_tiers,
    render_den_html,
    static_css_path,
    static_favicon_paths,
    static_fonts_css_path,
)
from svejk.build.admin_html import _admin_shell_ctx  # noqa: F401


def render_archiv_html(
    obdobi: int,
    *,
    inline_css: bool = False,
    css_href: str | None = None,
    fonts_css_href: str | None = None,
    base_path: str = "",
) -> str:
    css = _inline_css_text() if inline_css else ""
    if css_href is None:
        css_href = static_css_path(base_path, version=css_asset_version())
    if fonts_css_href is None:
        fonts_css_href = static_fonts_css_path(base_path, version=fonts_asset_version())
    favicons = static_favicon_paths(base_path)
    cfg = NewsletterConfig.from_env()
    editions = list_site_editions(obdobi)
    if not editions:
        raise ValueError(f"Žádná vydání pro období {obdobi}")

    latest = editions[-1]
    paths = SchuzePaths.create(latest.obdobi, latest.schuze)
    months = archive_by_month(
        paths,
        latest.datum_unl,
        link_mode="pages",
        obdobi=obdobi,
        base_path=base_path,
    )
    text_entries = archive_text_list(
        obdobi,
        link_mode="pages",
        base_path=base_path,
    )
    canonical_url = f"{cfg.site_url.rstrip('/')}{archiv_pages_href(base_path)}"
    page_path = _page_path_from_canonical(canonical_url, cfg.site_url)
    t = load_strings()
    og = _og_context(
        site_url=cfg.site_url,
        base_path=base_path,
        title=t["archive"]["title"] + f" · {SITE_NAME}",
        description=site_meta_description(),
    )
    tpl = _jinja_env().get_template("archiv.html")
    from svejk.build.seo import breadcrumbs_ctx_archiv

    return tpl.render(
        obdobi=obdobi,
        archive_months=months,
        archive_text_entries=text_entries,
        canonical_url=canonical_url,
        **og,
        inline_css=inline_css,
        css=css,
        css_href=css_href,
        fonts_css_href=fonts_css_href,
        cookie_privacy_url=soukromi_pages_href(base_path),
        **_site_ctx( site_url=cfg.site_url, base_path=base_path, page_path=page_path),
        **_site_nav_ctx(obdobi, base_path),
        **_site_footer_ctx(base_path, obdobi=obdobi, closing_seed="archiv"),
        **favicons,
        ph_fav_href=_ph_fav_href(base_path),
        **breadcrumbs_ctx_archiv(site_url=cfg.site_url, base_path=base_path),
    )


def render_404_html(
    obdobi: int,
    *,
    inline_css: bool = False,
    css_href: str | None = None,
    fonts_css_href: str | None = None,
    base_path: str = "",
) -> str:
    """Vlastní 404 stránka pro GitHub Pages."""
    css = _inline_css_text() if inline_css else ""
    if css_href is None:
        css_href = static_css_path(base_path, version=css_asset_version())
    if fonts_css_href is None:
        fonts_css_href = static_fonts_css_path(base_path, version=fonts_asset_version())
    favicons = static_favicon_paths(base_path)
    cfg = NewsletterConfig.from_env()
    editions = list_site_editions(obdobi)
    if not editions:
        raise ValueError(f"Žádná vydání pro období {obdobi}")

    latest = editions[-1]
    from svejk.timeline import den_v_tydnu
    latest_label = datum_design(
        latest.datum_unl, den_v_tydnu(latest.datum_unl)
    )
    base = base_path.rstrip("/")
    home = "/"
    home = f"{base}{home}" if base else home
    canonical_url = f"{cfg.site_url.rstrip('/')}{home}"
    page_path = _page_path_from_canonical(canonical_url, cfg.site_url)
    from svejk.build.seo import breadcrumbs_ctx_static

    tpl = _jinja_env().get_template("404-stranka.html")
    return tpl.render(
        latest_label=latest_label,
        newsletter=cfg,
        canonical_url=canonical_url,
        inline_css=inline_css,
        css=css,
        css_href=css_href,
        fonts_css_href=fonts_css_href,
        cookie_privacy_url=soukromi_pages_href(base_path),
        **_site_ctx( site_url=cfg.site_url, base_path=base_path, page_path=page_path),
        **_site_nav_ctx(obdobi, base_path),
        **_site_footer_ctx(base_path, obdobi=obdobi, closing_seed="404"),
        **favicons,
        ph_fav_href=_ph_fav_href(base_path),
        **breadcrumbs_ctx_static(
            site_url=cfg.site_url,
            base_path=base_path,
            label="Stránka nenalezena",
        ),
    )


def render_potvrzeno_html(
    obdobi: int,
    *,
    inline_css: bool = False,
    css_href: str | None = None,
    fonts_css_href: str | None = None,
    base_path: str = "",
) -> str:
    """Stránka po potvrzení double opt-in (přesměrování z Ecomailu)."""
    css = _inline_css_text() if inline_css else ""
    if css_href is None:
        css_href = static_css_path(base_path, version=css_asset_version())
    if fonts_css_href is None:
        fonts_css_href = static_fonts_css_path(base_path, version=fonts_asset_version())
    favicons = static_favicon_paths(base_path)
    cfg = NewsletterConfig.from_env()
    editions = list_site_editions(obdobi)
    if not editions:
        raise ValueError(f"Žádná vydání pro období {obdobi}")

    latest = editions[-1]
    potvrzeno_path = "/potvrzeno/"
    canonical_url = f"{cfg.site_url.rstrip('/')}{potvrzeno_path}"
    page_path = _page_path_from_canonical(canonical_url, cfg.site_url)
    from svejk.timeline import den_v_tydnu

    latest_label = datum_design(
        latest.datum_unl, den_v_tydnu(latest.datum_unl)
    )
    tpl = _jinja_env().get_template("potvrzeno.html")
    from svejk.build.seo import breadcrumbs_ctx_static

    cp = load_strings()["confirmed_page"]
    return tpl.render(
        latest_label=latest_label,
        site_url=cfg.site_url.rstrip("/"),
        privacy_url=cfg.privacy_url,
        contact_email=cfg.contact_email,
        canonical_url=canonical_url,
        inline_css=inline_css,
        css=css,
        css_href=css_href,
        fonts_css_href=fonts_css_href,
        cookie_privacy_url=soukromi_pages_href(base_path),
        **_site_ctx( site_url=cfg.site_url, base_path=base_path, page_path=page_path),
        **_site_nav_ctx(obdobi, base_path),
        **_site_footer_ctx(base_path, obdobi=obdobi, closing_seed="potvrzeno"),
        **favicons,
        ph_fav_href=_ph_fav_href(base_path),
        **breadcrumbs_ctx_static(
            site_url=cfg.site_url,
            base_path=base_path,
            label=cp["heading"],
        ),
    )


def render_pivo_html(
    obdobi: int,
    *,
    inline_css: bool = False,
    css_href: str | None = None,
    fonts_css_href: str | None = None,
    base_path: str = "",
) -> str:
    css = _inline_css_text() if inline_css else ""
    if css_href is None:
        css_href = static_css_path(base_path, version=css_asset_version())
    if fonts_css_href is None:
        fonts_css_href = static_fonts_css_path(base_path, version=fonts_asset_version())
    favicons = static_favicon_paths(base_path)
    cfg = NewsletterConfig.from_env()
    editions = list_site_editions(obdobi)
    if not editions:
        raise ValueError(f"Žádná vydání pro období {obdobi}")
    canonical_url = f"{cfg.site_url.rstrip('/')}{pivo_pages_href(base_path)}"
    page_path = _page_path_from_canonical(canonical_url, cfg.site_url)
    bp = load_strings()["beer_page"]
    og = _og_context(
        site_url=cfg.site_url,
        base_path=base_path,
        title=bp["title"],
        description=site_meta_description(),
    )
    tpl = _jinja_env().get_template("pivo-stranka.html")
    from svejk.build.seo import breadcrumbs_ctx_static

    return tpl.render(
        canonical_url=canonical_url,
        **og,
        pivo_tiers=pivo_tiers(),
        pivo_menu_pay=True,
        stripe_portal_href=_stripe_url("STRIPE_PORTAL_URL", STRIPE_PORTAL_URL),
        inline_css=inline_css,
        css=css,
        css_href=css_href,
        fonts_css_href=fonts_css_href,
        cookie_privacy_url=soukromi_pages_href(base_path),
        **_site_ctx( site_url=cfg.site_url, base_path=base_path, page_path=page_path),
        **_site_nav_ctx(obdobi, base_path),
        **_site_footer_ctx(base_path, obdobi=obdobi, closing_seed="pivo"),
        **favicons,
        ph_fav_href=_ph_fav_href(base_path),
        **breadcrumbs_ctx_static(
            site_url=cfg.site_url,
            base_path=base_path,
            label=bp["heading"],
        ),
    )


def render_dekuju_html(
    obdobi: int,
    *,
    inline_css: bool = False,
    css_href: str | None = None,
    fonts_css_href: str | None = None,
    base_path: str = "",
) -> str:
    """Stránka po úspěšné platbě (redirect ze Stripe)."""
    css = _inline_css_text() if inline_css else ""
    if css_href is None:
        css_href = static_css_path(base_path, version=css_asset_version())
    if fonts_css_href is None:
        fonts_css_href = static_fonts_css_path(base_path, version=fonts_asset_version())
    favicons = static_favicon_paths(base_path)
    cfg = NewsletterConfig.from_env()
    editions = list_site_editions(obdobi)
    if not editions:
        raise ValueError(f"Žádná vydání pro období {obdobi}")
    canonical_url = f"{cfg.site_url.rstrip('/')}{dekuju_pages_href(base_path)}"
    page_path = _page_path_from_canonical(canonical_url, cfg.site_url)
    tpl = _jinja_env().get_template("dekuju-stranka.html")
    return tpl.render(
        canonical_url=canonical_url,
        inline_css=inline_css,
        css=css,
        css_href=css_href,
        fonts_css_href=fonts_css_href,
        cookie_privacy_url=soukromi_pages_href(base_path),
        **_site_ctx( site_url=cfg.site_url, base_path=base_path, page_path=page_path),
        **_site_nav_ctx(obdobi, base_path),
        **_site_footer_ctx(base_path, obdobi=obdobi, closing_seed="dekuju"),
        **favicons,
        ph_fav_href=_ph_fav_href(base_path),
    )


def render_soukromi_html(
    obdobi: int,
    *,
    inline_css: bool = False,
    css_href: str | None = None,
    fonts_css_href: str | None = None,
    base_path: str = "",
) -> str:
    """Zásady ochrany osobních údajů (odběr, analytika, platby)."""
    css = _inline_css_text() if inline_css else ""
    if css_href is None:
        css_href = static_css_path(base_path, version=css_asset_version())
    if fonts_css_href is None:
        fonts_css_href = static_fonts_css_path(base_path, version=fonts_asset_version())
    favicons = static_favicon_paths(base_path)
    cfg = NewsletterConfig.from_env()
    canonical_url = f"{cfg.site_url.rstrip('/')}{soukromi_pages_href(base_path)}"
    page_path = _page_path_from_canonical(canonical_url, cfg.site_url)
    pp = load_strings()["privacy_page"]
    og = _og_context(
        site_url=cfg.site_url,
        base_path=base_path,
        title=pp["title"],
        description=site_meta_description(),
    )
    tpl = _jinja_env().get_template("soukromi.html")
    from svejk.build.seo import breadcrumbs_ctx_static

    return tpl.render(
        site_url=cfg.site_url.rstrip("/"),
        contact_email=cfg.contact_email,
        canonical_url=canonical_url,
        **og,
        inline_css=inline_css,
        css=css,
        css_href=css_href,
        fonts_css_href=fonts_css_href,
        cookie_privacy_url=soukromi_pages_href(base_path),
        **_site_ctx( site_url=cfg.site_url, base_path=base_path, page_path=page_path),
        **_site_nav_ctx(obdobi, base_path),
        **_site_footer_ctx(
            base_path,
            obdobi=obdobi,
            active_page="privacy",
            closing_seed="soukromi",
        ),
        **favicons,
        ph_fav_href=_ph_fav_href(base_path),
        **breadcrumbs_ctx_static(
            site_url=cfg.site_url,
            base_path=base_path,
            label="Ochrana údajů",
        ),
    )


def render_podminky_html(
    obdobi: int,
    *,
    inline_css: bool = False,
    css_href: str | None = None,
    fonts_css_href: str | None = None,
    base_path: str = "",
) -> str:
    """Podmínky používání webu, odběru a dobrovolných příspěvků."""
    css = _inline_css_text() if inline_css else ""
    if css_href is None:
        css_href = static_css_path(base_path, version=css_asset_version())
    if fonts_css_href is None:
        fonts_css_href = static_fonts_css_path(base_path, version=fonts_asset_version())
    favicons = static_favicon_paths(base_path)
    cfg = NewsletterConfig.from_env()
    canonical_url = f"{cfg.site_url.rstrip('/')}{podminky_pages_href(base_path)}"
    page_path = _page_path_from_canonical(canonical_url, cfg.site_url)
    tp = load_strings()["terms_page"]
    og = _og_context(
        site_url=cfg.site_url,
        base_path=base_path,
        title=tp["title"],
        description=site_meta_description(),
    )
    tpl = _jinja_env().get_template("podminky-stranka.html")
    from svejk.build.seo import breadcrumbs_ctx_static

    return tpl.render(
        site_url=cfg.site_url.rstrip("/"),
        contact_email=cfg.contact_email,
        canonical_url=canonical_url,
        **og,
        inline_css=inline_css,
        css=css,
        css_href=css_href,
        fonts_css_href=fonts_css_href,
        cookie_privacy_url=soukromi_pages_href(base_path),
        **_site_ctx( site_url=cfg.site_url, base_path=base_path, page_path=page_path),
        **_site_nav_ctx(obdobi, base_path),
        **_site_footer_ctx(
            base_path,
            obdobi=obdobi,
            active_page="terms",
            closing_seed="podminky",
        ),
        **favicons,
        ph_fav_href=_ph_fav_href(base_path),
        **breadcrumbs_ctx_static(
            site_url=cfg.site_url,
            base_path=base_path,
            label="Podmínky používání",
        ),
    )


def render_podpora_html(
    obdobi: int,
    *,
    inline_css: bool = False,
    css_href: str | None = None,
    fonts_css_href: str | None = None,
    base_path: str = "",
) -> str:
    """Zákaznická podpora — kontakt, platby, odběr."""
    css = _inline_css_text() if inline_css else ""
    if css_href is None:
        css_href = static_css_path(base_path, version=css_asset_version())
    if fonts_css_href is None:
        fonts_css_href = static_fonts_css_path(base_path, version=fonts_asset_version())
    favicons = static_favicon_paths(base_path)
    cfg = NewsletterConfig.from_env()
    canonical_url = f"{cfg.site_url.rstrip('/')}{podpora_pages_href(base_path)}"
    page_path = _page_path_from_canonical(canonical_url, cfg.site_url)
    sp = load_strings()["support_page"]
    og = _og_context(
        site_url=cfg.site_url,
        base_path=base_path,
        title=sp["title"],
        description=site_meta_description(),
    )
    tpl = _jinja_env().get_template("podpora-stranka.html")
    from svejk.build.seo import breadcrumbs_ctx_static

    return tpl.render(
        site_url=cfg.site_url.rstrip("/"),
        contact_email=cfg.contact_email,
        canonical_url=canonical_url,
        **og,
        inline_css=inline_css,
        css=css,
        css_href=css_href,
        fonts_css_href=fonts_css_href,
        cookie_privacy_url=soukromi_pages_href(base_path),
        **_site_ctx( site_url=cfg.site_url, base_path=base_path, page_path=page_path),
        **_site_nav_ctx(obdobi, base_path),
        **_site_footer_ctx(
            base_path,
            obdobi=obdobi,
            active_page="support",
            closing_seed="podpora",
        ),
        **favicons,
        ph_fav_href=_ph_fav_href(base_path),
        **breadcrumbs_ctx_static(
            site_url=cfg.site_url,
            base_path=base_path,
            label="Zákaznická podpora",
        ),
    )


def render_subscribe_html(
    obdobi: int,
    *,
    inline_css: bool = False,
    css_href: str | None = None,
    fonts_css_href: str | None = None,
    base_path: str = "",
) -> str:
    """Samostatná stránka pro odběr novinek (bez odkazu z webu)."""
    from dataclasses import replace

    css = _inline_css_text() if inline_css else ""
    if css_href is None:
        css_href = static_css_path(base_path, version=css_asset_version())
    if fonts_css_href is None:
        fonts_css_href = static_fonts_css_path(base_path, version=fonts_asset_version())
    favicons = static_favicon_paths(base_path)
    cfg = NewsletterConfig.from_env()
    newsletter = replace(cfg, show_subscribe=True) if cfg.enabled else cfg
    canonical_url = f"{cfg.site_url.rstrip('/')}{subscribe_pages_href(base_path)}"
    page_path = _page_path_from_canonical(canonical_url, cfg.site_url)
    sp = load_strings()["subscribe_page"]
    og = _og_context(
        site_url=cfg.site_url,
        base_path=base_path,
        title=sp["title"],
        description=sp["meta"],
    )
    tpl = _jinja_env().get_template("subscribe-stranka.html")
    return tpl.render(
        newsletter=newsletter,
        canonical_url=canonical_url,
        **og,
        inline_css=inline_css,
        css=css,
        css_href=css_href,
        fonts_css_href=fonts_css_href,
        cookie_privacy_url=soukromi_pages_href(base_path),
        **_site_ctx(site_url=cfg.site_url, base_path=base_path, page_path=page_path),
        **_site_nav_ctx(obdobi, base_path),
        **_site_footer_ctx(base_path, obdobi=obdobi, closing_seed="subscribe"),
        **favicons,
        ph_fav_href=_ph_fav_href(base_path),
    )


def render_o_webu_html(
    obdobi: int,
    *,
    inline_css: bool = False,
    css_href: str | None = None,
    fonts_css_href: str | None = None,
    base_path: str = "",
) -> str:
    """O webu — E-E-A-T stránka pro vyhledávače a nové čtenáře."""
    css = _inline_css_text() if inline_css else ""
    if css_href is None:
        css_href = static_css_path(base_path, version=css_asset_version())
    if fonts_css_href is None:
        fonts_css_href = static_fonts_css_path(base_path, version=fonts_asset_version())
    favicons = static_favicon_paths(base_path)
    cfg = NewsletterConfig.from_env()
    editions = list_site_editions(obdobi)
    if not editions:
        raise ValueError(f"Žádná vydání pro období {obdobi}")
    canonical_url = f"{cfg.site_url.rstrip('/')}{o_webu_pages_href(base_path)}"
    page_path = _page_path_from_canonical(canonical_url, cfg.site_url)
    ap = load_strings()["about_page"]
    about_meta = ap.get("meta") or site_meta_description()
    from svejk.build.seo import publisher_logo_url as _publisher_logo_url
    from svejk.build.seo import website_json_ld as _website_json_ld

    og = _og_context(
        site_url=cfg.site_url,
        base_path=base_path,
        title=ap["title"],
        description=about_meta,
    )
    nav_ctx = _site_nav_ctx(obdobi, base_path)
    tpl = _jinja_env().get_template("o-webu-stranka.html")
    from svejk.build.seo import breadcrumbs_ctx_static

    return tpl.render(
        site_url=cfg.site_url.rstrip("/"),
        contact_email=cfg.contact_email,
        canonical_url=canonical_url,
        about_meta=about_meta,
        website_json_ld=_website_json_ld(
            site_url=cfg.site_url,
            logo_url=_publisher_logo_url(cfg.site_url, base_path),
            base_path=base_path,
        ),
        **og,
        inline_css=inline_css,
        css=css,
        css_href=css_href,
        fonts_css_href=fonts_css_href,
        cookie_privacy_url=soukromi_pages_href(base_path),
        **_site_ctx(site_url=cfg.site_url, base_path=base_path, page_path=page_path),
        **nav_ctx,
        **_site_footer_ctx(
            base_path,
            obdobi=obdobi,
            active_page="about",
            closing_seed="o-webu",
        ),
        **favicons,
        ph_fav_href=_ph_fav_href(base_path),
        **breadcrumbs_ctx_static(
            site_url=cfg.site_url,
            base_path=base_path,
            label=ap["heading"],
        ),
    )


def render_index_legacy_html(
    obdobi: int,
    *,
    zapisek: dict[str, Any] | None = None,
    bod: dict[str, Any] | None = None,
    schuze: dict[str, Any] | None = None,
    statistiky: dict[str, Any] | None = None,
    **kwargs: Any,
) -> str:
    """Starý MVP náhled zápisu (noindex). Export webu používá render_den_html."""
    ctx = _admin_shell_ctx(obdobi, **kwargs)
    tpl = _jinja_env().get_template("index.html")
    return tpl.render(
        zapisek=zapisek,
        bod=bod or {},
        schuze=schuze or {},
        statistiky=statistiky or {},
        **ctx,
    )
