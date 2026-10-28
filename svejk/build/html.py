"""HTML výstup novin-dlouhe (design varianta C)."""

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
    from svejk.build.glossary_markup import slovnicek_dne, slovnicek_from_labels

    if content.slovnicek:
        return slovnicek_from_labels(content.slovnicek, base_path=base_path)

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
                item.pointa_tail,
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


_JS_DIR = _STATIC / "js"


@lru_cache(maxsize=32)
def js_asset_version(name: str) -> str:
    import hashlib

    path = _JS_DIR / name
    return hashlib.sha256(path.read_bytes()).hexdigest()[:10] if path.is_file() else ""


def _static_dir_from_css(css_href: str) -> str:
    """/static (nebo base_path/static, file://…/static) podle odkazu na CSS stránky."""
    href = (css_href or "").split("?", 1)[0]
    if "/" in href:
        return href.rsplit("/", 1)[0]
    return "/static"


def fonts_asset_version() -> str:
    import hashlib

    return hashlib.sha256(_FONTS_CSS.read_bytes()).hexdigest()[:10]


def fonts_css_inline(fonts_css_href: str) -> str:
    """fonts.css pro <style> v head. Relativní url(fonts/…) → absolutní pod /static/."""
    if not fonts_css_href:
        return ""
    base = fonts_css_href.split("?", 1)[0].rsplit("/fonts.css", 1)[0]
    raw = _FONTS_CSS.read_text(encoding="utf-8")
    return raw.replace("url('fonts/", f"url('{base}/fonts/").replace(
        'url("fonts/', f'url("{base}/fonts/'
    )


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


@lru_cache(maxsize=1)
def _jinja_env() -> Environment:
    # Jedno prostředí na běh: dřív se Environment (a kompilace šablon) tvořil
    # při každém renderu, 4 722× za export (~36 s).
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

    def _fonts_inline_filter(href: str) -> Markup:
        return Markup(fonts_css_inline(href or ""))

    env.filters["fonts_inline"] = _fonts_inline_filter

    @pass_context
    def _static_js(context, name: str) -> str:
        # Skripty jako /static/js/*.js?v=hash: dřív ~48 KB inline JS v každé stránce,
        # bez cache prohlížeče.
        base = _static_dir_from_css(str(context.get("css_href") or "")) or "/static"
        version = js_asset_version(name)
        return f"{base}/js/{name}" + (f"?v={version}" if version else "")

    env.globals["static_js"] = _static_js
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
    edition_href: str | None = None,
) -> dict:
    from svejk.build.seo import breadcrumbs_ctx_edition_subpage

    return breadcrumbs_ctx_edition_subpage(
        site_url=site_url,
        base_path=base_path,
        obdobi=obdobi,
        schuze=schuze,
        datum_unl=datum_unl,
        subpage_label=subpage_label,
        edition_href=edition_href,
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
    # build_den_content vrací sdílený objekt z cache; odkazy níž se do něj vkládají,
    # takže druhé vykreslení (homepage) by jinak vnořilo <a> do <a>.
    content = copy.deepcopy(content)
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
        share_cache_key,
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
    og_published = edition_published_iso(content.datum)
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
    from svejk.build.seo import edition_modified_iso as _edition_modified_iso
    from svejk.build.seo import publisher_logo_url as _publisher_logo_url
    from svejk.build.seo import website_json_ld as _website_json_ld

    date_modified = _edition_modified_iso(paths, content.datum)
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
    zaver_for_share = (content.zaver or "").strip() or (content.zaver_body or "").strip()
    share_hero = (
        share_hero_href(
            base_path,
            content.datum,
            version=share_cache_key(zaver_for_share),
        )
        if link_mode == "pages" and zaver_for_share
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
        # bez steno stránky Citát dne odkazuje rovnou na PSP (jazykolam.href)
        steno_page_href=(
            steno_sources_href(
                ob, paths.schuze, content.datum, link_mode=link_mode, base_path=base_path
            )
            if has_steno_sources(paths, content.datum)
            else ""
        ),
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


_FIELD_LINK_STYLE = {
    "lead": "color:#211c14",
    "mean": "color:#211c14",
    "kuriozita": "color:#5a5348",
    "citace_text": "color:#211c14",
    "zaver": "color:#cf5a31",
    "zaver_body": "color:#cf5a31",
    "dnesni_ucet": "color:#211c14",
}


