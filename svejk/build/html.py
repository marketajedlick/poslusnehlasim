"""HTML výstup novin-dlouhe (design varianta C)."""

from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, pass_context, select_autoescape
from markupsafe import Markup

from svejk.build.day_content import DenContent, build_den_content, datum_day_month, datum_design
from svejk.build.io import read_json
from svejk.build.seo import SITE_NAME, site_meta_description
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
from svejk.build.steno_sources import apply_steno_links_to_content, collect_steno_sources
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

_TEMPLATES = Path(__file__).resolve().parent.parent / "templates"
_STATIC = Path(__file__).resolve().parent.parent / "static"
_CSS = _STATIC / "noviny-dlouhe.css"
_SATELLITE_CSS = _STATIC / "satellite.css"
_ADMIN_CSS = _STATIC / "admin.css"
_FONTS_CSS = _STATIC / "fonts.css"
_EMAIL_CSS = _STATIC / "noviny-email.css"
_DOI_EMAIL_CSS = _STATIC / "doi-email.css"
_SVEJK_SVG = _STATIC / "svejk.svg"
_PH_FAV = _STATIC / "ph-fav.svg"
_FAVICON_PNG = _STATIC / "ph-fav.png"
_OG_SHARE = _STATIC / "og-share.png"
_OG_SHARE_SIZE = (1200, 630)
_FALLBACK_OG_SIZE = (200, 280)


def static_css_path(base_path: str = "", *, version: str | None = None) -> str:
    base = base_path.rstrip("/")
    path = "/static/noviny-dlouhe.css"
    if version:
        path = f"{path}?v={version}"
    return f"{base}{path}" if base else path


def static_satellite_css_path(base_path: str = "", *, version: str | None = None) -> str:
    base = base_path.rstrip("/")
    path = "/static/satellite.css"
    if version:
        path = f"{path}?v={version}"
    return f"{base}{path}" if base else path


def static_admin_css_path(base_path: str = "", *, version: str | None = None) -> str:
    base = base_path.rstrip("/")
    path = "/static/admin.css"
    if version:
        path = f"{path}?v={version}"
    return f"{base}{path}" if base else path


def static_fonts_css_path(base_path: str = "", *, version: str | None = None) -> str:
    base = base_path.rstrip("/")
    path = "/static/fonts.css"
    if version:
        path = f"{path}?v={version}"
    return f"{base}{path}" if base else path


def static_favicon_paths(base_path: str = "") -> dict[str, str]:
    base = base_path.rstrip("/")
    prefix = f"{base}/static" if base else "/static"
    return {
        "favicon_png": f"{prefix}/favicon.png",
        "apple_touch_icon": f"{prefix}/apple-touch-icon.png",
    }


def _edition_postreh(content: DenContent) -> tuple[dict[str, str] | None, int | None]:
    """Nejdelší kuriozita s lead_tail → Švejkův postřeh karta."""
    best_num: int | None = None
    best_len = 0
    for item in content.items:
        k = (item.kuriozita or "").strip()
        if not k or not (item.lead_tail or "").strip():
            continue
        if len(k) > best_len:
            best_len = len(k)
            best_num = item.num
    if best_num is None:
        return None, None
    item = next(i for i in content.items if i.num == best_num)
    return (
        {
            "text": item.kuriozita,
            "pointa": item.pointa or "",
            "title": item.nadpis,
        },
        best_num,
    )


def _edition_slovnicek(
    content: DenContent,
    *,
    base_path: str = "",
) -> list[tuple[str, str, str | None]]:
    from svejk.build.glossary_markup import slovnicek_dne

    chunks: list[str] = [
        content.zaver or "",
        content.zaver_body or "",
        content.dnesni_ucet or "",
        content.result_note or "",
    ]
    for item in content.items:
        chunks.extend(
            [
                item.nadpis,
                item.lead,
                item.lead_tail,
                item.mean,
                item.kuriozita,
                item.pointa,
                item.citace_text,
            ]
        )
    listy = content.snemovni_listy
    if listy:
        for key in ("meta", "deck", "footer"):
            val = listy.get(key)
            if isinstance(val, str):
                chunks.append(val)
        for section in listy.get("sections") or []:
            if isinstance(section, dict):
                heading = section.get("heading")
                if isinstance(heading, str):
                    chunks.append(heading)
                for para in section.get("paragraphs") or []:
                    if isinstance(para, str):
                        chunks.append(para)
                for bullet in section.get("bullets") or []:
                    if isinstance(bullet, str):
                        chunks.append(bullet)
    return slovnicek_dne(*chunks, base_path=base_path)


