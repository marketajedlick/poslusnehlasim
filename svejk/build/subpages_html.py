"""Podstránky vydání: steno zdroje, smlouvy, vyznamenání, řečníci, slovníček.

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
    _edition_subpage_breadcrumbs,
    _inline_css_text,
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
    static_satellite_css_path,
)


def render_vyznamenani_table_html(
    paths: SchuzePaths,
    datum_unl: str,
    kind: VyznamenaniKind,
    *,
    inline_css: bool = False,
    css_href: str | None = None,
    fonts_css_href: str | None = None,
    base_path: str = "",
    link_mode: str = "file",
) -> str | None:
    data = load_vyznamenani(paths, datum_unl, kind)
    if not data:
        return None
    css = _inline_css_text(satellite=True) if inline_css else ""
    if css_href is None:
        css_href = static_css_path(base_path, version=css_asset_version())
    if fonts_css_href is None:
        fonts_css_href = static_fonts_css_path(base_path, version=fonts_asset_version())
    favicons = static_favicon_paths(base_path)
    cfg = NewsletterConfig.from_env()
    obdobi = int(data.get("obdobi") or paths.obdobi)
    schuze = int(data.get("schuze") or paths.schuze)
    d = datetime.strptime(datum_unl, "%d.%m.%Y")
    datum_label = vyznamenani_datum_label(datum_unl)
    pocet = int(data.get("pocet") or len(data.get("radky") or []))
    meta = page_meta(kind, pocet=pocet, datum_label=datum_label)
    sibling_kind: VyznamenaniKind | None = (
        "prosli" if kind == "neprosli" else "neprosli" if kind == "prosli" else None
    )
    sibling_data = (
        load_vyznamenani(paths, datum_unl, sibling_kind) if sibling_kind else None
    )
    if link_mode == "pages":
        edition_href = edition_pages_href(obdobi, schuze, datum_unl, base_path)
        canonical_url = f"{cfg.site_url.rstrip('/')}{vyznamenani_pages_href(obdobi, schuze, datum_unl, kind, base_path)}"
        sibling_href = (
            vyznamenani_href(
                obdobi,
                schuze,
                datum_unl,
                sibling_kind,
                link_mode="pages",
                base_path=base_path,
            )
            if sibling_data
            else ""
        )
    else:
        edition_href = f"{d.strftime('%Y-%m-%d')}.html"
        canonical_url = ""
        sibling_href = (
            vyznamenani_href(obdobi, schuze, datum_unl, sibling_kind, link_mode="file")
            if sibling_data
            else ""
        )
    sibling_link_label = (
        sibling_label(sibling_kind) if sibling_kind else ""
    )
    page_description = meta["gloss"]
    og_title = f"{meta['title']} · {datum_label} · {SITE_NAME}"
    og = _og_context(
        site_url=cfg.site_url,
        base_path=base_path,
        title=og_title,
        description=page_description,
    )
    votes_by_cislo = _load_votes_by_cislo(paths, datum_unl)
    explain = page_explain(kind, data, votes_by_cislo)
    page_path = _page_path_from_canonical(canonical_url, cfg.site_url) if canonical_url else ""
    tpl = _jinja_env().get_template("vyznamenani-tabulka-stranka.html")
    return tpl.render(
        rows=table_rows(data, kind=kind, votes_by_cislo=votes_by_cislo),
        kind=kind,
        show_vote_threshold=bool(votes_by_cislo),
        page_explain=explain,
        datum_label=datum_label,
        edition_href=edition_href,
        sibling_href=sibling_href if sibling_data else "",
        sibling_label=sibling_link_label if sibling_data else "",
        page_title=meta["title"],
        page_gloss=meta["gloss"],
        page_note=meta["note"],
        page_description=page_description,
        canonical_url=canonical_url,
        inline_css=inline_css,
        css=css,
        css_href=css_href,
        satellite_css_href=None if inline_css else static_satellite_css_path(base_path, version=css_asset_version()),
        fonts_css_href=fonts_css_href,
        cookie_privacy_url=soukromi_pages_href(base_path),
        **_site_ctx( site_url=cfg.site_url, base_path=base_path, page_path=page_path),
        **_site_nav_ctx(
            paths.obdobi,
            base_path,
            current_schuze=schuze,
            current_datum=datum_unl,
        ),
        **_site_footer_ctx(
            base_path,
            obdobi=paths.obdobi,
            closing_seed=f"vyznamenani/{kind}/{datum_unl}",
        ),
        **favicons,
        ph_fav_href=_ph_fav_href(base_path),
        **og,
        **_edition_subpage_breadcrumbs(
            site_url=cfg.site_url,
            base_path=base_path,
            obdobi=obdobi,
            schuze=schuze,
            datum_unl=datum_unl,
            subpage_label=meta["title"],
        ),
    )


def render_vyznamenani_neprosli_html(
    paths: SchuzePaths,
    datum_unl: str,
    **kwargs: Any,
) -> str | None:
    return render_vyznamenani_table_html(paths, datum_unl, "neprosli", **kwargs)


def render_steno_sources_html(
    paths: SchuzePaths,
    datum_unl: str,
    *,
    inline_css: bool = False,
    css_href: str | None = None,
    fonts_css_href: str | None = None,
    base_path: str = "",
    link_mode: str = "file",
) -> str | None:
    blocks = collect_steno_sources(paths, datum_unl)
    if not blocks:
        return None
    css = _inline_css_text(satellite=True) if inline_css else ""
    if css_href is None:
        css_href = static_css_path(base_path, version=css_asset_version())
    if fonts_css_href is None:
        fonts_css_href = static_fonts_css_path(base_path, version=fonts_asset_version())
    favicons = static_favicon_paths(base_path)
    cfg = NewsletterConfig.from_env()
    obdobi = paths.obdobi
    schuze = paths.schuze
    d = datetime.strptime(datum_unl, "%d.%m.%Y")
    datum_label = datum_design(datum_unl, den_v_tydnu(datum_unl))
    t = load_strings()
    st = t.get("steno_sources", {})
    page_title = st.get("page_title", "Stenoprotokol")
    page_gloss = st.get("page_gloss", "")
    page_explain = st.get("page_explain", "")
    page_description = page_gloss or page_title
    if link_mode == "pages":
        edition_href = edition_pages_href(obdobi, schuze, datum_unl, base_path)
        # Self-referenční canonical — steno je indexovatelné jako vlastní stránka.
        steno_href = steno_sources_pages_href(obdobi, schuze, datum_unl, base_path)
        canonical_url = f"{cfg.site_url.rstrip('/')}{steno_href}"
    else:
        edition_href = f"{d.strftime('%Y-%m-%d')}.html"
        canonical_url = ""
    og_title = f"{page_title} · {datum_label} · {SITE_NAME}"
    og = _og_context(
        site_url=cfg.site_url,
        base_path=base_path,
        title=og_title,
        description=page_description,
    )
    page_path = _page_path_from_canonical(canonical_url, cfg.site_url) if canonical_url else ""
    tpl = _jinja_env().get_template("steno-zdroje-stranka.html")
    return tpl.render(
        blocks=blocks,
        datum_label=datum_label,
        edition_href=edition_href,
        page_title=page_title,
        page_gloss=page_gloss,
        page_explain=page_explain,
        page_description=page_description,
        canonical_url=canonical_url,
        inline_css=inline_css,
        css=css,
        css_href=css_href,
        satellite_css_href=None if inline_css else static_satellite_css_path(base_path, version=css_asset_version()),
        fonts_css_href=fonts_css_href,
        cookie_privacy_url=soukromi_pages_href(base_path),
        **_site_ctx( site_url=cfg.site_url, base_path=base_path, page_path=page_path),
        **_site_nav_ctx(
            obdobi,
            base_path,
            current_schuze=schuze,
            current_datum=datum_unl,
        ),
        **_site_footer_ctx(
            base_path,
            obdobi=obdobi,
            closing_seed=f"steno/{datum_unl}",
        ),
        **favicons,
        ph_fav_href=_ph_fav_href(base_path),
        **og,
        **_edition_subpage_breadcrumbs(
            site_url=cfg.site_url,
            base_path=base_path,
            obdobi=obdobi,
            schuze=schuze,
            datum_unl=datum_unl,
            subpage_label=page_title,
            edition_href=edition_href,
        ),
    )


def render_smlouvy_html(
    paths: SchuzePaths,
    datum_unl: str,
    *,
    inline_css: bool = False,
    css_href: str | None = None,
    fonts_css_href: str | None = None,
    base_path: str = "",
    link_mode: str = "file",
) -> str | None:
    from svejk.build.mezin_smlouvy import has_smlouvy, smlouvy_page_items

    if not has_smlouvy(paths, datum_unl):
        return None
    items = smlouvy_page_items(
        paths,
        datum_unl,
        obdobi=paths.obdobi,
        link_mode=link_mode,
        base_path=base_path,
    )
    if not items:
        return None
    css = _inline_css_text(satellite=True) if inline_css else ""
    if css_href is None:
        css_href = static_css_path(base_path, version=css_asset_version())
    if fonts_css_href is None:
        fonts_css_href = static_fonts_css_path(base_path, version=fonts_asset_version())
    favicons = static_favicon_paths(base_path)
    cfg = NewsletterConfig.from_env()
    obdobi = paths.obdobi
    schuze = paths.schuze
    datum_label = datum_design(datum_unl, den_v_tydnu(datum_unl))
    t = load_strings()
    sp = t.get("smlouvy_page", {})
    page_title = sp.get("page_title", "Mezinárodní smlouvy")
    page_gloss = sp.get("page_gloss", "")
    page_description = page_gloss or page_title
    steno_page_href = steno_sources_pages_href(obdobi, schuze, datum_unl, base_path)
    if link_mode == "pages":
        edition_href = edition_pages_href(obdobi, schuze, datum_unl, base_path)
        canonical_url = f"{cfg.site_url.rstrip('/')}{smlouvy_pages_href(obdobi, schuze, datum_unl, base_path)}"
    else:
        d = datetime.strptime(datum_unl, "%d.%m.%Y")
        edition_href = f"{d.strftime('%Y-%m-%d')}.html"
        canonical_url = ""
    og_title = f"{page_title} · {datum_label} · {SITE_NAME}"
    og = _og_context(
        site_url=cfg.site_url,
        base_path=base_path,
        title=og_title,
        description=page_description,
    )
    page_path = _page_path_from_canonical(canonical_url, cfg.site_url) if canonical_url else ""
    tpl = _jinja_env().get_template("smlouvy-stranka.html")
    return tpl.render(
        items=items,
        datum_label=datum_label,
        edition_href=edition_href,
        steno_page_href=steno_page_href,
        page_title=page_title,
        page_gloss=page_gloss,
        page_description=page_description,
        steno_link_label=sp.get("steno_link", "Stenoprotokol →"),
        psp_link_label=sp.get("psp_link", "Přesný záznam na webu Sněmovny →"),
        canonical_url=canonical_url,
        inline_css=inline_css,
        css=css,
        css_href=css_href,
        satellite_css_href=None if inline_css else static_satellite_css_path(base_path, version=css_asset_version()),
        fonts_css_href=fonts_css_href,
        cookie_privacy_url=soukromi_pages_href(base_path),
        **_site_ctx(site_url=cfg.site_url, base_path=base_path, page_path=page_path),
        **_site_nav_ctx(
            obdobi,
            base_path,
            current_schuze=schuze,
            current_datum=datum_unl,
        ),
        **_site_footer_ctx(
            base_path,
            obdobi=obdobi,
            closing_seed=f"smlouvy/{datum_unl}",
        ),
        **favicons,
        ph_fav_href=_ph_fav_href(base_path),
        **og,
        **_edition_subpage_breadcrumbs(
            site_url=cfg.site_url,
            base_path=base_path,
            obdobi=obdobi,
            schuze=schuze,
            datum_unl=datum_unl,
            subpage_label=page_title,
        ),
    )


def render_recnici_table_html(
    paths: SchuzePaths,
    datum_unl: str,
    *,
    inline_css: bool = False,
    css_href: str | None = None,
    fonts_css_href: str | None = None,
    base_path: str = "",
    link_mode: str = "file",
) -> str | None:
    data = load_recnici(paths, datum_unl)
    if not data or not data.get("radky"):
        return None
    css = _inline_css_text(satellite=True) if inline_css else ""
    if css_href is None:
        css_href = static_css_path(base_path, version=css_asset_version())
    if fonts_css_href is None:
        fonts_css_href = static_fonts_css_path(base_path, version=fonts_asset_version())
    favicons = static_favicon_paths(base_path)
    cfg = NewsletterConfig.from_env()
    obdobi = int(data.get("obdobi") or paths.obdobi)
    schuze = int(data.get("schuze") or paths.schuze)
    d = datetime.strptime(datum_unl, "%d.%m.%Y")
    datum_label = recnici_datum_label(datum_unl)
    meta = recnici_page_meta(data, datum_label=datum_label)
    if link_mode == "pages":
        edition_href = edition_pages_href(obdobi, schuze, datum_unl, base_path)
        canonical_url = f"{cfg.site_url.rstrip('/')}{recnici_pages_href(obdobi, schuze, datum_unl, base_path)}"
    else:
        edition_href = f"{d.strftime('%Y-%m-%d')}.html"
        canonical_url = ""
    page_description = meta["gloss"]
    og_title = f"{meta['title']} · {datum_label} · {SITE_NAME}"
    og = _og_context(
        site_url=cfg.site_url,
        base_path=base_path,
        title=og_title,
        description=page_description,
    )
    page_path = _page_path_from_canonical(canonical_url, cfg.site_url) if canonical_url else ""
    tpl = _jinja_env().get_template("recnici-tabulka-stranka.html")
    return tpl.render(
        rows=recnici_rows(data),
        datum_label=datum_label,
        edition_href=edition_href,
        back_to_edition=meta["back_to_edition"].format(date=datum_label),
        page_title=meta["title"],
        page_gloss=meta["gloss"],
        page_note=meta["note"],
        table_speaker=meta["table_speaker"],
        table_words=meta["table_words"],
        table_role=meta["table_role"],
        page_description=page_description,
        canonical_url=canonical_url,
        inline_css=inline_css,
        css=css,
        css_href=css_href,
        satellite_css_href=None if inline_css else static_satellite_css_path(base_path, version=css_asset_version()),
        fonts_css_href=fonts_css_href,
        cookie_privacy_url=soukromi_pages_href(base_path),
        **_site_ctx( site_url=cfg.site_url, base_path=base_path, page_path=page_path),
        **_site_nav_ctx(
            obdobi,
            base_path,
            current_schuze=schuze,
            current_datum=datum_unl,
        ),
        **_site_footer_ctx(
            base_path,
            obdobi=obdobi,
            closing_seed=f"recnici/{datum_unl}",
        ),
        **favicons,
        ph_fav_href=_ph_fav_href(base_path),
        **og,
        **_edition_subpage_breadcrumbs(
            site_url=cfg.site_url,
            base_path=base_path,
            obdobi=obdobi,
            schuze=schuze,
            datum_unl=datum_unl,
            subpage_label=meta["title"],
        ),
    )


def render_slovnicek_html(
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
    canonical_url = f"{cfg.site_url.rstrip('/')}{slovnicek_pages_href(base_path)}"
    page_path = _page_path_from_canonical(canonical_url, cfg.site_url)
    gp = load_strings()["glossary_page"]
    entries = list(slovnicek_entries())
    og = _og_context(
        site_url=cfg.site_url,
        base_path=base_path,
        title=gp["title"],
        description=site_meta_description(),
    )
    from svejk.build.seo import breadcrumbs_ctx_slovnicek
    from svejk.build.seo import faq_json_ld as _faq_json_ld

    faq_ld = _faq_json_ld(url=canonical_url, entries=entries)
    tpl = _jinja_env().get_template("slovnicek-stranka.html")
    slovnicek = [
        {
            "term": slovnicek_term_label(slovnicek_display_term(q)),
            "answer": a,
            "anchor": slovnicek_anchor(q),
            "href": slovnicek_term_pages_href(slovnicek_anchor(q), base_path),
        }
        for q, a in entries
    ]
    return tpl.render(
        slovnicek=slovnicek,
        slovnicek_index_href=slovnicek_pages_href(base_path),
        canonical_url=canonical_url,
        faq_json_ld=faq_ld,
        **og,
        inline_css=inline_css,
        css=css,
        css_href=css_href,
        fonts_css_href=fonts_css_href,
        cookie_privacy_url=soukromi_pages_href(base_path),
        **_site_ctx( site_url=cfg.site_url, base_path=base_path, page_path=page_path),
        **_site_nav_ctx(obdobi, base_path),
        **_site_footer_ctx(base_path, obdobi=obdobi, closing_seed="slovnicek"),
        **favicons,
        ph_fav_href=_ph_fav_href(base_path),
        **breadcrumbs_ctx_slovnicek(site_url=cfg.site_url, base_path=base_path),
    )


def render_slovnicek_term_html(
    obdobi: int,
    *,
    term: str,
    answer: str,
    slug: str,
    mentions: tuple[Any, ...] = (),
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
    term_label = slovnicek_term_label(slovnicek_display_term(term))
    term_href = slovnicek_term_pages_href(slug, base_path)
    glossary_href = slovnicek_pages_href(base_path)
    canonical_url = f"{cfg.site_url.rstrip('/')}{term_href}"
    page_path = _page_path_from_canonical(canonical_url, cfg.site_url)
    gt = load_strings()["glossary_term"]
    from svejk.build.seo import (
        breadcrumbs_ctx_slovnicek_term,
        slovnicek_term_json_ld,
        slovnicek_term_page_title,
    )

    title = slovnicek_term_page_title(term_label)
    description = answer
    og = _og_context(
        site_url=cfg.site_url,
        base_path=base_path,
        title=title,
        description=description,
    )
    schema_ld = slovnicek_term_json_ld(
        url=canonical_url,
        term=term_label,
        answer=answer,
        glossary_url=f"{cfg.site_url.rstrip('/')}{glossary_href}",
    )
    tpl = _jinja_env().get_template("slovnicek-pojem.html")
    return tpl.render(
        term=term_label,
        answer=answer,
        mentions=mentions,
        canonical_url=canonical_url,
        schema_json_ld=schema_ld,
        slovnicek_index_href=glossary_href,
        title=title,
        **og,
        inline_css=inline_css,
        css=css,
        css_href=css_href,
        fonts_css_href=fonts_css_href,
        cookie_privacy_url=soukromi_pages_href(base_path),
        **_site_ctx(site_url=cfg.site_url, base_path=base_path, page_path=page_path),
        **_site_nav_ctx(obdobi, base_path),
        **_site_footer_ctx(base_path, obdobi=obdobi, closing_seed=f"slovnicek/{slug}"),
        **favicons,
        ph_fav_href=_ph_fav_href(base_path),
        **breadcrumbs_ctx_slovnicek_term(
            site_url=cfg.site_url,
            base_path=base_path,
            term_label=term_label,
        ),
    )