def css_asset_version() -> str:
    import hashlib

    h = hashlib.sha256()
    for path in (_CSS, _SATELLITE_CSS, _ADMIN_CSS):
        if path.is_file():
            h.update(path.read_bytes())
    return h.hexdigest()[:10]


def _inline_css_text(*, satellite: bool = False, admin: bool = False) -> str:
    parts = [_CSS.read_text(encoding="utf-8")]
    if satellite and _SATELLITE_CSS.is_file():
        parts.append(_SATELLITE_CSS.read_text(encoding="utf-8"))
    if admin and _ADMIN_CSS.is_file():
        parts.append(_ADMIN_CSS.read_text(encoding="utf-8"))
    return "\n".join(parts)


def fonts_asset_version() -> str:
    import hashlib

    return hashlib.sha256(_FONTS_CSS.read_bytes()).hexdigest()[:10]


def _split_paragraphs(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p for p in parts if p]


def _abs_href(href: str, site_url: str | None) -> str:
    if not site_url or not href or href.startswith(("http://", "https://", "mailto:")):
        return href
    return f"{site_url.rstrip('/')}{href}"


def _apply_content_item_links(
    content: DenContent,
    paths: SchuzePaths,
    *,
    obdobi: int,
    link_mode: str,
    base_path: str = "",
    site_url: str | None = None,
) -> None:
    """Doplní odkazy v lead/mean a kuriozita_nav — stejná logika jako u webového vydání."""
    for item in content.items:
        link_pairs: list[tuple[str, str]] = []
        for phrase, page in item.mean_links:
            if page not in ("neprosli", "prosli", "zvoleni"):
                continue
            kind: VyznamenaniKind = page  # type: ignore[assignment]
            if not load_vyznamenani(paths, content.datum, kind):
                continue
            href = vyznamenani_href(
                obdobi,
                paths.schuze,
                content.datum,
                kind,
                link_mode=link_mode,
                base_path=base_path,
            )
            link_pairs.append((phrase, _abs_href(href, site_url)))
        if link_pairs:
            item.lead = inject_mean_links(item.lead, link_pairs)
            item.mean = inject_mean_links(item.mean, link_pairs)
        if item.kuriozita_links:
            resolved = resolve_vyznamenani_page_links(
                paths,
                content.datum,
                item.kuriozita_links,
                obdobi=obdobi,
                schuze=paths.schuze,
                link_mode=link_mode,
                base_path=base_path,
            ) + resolve_recnici_page_links(
                paths,
                content.datum,
                item.kuriozita_links,
                obdobi=obdobi,
                schuze=paths.schuze,
                link_mode=link_mode,
                base_path=base_path,
            )
            from svejk.build.mezin_smlouvy import resolve_smlouvy_page_links

            resolved += resolve_smlouvy_page_links(
                paths,
                content.datum,
                item.kuriozita_links,
                obdobi=obdobi,
                schuze=paths.schuze,
                link_mode=link_mode,
                base_path=base_path,
            )
            item.kuriozita_nav = [
                (label, _abs_href(href, site_url)) for label, href in resolved
            ]


def _apply_steno_links(
    content: DenContent,
    paths: SchuzePaths,
    *,
    obdobi: int,
    link_mode: str,
    base_path: str = "",
) -> str | None:
    return apply_steno_links_to_content(
        content,
        paths,
        obdobi=obdobi,
        link_mode=link_mode,
        base_path=base_path,
    )


def _jinja_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES)),
        autoescape=select_autoescape(["html"]),
    )
    env.filters["split_paragraphs"] = _split_paragraphs

    @pass_context
    def _glossary_filter(context, text: str) -> Markup:
        from svejk.build.glossary_markup import glossary_markup as _gm

        return _gm(text)

    env.filters["glossary"] = _glossary_filter

    def _plain_filter(text: str) -> str:
        from svejk.build.glossary_markup import strip_glossary_markup

        if not text:
            return ""
        return re.sub(r"<[^>]+>", "", strip_glossary_markup(text)).strip()

    env.filters["plain"] = _plain_filter

    @pass_context
    def _kuriozita_display_filter(context, text: str) -> Markup:
        from svejk.build.glossary_markup import highlight_markup
        from svejk.build.witty import rozdel_kuriozitu_label

        text = (text or "").strip()
        if not text:
            return Markup("")
        label, body = rozdel_kuriozitu_label(text)
        if label:
            return Markup(
                f'<strong class="kuriozita-label">{label}</strong> {highlight_markup(body)}'
            )
        return Markup(highlight_markup(text))

    env.filters["kuriozita_display"] = _kuriozita_display_filter
    return env


_DEFAULT_FOOTER_CONTACT = "svejk@poslusnehlasim.cz"


def _footer_closing(seed: str) -> str:
    closings = footer_closings()
    idx = sum(ord(c) for c in seed) % len(closings)
    return closings[idx]


def _edition_stats_parts(obdobi: int) -> tuple[int, str]:
    editions = list_site_editions(obdobi)
    n_editions = len(editions)
    n_schuze = len({e.schuze for e in editions})
    schuze_part = schuze_count_label(n_schuze)
    return n_editions, schuze_part


def _footer_stats_line(obdobi: int) -> str:
    n_editions, schuze_part = _edition_stats_parts(obdobi)
    return footer_stats_line(n_editions, schuze_part)


def _page_path_from_canonical(canonical_url: str, site_url: str) -> str:
    site = site_url.rstrip("/")
    if canonical_url.startswith(site):
        path = canonical_url[len(site) :]
        return path if path else "/"
    return canonical_url


def _edition_subpage_breadcrumbs(
    *,
    site_url: str,
    base_path: str,
    obdobi: int,
    schuze: int,
    datum_unl: str,
    subpage_label: str,
) -> dict:
    from svejk.build.seo import breadcrumbs_ctx_edition_subpage

    return breadcrumbs_ctx_edition_subpage(
        site_url=site_url,
        base_path=base_path,
        obdobi=obdobi,
        schuze=schuze,
        datum_unl=datum_unl,
        subpage_label=subpage_label,
    )


def _site_ctx(
    *,
    site_url: str,
    base_path: str = "",
    page_path: str = "/",
) -> dict[str, Any]:
    from svejk.build.seo import site_brand_line as _site_brand_line
    from svejk.build.seo import site_meta_description as _site_meta_description

    t = load_strings()
    page = page_path if page_path.startswith("/") else f"/{page_path}"
    share_page_url = f"{site_url.rstrip('/')}{page}"
    return {
        "t": t,
        "site_meta_description": _site_meta_description(),
        "site_brand_line": _site_brand_line(),
        "share_page_url": share_page_url,
    }


def _site_footer_ctx(
    base_path: str = "",
    *,
    obdobi: int = 2025,
    active_page: str = "",
    closing_seed: str = "",
) -> dict[str, str]:
    cfg = NewsletterConfig.from_env()
    seed = closing_seed or active_page or base_path or "site"
    contact = (cfg.contact_email or _DEFAULT_FOOTER_CONTACT).strip()
    return {
        "terms_href": podminky_pages_href(base_path),
        "privacy_href": soukromi_pages_href(base_path),
        "about_href": o_webu_pages_href(base_path),
        "support_href": podpora_pages_href(base_path),
        "footer_closing": _footer_closing(seed),
        "footer_stats": _footer_stats_line(obdobi),
        "footer_contact_email": contact,
        "footer_active_page": active_page,
    }


def _edition_nav_ctx(
    obdobi: int,
    base_path: str,
    *,
    schuze: int,
    datum: str,
    link_mode: str,
    site_url: str,
) -> dict[str, str]:
    ctx = _site_nav_ctx(
        obdobi,
        base_path,
        current_schuze=schuze,
        current_datum=datum,
    )
    if link_mode != "file":
        return ctx
    # ponytail: lokální náhled — menu vede na produkci, jako fonty
    site = site_url.rstrip("/")
    return {
        k: (f"{site}{v}" if v and str(v).startswith("/") else (v or ""))
        for k, v in ctx.items()
    }


def _edition_back_label(datum_unl: str) -> str:
    d = datetime.strptime(datum_unl, "%d.%m.%Y")
    return f"{d.day}. {d.month}. {d.year}"


def _site_nav_ctx(
    obdobi: int,
    base_path: str = "",
    *,
    current_schuze: int | None = None,
    current_datum: str | None = None,
) -> dict[str, str]:
    editions = list_site_editions(obdobi)
    latest_href = ""
    edition_back_href = ""
    edition_back_label = ""
    if editions:
        latest = editions[-1]
        latest_href = edition_pages_href(
            latest.obdobi, latest.schuze, latest.datum_unl, base_path
        )
        if (
            current_schuze is not None
            and current_datum is not None
            and latest.schuze == current_schuze
            and latest.datum_unl == current_datum
        ):
            latest_href = ""
        edition_back_href = edition_pages_href(
            latest.obdobi, latest.schuze, latest.datum_unl, base_path
        )
        edition_back_label = _edition_back_label(latest.datum_unl)
    return {
        "archive_href": archiv_pages_href(base_path),
        "latest_href": latest_href,
        "edition_back_href": edition_back_href,
        "edition_back_label": edition_back_label,
        "slovnicek_href": slovnicek_pages_href(base_path),
        "pivo_href": pivo_pages_href(base_path),
    }


def render_site_footer_html(base_path: str = "", *, obdobi: int = 2025) -> str:
    env = _jinja_env()
    cfg = NewsletterConfig.from_env()
    return env.get_template("site-footer.html").render(
        **_site_footer_ctx(base_path, obdobi=obdobi, closing_seed="snapshot"),
        t=load_strings(),
    )


def inject_site_footer(html: str, base_path: str = "") -> str:
    """Doplní patičku do HTML z produkčního snapshotu, pokud v něm chybí."""
    if 'class="site-footer"' in html:
        return html
    fragment = render_site_footer_html(base_path)
    marker = '<div id="cookie-consent"'
    if marker in html:
        return html.replace(marker, fragment + "\n" + marker, 1)
    if "</body>" in html:
        return html.replace("</body>", fragment + "\n</body>", 1)
    return html + "\n" + fragment


def render_den_html(
    content: DenContent,
    paths: SchuzePaths,
    day_path: Path,
    *,
    inline_css: bool = True,
    css_href: str | None = None,
    fonts_css_href: str | None = None,
    link_mode: str = "file",
    obdobi: int | None = None,
    base_path: str = "",
    canonical_url: str = "",
    meta_description: str = "",
    is_homepage: bool = False,
) -> str:
    _ = day_path
    css = _CSS.read_text(encoding="utf-8") if inline_css else ""
    if css_href is None:
        css_href = static_css_path(base_path)
    favicons = static_favicon_paths(base_path)
    nav = edition_nav(
        paths,
        content.datum,
        link_mode=link_mode,
        obdobi=obdobi,
        base_path=base_path,
    )
    ob = obdobi if obdobi is not None else paths.obdobi
    dup_day = sum(1 for e in list_site_editions(ob) if e.datum_unl == content.datum) > 1
    cfg = NewsletterConfig.from_env()
    if fonts_css_href is None:
        fonts_css_href = static_fonts_css_path(base_path)
        if link_mode == "file":
            # lokální náhledy v processed/ — fonty natáhnou z produkčního webu
            fonts_css_href = f"{cfg.site_url.rstrip('/')}{fonts_css_href}"
    if not meta_description:
        from svejk.build.seo import edition_meta_description as _edition_meta_description

        meta_description = _edition_meta_description(
            dnesni_ucet=content.dnesni_ucet,
            nadpis_vydani=content.nadpis_vydani,
            first_item_nadpis=content.items[0].nadpis if content.items else "",
            datum_unl=content.datum,
            proslo=content.proslo,
            zamitnuto=content.zamitnuto,
        )
    if not canonical_url:
        href = edition_pages_href(ob, paths.schuze, content.datum, base_path)
        canonical_url = f"{cfg.site_url.rstrip('/')}{href}"
    page_path = _page_path_from_canonical(canonical_url, cfg.site_url)
    nav_ctx = _edition_nav_ctx(
        ob,
        base_path,
        schuze=paths.schuze,
        datum=content.datum,
        link_mode=link_mode,
        site_url=cfg.site_url,
    )
    datum_label = datum_design(content.datum, content.den)
    edition_title = f"{SITE_NAME} · {datum_label}"
    from svejk.build.seo import article_headline as _article_headline
    from svejk.build.seo import article_json_ld as _article_json_ld
    from svejk.build.seo import edition_page_title as _edition_page_title
    from svejk.build.seo import homepage_page_title as _homepage_page_title
    from svejk.build.seo import homepage_share_og_title as _homepage_share_og_title

    # Homepage: stabilní <title> s klíčovými slovy; vydání: datum + téma dne.
    page_title = (
        _homepage_page_title()
        if is_homepage
        else _edition_page_title(
            dnesni_ucet=content.dnesni_ucet,
            meta_description=meta_description,
            nadpis_vydani=content.nadpis_vydani,
            first_item_nadpis=content.items[0].nadpis if content.items else "",
            datum_unl=content.datum,
            den=content.den,
            datum_design=datum_label,
        )
    )
    from svejk.build.og_image import (
        OG_HEIGHT,
        OG_WIDTH,
        edition_og_headline,
        edition_og_title,
        og_image_abs_url,
        share_hero_href,
    )

    og_share_title = (
        _homepage_share_og_title(
            dnesni_ucet=content.dnesni_ucet,
            nadpis_vydani=content.nadpis_vydani,
            first_item_nadpis=content.items[0].nadpis if content.items else "",
            datum_unl=content.datum,
            den=content.den,
        )
        if is_homepage
        else _edition_page_title(
            dnesni_ucet=content.dnesni_ucet,
            nadpis_vydani=content.nadpis_vydani,
            first_item_nadpis=content.items[0].nadpis if content.items else "",
            datum_unl=content.datum,
            den=content.den,
        )
    )
    og_headline = edition_og_headline(
        dnesni_ucet=content.dnesni_ucet,
        nadpis_vydani=content.nadpis_vydani,
        first_item_nadpis=content.items[0].nadpis if content.items else "",
        datum_unl=content.datum,
        den=content.den,
    )
    og_published = datetime.strptime(content.datum, "%d.%m.%Y").strftime(
        "%Y-%m-%dT00:00:00+01:00"
    )
    og = _og_context(
        site_url=cfg.site_url,
        base_path=base_path,
        title=og_share_title,
        description=meta_description,
        og_type="article",
        image_url=og_image_abs_url(cfg.site_url, base_path, content.datum),
        image_width=OG_WIDTH,
        image_height=OG_HEIGHT,
        image_alt=og_headline,
        published_time=og_published,
    )
    schema_headline = _article_headline(
        dnesni_ucet=content.dnesni_ucet,
        meta_description=meta_description,
        nadpis_vydani=content.nadpis_vydani,
        first_item_nadpis=content.items[0].nadpis if content.items else "",
        edition_title=edition_title,
    )
    from svejk.build.seo import breadcrumbs_ctx_edition
    from svejk.build.day_content import edition_day_meta as _edition_day_meta
    from svejk.build.nav import homepage_archive_list as _homepage_archive_list
    from svejk.build.urls import datum_unl_to_iso as _datum_unl_to_iso

    edition_day_headline = schema_headline
    edition_day_meta_label = _edition_day_meta(content.den, content.datum)
    edition_iso_date = _datum_unl_to_iso(content.datum)
    homepage_archive = (
        _homepage_archive_list(
            paths,
            content.datum,
            link_mode=link_mode if link_mode in ("pages", "web") else "pages",
            obdobi=ob,
            base_path=base_path,
            limit=5,
        )
        if is_homepage
        else ()
    )
    import re as _re

    from svejk.build.glossary_markup import strip_glossary_markup as _strip_gloss

    def _plain(text: str) -> str:
        return _re.sub(r"<[^>]+>", "", _strip_gloss(text or "")).strip()

    schema_parts: list[dict[str, str | int]] = []
    body_chunks: list[str] = []
    for item in content.items:
        chunk = _plain(item.lead)
        mean = _plain(item.mean)
        if mean:
            chunk = f"{chunk} {mean}"
        nadpis = _plain(item.nadpis)
        body_chunks.append(f"{nadpis}. {chunk}")
        schema_parts.append(
            {
                "headline": nadpis,
                "body": chunk,
                "position": item.num,
                "url": f"{canonical_url}#{item.anchor_id}",
            }
        )
    if content.zaver:
        body_chunks.append(_plain(content.zaver))
    from svejk.build.seo import mtime_iso as _mtime_iso
    from svejk.build.seo import publisher_logo_url as _publisher_logo_url
    from svejk.build.seo import website_json_ld as _website_json_ld

    date_modified = _mtime_iso(day_path) if day_path.is_file() else None
    website_ld = (
        _website_json_ld(
            site_url=cfg.site_url,
            logo_url=_publisher_logo_url(cfg.site_url, base_path),
            base_path=base_path,
        )
        if is_homepage
        else ""
    )
    json_ld = _article_json_ld(
        headline=schema_headline,
        description=meta_description,
        url=canonical_url,
        date_unl=content.datum,
        site_url=cfg.site_url,
        image_url=og["og_image_url"],
        logo_url=_publisher_logo_url(cfg.site_url, base_path),
        date_modified=date_modified,
        edition_title=edition_title,
        article_body=" ".join(body_chunks),
        parts=schema_parts or None,
        base_path=base_path,
    )
    for item in content.items:
        if item.mean_links:
            link_pairs: list[tuple[str, str]] = []
            for phrase, page in item.mean_links:
                if page not in ("neprosli", "prosli", "zvoleni"):
                    continue
                kind: VyznamenaniKind = page  # type: ignore[assignment]
                if not load_vyznamenani(paths, content.datum, kind):
                    continue
                href = vyznamenani_href(
                    ob,
                    paths.schuze,
                    content.datum,
                    kind,
                    link_mode=link_mode,
                    base_path=base_path,
                )
                link_pairs.append((phrase, href))
            if link_pairs:
                item.lead = inject_mean_links(item.lead, link_pairs)
                item.mean = inject_mean_links(item.mean, link_pairs)
        if item.kuriozita_links:
            resolved = resolve_vyznamenani_page_links(
                paths,
                content.datum,
                item.kuriozita_links,
                obdobi=ob,
                schuze=paths.schuze,
                link_mode=link_mode,
                base_path=base_path,
            ) + resolve_recnici_page_links(
                paths,
                content.datum,
                item.kuriozita_links,
                obdobi=ob,
                schuze=paths.schuze,
                link_mode=link_mode,
                base_path=base_path,
            )
            from svejk.build.mezin_smlouvy import resolve_smlouvy_page_links

            item.kuriozita_nav = resolved + resolve_smlouvy_page_links(
                paths,
                content.datum,
                item.kuriozita_links,
                obdobi=ob,
                schuze=paths.schuze,
                link_mode=link_mode,
                base_path=base_path,
            )
    postreh, postreh_item_num = _edition_postreh(content)
    session_calendar = build_session_calendar(
        ob,
        content.datum,
        base_path=base_path,
        link_mode=link_mode if link_mode in ("pages", "web") else "pages",
    )
    slovnicek_dne = _edition_slovnicek(content, base_path=base_path)
    fav_href = _ph_fav_href(base_path)
    svejk_img_href = f"{base_path.rstrip('/')}/static/svejk-terra.png" if base_path else "/static/svejk-terra.png"
    share_hero = (
        share_hero_href(base_path, content.datum)
        if link_mode == "pages" and (content.zaver_body or content.zaver)
        else ""
    )
    tpl = _jinja_env().get_template("noviny-dlouhe.html")
    return tpl.render(
        content=content,
        obdobi=ob,
        schuze=paths.schuze,
        dup_day=dup_day,
        datum_design=datum_design(content.datum, content.den),
        pager_date_label=datum_day_month(content.datum),
        ph_fav_href=fav_href,
        svejk_img_href=svejk_img_href,
        share_hero_href=share_hero,
        inline_css=inline_css,
        css=css,
        css_href=css_href,
        fonts_css_href=fonts_css_href,
        nav=nav,
        postreh=postreh,
        postreh_item_num=postreh_item_num,
        session_calendar=session_calendar,
        slovnicek_dne=slovnicek_dne,
        jazykolam=content.jazykolam,
        steno_page_href=steno_sources_pages_href(ob, paths.schuze, content.datum, base_path),
        newsletter=cfg,
        canonical_url=canonical_url,
        meta_description=meta_description,
        page_title=page_title,
        article_json_ld=json_ld,
        website_json_ld=website_ld,
        **og,
        cookie_privacy_url=soukromi_pages_href(base_path),
        **_site_ctx( site_url=cfg.site_url, base_path=base_path, page_path=page_path),
        **nav_ctx,
        **_site_footer_ctx(
            base_path,
            obdobi=ob,
            closing_seed=f"{ob}/{paths.schuze}/{content.datum}",
        ),
        **favicons,
        is_homepage=is_homepage,
        edition_day_headline=edition_day_headline,
        edition_day_meta=edition_day_meta_label,
        edition_iso_date=edition_iso_date,
        homepage_archive=homepage_archive,
        **breadcrumbs_ctx_edition(
            site_url=cfg.site_url,
            base_path=base_path,
            datum_unl=content.datum,
            is_homepage=is_homepage,
        ),
    )


def _static_asset_url(site_url: str, base_path: str, name: str) -> str:
    base = base_path.rstrip("/")
    prefix = f"{base}/static" if base else "/static"
    return f"{site_url.rstrip('/')}{prefix}/{name}"


def _ph_fav_href(base_path: str = "") -> str:
    base = base_path.rstrip("/")
    return f"{base}/static/ph-fav.svg" if base else "/static/ph-fav.svg"


def _social_image_asset() -> tuple[str, int, int]:
    """Soubor a rozměry sdílecího obrázku (og-share.png od grafika, jinak favicon)."""
    if _OG_SHARE.is_file():
        return "og-share.png", *_OG_SHARE_SIZE
    return "apple-touch-icon.png", *_FALLBACK_OG_SIZE


def _og_context(
    *,
    site_url: str,
    base_path: str,
    title: str,
    description: str,
    og_type: str = "website",
    image_url: str | None = None,
    image_width: int | None = None,
    image_height: int | None = None,
    image_alt: str | None = None,
    published_time: str | None = None,
) -> dict[str, str | int]:
    if image_url:
        og_image_url = image_url
        og_image_width = image_width or _OG_SHARE_SIZE[0]
        og_image_height = image_height or _OG_SHARE_SIZE[1]
        og_image_alt = image_alt or SITE_NAME
    else:
        image_name, image_w, image_h = _social_image_asset()
        og_image_url = _static_asset_url(site_url, base_path, image_name)
        og_image_width = image_w
        og_image_height = image_h
        og_image_alt = image_alt or f"{SITE_NAME}, Švejk"
    ctx: dict[str, str | int] = {
        "og_title": title,
        "og_description": description,
        "og_image_url": og_image_url,
        "og_image_width": og_image_width,
        "og_image_height": og_image_height,
        "og_image_alt": og_image_alt,
        "og_type": og_type,
    }
    if published_time:
        ctx["og_published_time"] = published_time
    return ctx


def plain_text_from_content(
    content: DenContent,
    *,
    datum_label: str,
    edition_url: str,
    archive_url: str,
    pivo_url: str,
) -> str:
    from svejk.build.glossary_markup import strip_glossary_markup

    def _plain(text: str) -> str:
        if not text:
            return ""
        return re.sub(r"<[^>]+>", "", strip_glossary_markup(text)).strip()

    lines = [f"POSLUŠNĚ HLÁSÍM · {datum_label}", ""]
    zaver = _plain(content.zaver or "")
    if zaver:
        lines.append(f"„{zaver}“")
    for item in content.items:
        lines.extend(
            [
                "",
                f"{item.num:02d} · {item.kick} · {item.stamp}",
                _plain(item.nadpis),
                _plain(item.lead),
            ]
        )
        if item.citace_text:
            cite = f"„{_plain(item.citace_text)}“"
            if item.citace_autor:
                cite = f"{cite} ({item.citace_autor})"
            lines.append(cite)
        if item.lead_tail and item.kuriozita:
            lines.append(_plain(item.kuriozita))
            lines.append(_plain(item.lead_tail))
        elif item.lead_tail:
            lines.append(_plain(item.lead_tail))
        if item.pointa:
            lines.append(_plain(item.pointa))
        if item.mean:
            mean_label = load_strings()["edition"]["mean_label"]
            lines.append(f"{mean_label} {_plain(item.mean)}")
        if item.kuriozita and not item.lead_tail:
            lines.append(_plain(item.kuriozita))
        for label, href in item.kuriozita_nav:
            lines.append(f"{label}: {href}")
    lines.extend(
        [
            "",
            f"Číst vydání: {edition_url}",
            f"Archiv všech vydání: {archive_url}",
            f"Kup Švejkovi pivo: {pivo_url}#stamgast",
            "",
            "Odhlášení odběru: odkaz v patičce e-mailu od Ecomailu.",
        ]
    )
    return "\n".join(lines)


def _make_internal_links_absolute(text: str, site_url: str) -> str:
    """Přepíše relativní href (/noviny/...) na absolutní URL pro e-mail."""
    if not text or "href=\"/" not in text:
        return text
    site = site_url.rstrip("/")
    return re.sub(
        r'href="(/[^"]*)"',
        lambda m: f'href="{site}{m.group(1)}"',
        text,
    )


_FIELD_LINK_STYLE = {
    "lead": "color:#211c14",
    "mean": "color:#211c14",
    "kuriozita": "color:#5a5348",
    "citace_text": "color:#211c14",
    "zaver": "color:#cf5a31",
    "zaver_body": "color:#cf5a31",
    "dnesni_ucet": "color:#211c14",
}


def _inline_email_body_link_styles(text: str, *, field: str = "lead") -> str:
    """Inline styly pro klienty, které neberou <style> z hlavičky."""
    if not text:
        return text
    if '<span class="hl">' in text:
        text = text.replace(
            '<span class="hl">',
            '<span class="hl" style="display:inline;background:rgba(210,60,30,.25);border-radius:2px;padding:0 2px;margin:0 -2px;">',
        )
    if "<a " not in text:
        return text
    color = _FIELD_LINK_STYLE.get(field, _FIELD_LINK_STYLE["lead"])
    style = f'style="{color};text-decoration:underline;font-weight:inherit;"'
    text = text.replace('class=\\"steno-link\\"', 'class="steno-link"')
    text = text.replace('class=\\"mean-link\\"', 'class="mean-link"')
    return re.sub(
        r'<a class="(steno-link|mean-link)"',
        lambda m: f'<a class="{m.group(1)}" {style}',
        text,
    )


def _apply_email_links_absolute(content: Any, site_url: str) -> None:
    """Po doplnění odkazů udělá všechny interní hrefs absolutní."""
    site = site_url.rstrip("/")
    for item in content.items:
        for field in ("lead", "lead_tail", "mean", "kuriozita", "citace_text", "pointa"):
            val = getattr(item, field, None)
            if val:
                val = _make_internal_links_absolute(val, site_url)
                val = _inline_email_body_link_styles(val, field=field)
                setattr(item, field, val)
        citace_href = (getattr(item, "citace_href", None) or "").strip()
        if citace_href.startswith("/"):
            item.citace_href = f"{site}{citace_href}"
        if item.kuriozita_nav:
            item.kuriozita_nav = [
                (label, f"{site}{href}" if href.startswith("/") else href)
                for label, href in item.kuriozita_nav
            ]
    for field in ("dnesni_ucet", "result_note", "zaver", "zaver_body"):
        val = getattr(content, field, None)
        if val:
            val = _make_internal_links_absolute(val, site_url)
            val = _inline_email_body_link_styles(val, field=field)
            setattr(content, field, val)


def _prepare_content_for_email(content: DenContent) -> None:
    """Tooltipy v e-mailu nefungují — nech jen viditelný text."""
    from svejk.build.glossary_markup import strip_glossary_markup

    for field in ("dnesni_ucet", "result_note", "zaver", "zaver_body"):
        val = getattr(content, field, None)
        if val:
            setattr(content, field, strip_glossary_markup(val))
    for item in content.items:
        for field in ("lead", "lead_tail", "mean", "kuriozita", "citace_text", "pointa"):
            val = getattr(item, field, None)
            if val:
                setattr(item, field, strip_glossary_markup(val))


def render_email_html(
    edition: Edition,
    *,
    site_url: str,
    base_path: str = "",
) -> tuple[str, str, str]:
    """HTML + plain text newsletteru ve stylu webového vydání."""
    paths = SchuzePaths.create(edition.obdobi, edition.schuze)
    d = datetime.strptime(edition.datum_unl, "%d.%m.%Y")
    day_path = paths.facts_by_day / f"{d.strftime('%Y-%m-%d')}.json"
    site = site_url.rstrip("/")
    content = build_den_content(day_path, paths, link_mode="pages", base_path=base_path)
    edition_href = edition_pages_href(
        edition.obdobi, edition.schuze, edition.datum_unl, base_path
    )
    archive_href = archiv_pages_href(base_path)
    pivo_href = pivo_pages_href(base_path)
    edition_url = f"{site}{edition_href}"
    archive_url = f"{site}{archive_href}"
    pivo_url = f"{site}{pivo_href}"
    steno_href = steno_sources_pages_href(
        edition.obdobi, paths.schuze, edition.datum_unl, base_path
    )
    steno_page_url = f"{site}{steno_href}" if steno_href else ""
    datum_label = datum_design(edition.datum_unl, content.den)
    subject = f"Nové vydání · {datum_label}"
    _apply_content_item_links(
        content,
        paths,
        obdobi=edition.obdobi,
        link_mode="pages",
        base_path=base_path,
        site_url=site,
    )
    _apply_email_links_absolute(content, site)
    _prepare_content_for_email(content)
    plain = plain_text_from_content(
        content,
        datum_label=datum_label,
        edition_url=edition_url,
        archive_url=archive_url,
        pivo_url=pivo_url,
    )
    css = _EMAIL_CSS.read_text(encoding="utf-8")
    tpl = _jinja_env().get_template("noviny-email.html")
    html = tpl.render(
        content=content,
        css=css,
        t=load_strings(),
        datum_design=datum_label,
        edition_url=edition_url,
        archive_url=archive_url,
        pivo_url=pivo_url,
        static_base=f"{site}/static",
        steno_page_url=steno_page_url,
    )
    return subject, plain, html


def render_doi_email_html(
    *,
    site_url: str | None = None,
    base_path: str = "",
) -> tuple[str, str, str]:
    """HTML + plain text pro potvrzovací e-mail (double opt-in) v Ecomailu."""
    from svejk.build.nav import soukromi_pages_href

    cfg = NewsletterConfig.from_env()
    site = (site_url or cfg.site_url).rstrip("/")
    t = load_strings()
    doi = t["doi"]
    base = base_path.rstrip("/")
    privacy_path = soukromi_pages_href(base)
    confirm_path = "/potvrzeno/"
    privacy_url = f"{site}{privacy_path}"
    confirm_redirect_url = f"{site}{confirm_path}"
    subject = doi["subject"]
    css = _DOI_EMAIL_CSS.read_text(encoding="utf-8")
    tpl = _jinja_env().get_template("doi-email.html")
    html = tpl.render(
        t=t,
        css=css,
        privacy_url=privacy_url,
        confirm_redirect_url=confirm_redirect_url,
        svejk_head_url=f"{site}/static/favicon.png",
        static_base=f"{site}/static",
    )
    plain = "\n".join(
        [
            doi["plain_lead"],
            "",
            doi["intro"],
            "",
            f"{doi['quote_key']} {doi['quote_body']}",
            "",
            doi["plain_cta"],
            "",
            doi["inbox_tip"],
            "",
            f"{doi['plain_after_confirm']} {confirm_redirect_url}",
            doi["footer"],
            f"{doi['privacy_link']}: {privacy_url}",
        ]
    )
    return subject, plain, html


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

