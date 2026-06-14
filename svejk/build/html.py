"""HTML výstup novin-dlouhe (design varianta C)."""

from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, pass_context, select_autoescape
from markupsafe import Markup

from svejk.build.day_content import DenContent, build_den_content, datum_design
from svejk.build.io import read_json
from svejk.glossary import slovnicek_anchor, slovnicek_for_locale
from svejk.build.publish import list_site_editions
from svejk.locale import (
    alternate_locale,
    footer_closings,
    footer_stats_line,
    hreflang_links,
    load_strings,
    localized_path,
    locale_switch_href,
    normalize_locale,
    og_locale_tag,
    schuze_count_label,
)
from svejk.build.nav import (
    Edition,
    archiv_pages_href,
    archive_by_month,
    edition_nav,
    edition_pages_href,
    pivo_pages_href,
    dekuju_pages_href,
    podminky_pages_href,
    podpora_pages_href,
    slovnicek_pages_href,
    soukromi_pages_href,
    vyznamenani_pages_href,
)

# Stripe Payment Links — redirect ve Stripe Dashboardu → /dekuju.html
STRIPE_PIVO_URL = "https://donate.stripe.com/14A7sNekE1pP8cEfb83Je00"
STRIPE_RUM_URL = "https://donate.stripe.com/4gM00l0tO3xX0Kc1ki3Je01"
STRIPE_STAMGAST_URL = "https://donate.stripe.com/5kQ14pa4o8ShfF66EC3Je02"
STRIPE_PORTAL_URL = "https://billing.stripe.com/p/login/14A7sNekE1pP8cEfb83Je00"


def _stripe_url(env_key: str, default: str) -> str:
    return os.environ.get(env_key, default).strip() or default


def pivo_tiers(locale: str = "cs") -> list[dict[str, Any]]:
    """Hospodský ceník — tři položky, pay_href vede na Stripe Payment Links."""
    loc = normalize_locale(locale)
    pt = load_strings(loc).get("pivo_tiers", {})
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
    localized_vyznamenani_data,
    page_explain,
    page_meta,
    resolve_vyznamenani_page_links,
    sibling_label,
    table_rows,
    vyznamenani_datum_label,
    vyznamenani_href,
    _load_votes_by_cislo,
)
from svejk.newsletter.config import NewsletterConfig
from svejk.paths import SchuzePaths

_TEMPLATES = Path(__file__).resolve().parent.parent / "templates"
_STATIC = Path(__file__).resolve().parent.parent / "static"
_CSS = _STATIC / "noviny-dlouhe.css"
_FONTS_CSS = _STATIC / "fonts.css"
_EMAIL_CSS = _STATIC / "noviny-email.css"
_SVEJK_SVG = _STATIC / "svejk.svg"
_FAVICON_PNG = _STATIC / "svejk-terra.png"
_OG_SHARE = _STATIC / "og-share.png"
_OG_SHARE_SIZE = (1200, 630)
_FALLBACK_OG_SIZE = (200, 280)


def static_css_path(base_path: str = "", *, version: str | None = None) -> str:
    base = base_path.rstrip("/")
    path = "/static/noviny-dlouhe.css"
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
        "favicon_svg": f"{prefix}/favicon.svg",
        "favicon_png": f"{prefix}/favicon.png",
        "apple_touch_icon": f"{prefix}/apple-touch-icon.png",
    }


def css_asset_version() -> str:
    import hashlib

    return hashlib.sha256(_CSS.read_bytes()).hexdigest()[:10]


def fonts_asset_version() -> str:
    import hashlib

    return hashlib.sha256(_FONTS_CSS.read_bytes()).hexdigest()[:10]


def _proslo_board_label(n: int, locale: str = "cs") -> str:
    b = load_strings(locale).get("board", {})
    if n == 1:
        return b.get("proslo_1", "věc schválili")
    if 2 <= n <= 4:
        return b.get("proslo_2_4", "věci schválili")
    return b.get("proslo_other", "věcí schválili")


def _zamitnuto_board_label(n: int, locale: str = "cs") -> str:
    b = load_strings(locale).get("board", {})
    if n == 1:
        return b.get("zamitnuto_1", "návrh zamítli")
    if 2 <= n <= 4:
        return b.get("zamitnuto_2_4", "návrhy zamítli")
    return b.get("zamitnuto_other", "návrhů zamítli")



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
    locale: str = "cs",
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
                locale=locale,
            )
            link_pairs.append((phrase, _abs_href(href, site_url)))
        if link_pairs:
            item.lead = inject_mean_links(item.lead, link_pairs)
            item.mean = inject_mean_links(item.mean, link_pairs)
        if item.kuriozita_links:
            item.kuriozita_nav = [
                (label, _abs_href(href, site_url))
                for label, href in                 resolve_vyznamenani_page_links(
                    paths,
                    content.datum,
                    item.kuriozita_links,
                    obdobi=obdobi,
                    schuze=paths.schuze,
                    link_mode=link_mode,
                    base_path=base_path,
                    locale=locale,
                )
            ]


def _jinja_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES)),
        autoescape=select_autoescape(["html"]),
    )
    env.filters["split_paragraphs"] = _split_paragraphs

    @pass_context
    def _glossary_filter(context, text: str) -> Markup:
        from svejk.build.glossary_markup import glossary_markup as _gm

        loc = context.get("locale", "cs")
        return _gm(text, locale=loc)

    env.filters["glossary"] = _glossary_filter
    return env


_FOOTER_CLOSINGS = footer_closings("cs")

_DEFAULT_FOOTER_CONTACT = "svejk@poslusnehlasim.cz"


def _footer_closing(seed: str, locale: str = "cs") -> str:
    closings = footer_closings(locale)
    idx = sum(ord(c) for c in seed) % len(closings)
    return closings[idx]


def _edition_stats_parts(obdobi: int, locale: str = "cs") -> tuple[int, str]:
    editions = list_site_editions(obdobi)
    n_editions = len(editions)
    n_schuze = len({e.schuze for e in editions})
    schuze_part = schuze_count_label(n_schuze, locale)
    return n_editions, schuze_part


def _footer_stats_line(obdobi: int, locale: str = "cs") -> str:
    n_editions, schuze_part = _edition_stats_parts(obdobi, locale)
    return footer_stats_line(n_editions, schuze_part, locale)


def _page_path_from_canonical(canonical_url: str, site_url: str) -> str:
    site = site_url.rstrip("/")
    if canonical_url.startswith(site):
        path = canonical_url[len(site) :]
        return path if path else "/"
    return canonical_url


def _locale_ctx(
    locale: str,
    *,
    site_url: str,
    base_path: str = "",
    page_path: str = "/",
) -> dict[str, Any]:
    loc = normalize_locale(locale)
    t = load_strings(loc)
    return {
        "locale": loc,
        "lang": loc,
        "t": t,
        "og_locale": og_locale_tag(loc),
        "og_locale_alternate": og_locale_tag(alternate_locale(loc)),
        "hreflang_links": hreflang_links(page_path, site_url, base_path),
        "lang_switch_href": locale_switch_href(page_path, loc, base_path),
        "lang_switch_label": t["nav"]["lang_switch"],
        "lang_switch_aria": t["nav"]["lang_switch_aria"],
    }


def _site_footer_ctx(
    base_path: str = "",
    *,
    obdobi: int = 2025,
    active_page: str = "",
    closing_seed: str = "",
    locale: str = "cs",
) -> dict[str, str]:
    cfg = NewsletterConfig.from_env()
    seed = closing_seed or active_page or base_path or "site"
    contact = (cfg.contact_email or _DEFAULT_FOOTER_CONTACT).strip()
    loc = normalize_locale(locale)
    return {
        "terms_href": podminky_pages_href(base_path, loc),
        "privacy_href": soukromi_pages_href(base_path, loc),
        "support_href": podpora_pages_href(base_path, loc),
        "footer_closing": _footer_closing(seed, loc),
        "footer_stats": _footer_stats_line(obdobi, loc),
        "footer_contact_email": contact,
        "footer_active_page": active_page,
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
    locale: str = "cs",
) -> dict[str, str]:
    loc = normalize_locale(locale)
    editions = list_site_editions(obdobi)
    latest_href = ""
    edition_back_href = ""
    edition_back_label = ""
    if editions:
        latest = editions[-1]
        latest_href = edition_pages_href(
            latest.obdobi, latest.schuze, latest.datum_unl, base_path, loc
        )
        if (
            current_schuze is not None
            and current_datum is not None
            and latest.schuze == current_schuze
            and latest.datum_unl == current_datum
        ):
            latest_href = ""
        edition_back_href = edition_pages_href(
            latest.obdobi, latest.schuze, latest.datum_unl, base_path, loc
        )
        edition_back_label = _edition_back_label(latest.datum_unl)
    return {
        "archive_href": archiv_pages_href(base_path, loc),
        "latest_href": latest_href,
        "edition_back_href": edition_back_href,
        "edition_back_label": edition_back_label,
        "slovnicek_href": slovnicek_pages_href(base_path, loc),
        "pivo_href": pivo_pages_href(base_path, loc),
    }


def render_site_footer_html(base_path: str = "", *, obdobi: int = 2025, locale: str = "cs") -> str:
    env = _jinja_env()
    loc = normalize_locale(locale)
    cfg = NewsletterConfig.from_env()
    return env.get_template("site-footer.html").render(
        **_site_footer_ctx(base_path, obdobi=obdobi, closing_seed="snapshot", locale=loc),
        t=load_strings(loc),
        locale=loc,
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
    locale: str = "cs",
    show_locale_notice: bool | None = None,
) -> str:
    _ = day_path
    css = _CSS.read_text(encoding="utf-8") if inline_css else ""
    if css_href is None:
        css_href = static_css_path(base_path)
    favicons = static_favicon_paths(base_path)
    loc = normalize_locale(locale)
    nav = edition_nav(
        paths,
        content.datum,
        link_mode=link_mode,
        obdobi=obdobi,
        base_path=base_path,
        locale=loc,
    )
    svejk_svg = _SVEJK_SVG.read_text(encoding="utf-8") if _SVEJK_SVG.is_file() else ""
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
            first_item_nadpis=content.items[0].nadpis if content.items else "",
            proslo=content.proslo,
            zamitnuto=content.zamitnuto,
            locale=loc,
        ) or (
            f"Diary from the Czech Chamber of Deputies, {datum_design(content.datum, content.den)}."
            if loc == "en"
            else f"Deník z Poslanecké sněmovny, {datum_design(content.datum, content.den)}."
        )
    if not canonical_url:
        href = edition_pages_href(ob, paths.schuze, content.datum, base_path, loc)
        canonical_url = f"{cfg.site_url.rstrip('/')}{href}"
    page_path = _page_path_from_canonical(canonical_url, cfg.site_url)
    nav_ctx = (
        _site_nav_ctx(
            ob,
            base_path,
            current_schuze=paths.schuze,
            current_datum=content.datum,
            locale=loc,
        )
        if link_mode == "pages"
        else {
            "archive_href": None,
            "latest_href": None,
            "slovnicek_href": None,
            "pivo_href": None,
        }
    )
    datum_label = datum_design(content.datum, content.den)
    edition_title = f"Poslušně hlásím · {datum_label}"
    from svejk.build.seo import article_headline as _article_headline
    from svejk.build.seo import article_json_ld as _article_json_ld
    from svejk.build.seo import edition_page_title as _edition_page_title

    page_title = _edition_page_title(
        dnesni_ucet=content.dnesni_ucet,
        meta_description=meta_description,
        first_item_nadpis=content.items[0].nadpis if content.items else "",
        datum_unl=content.datum,
        den=content.den,
        datum_design=datum_label,
    )
    from svejk.build.og_image import (
        OG_HEIGHT,
        OG_WIDTH,
        edition_og_headline,
        edition_og_title,
        og_image_abs_url,
    )

    og_share_title = edition_og_title(content.datum, content.den, locale=loc)
    og_headline = edition_og_headline(
        dnesni_ucet=content.dnesni_ucet,
        first_item_nadpis=content.items[0].nadpis if content.items else "",
        datum_unl=content.datum,
        den=content.den,
        locale=loc,
    )
    og = _og_context(
        site_url=cfg.site_url,
        base_path=base_path,
        title=og_share_title,
        description=meta_description,
        og_type="article",
        image_url=og_image_abs_url(cfg.site_url, base_path, content.datum, locale=loc),
        image_width=OG_WIDTH,
        image_height=OG_HEIGHT,
        image_alt=og_headline,
    )
    schema_headline = _article_headline(
        dnesni_ucet=content.dnesni_ucet,
        meta_description=meta_description,
        first_item_nadpis=content.items[0].nadpis if content.items else "",
        edition_title=edition_title,
    )
    schema_parts: list[dict[str, str | int]] = []
    body_chunks: list[str] = []
    for item in content.items:
        chunk = item.lead.strip()
        if item.mean:
            chunk = f"{chunk} {item.mean.strip()}"
        body_chunks.append(f"{item.nadpis}. {chunk}")
        schema_parts.append(
            {"headline": item.nadpis, "body": chunk, "position": item.num}
        )
    if content.zaver:
        body_chunks.append(content.zaver.strip())
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
        locale=loc,
    )
    for item in content.items:
        if not item.mean_links:
            continue
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
                locale=loc,
            )
            link_pairs.append((phrase, href))
        if link_pairs:
            item.lead = inject_mean_links(item.lead, link_pairs)
            item.mean = inject_mean_links(item.mean, link_pairs)
        if item.kuriozita_links:
            item.kuriozita_nav = resolve_vyznamenani_page_links(
                paths,
                content.datum,
                item.kuriozita_links,
                obdobi=ob,
                schuze=paths.schuze,
                link_mode=link_mode,
                base_path=base_path,
                locale=loc,
            )
    tpl = _jinja_env().get_template("noviny-dlouhe.html")
    if show_locale_notice is None:
        from svejk.build.facts_i18n import has_en_translation

        day_data = read_json(day_path) if day_path.is_file() else {}
        show_locale_notice = loc == "en" and not has_en_translation(day_data)
    return tpl.render(
        content=content,
        schuze=paths.schuze,
        dup_day=dup_day,
        datum_design=datum_design(content.datum, content.den),
        proslo_label=_proslo_board_label(content.proslo, loc),
        zamitnuto_label=_zamitnuto_board_label(content.zamitnuto, loc),
        svejk_svg=svejk_svg,
        inline_css=inline_css,
        css=css,
        css_href=css_href,
        fonts_css_href=fonts_css_href,
        nav=nav,
        newsletter=cfg,
        canonical_url=canonical_url,
        meta_description=meta_description,
        page_title=page_title,
        article_json_ld=json_ld,
        website_json_ld=website_ld,
        **og,
        pivo_tiers=pivo_tiers(loc),
        cookie_privacy_url=soukromi_pages_href(base_path, loc),
        show_locale_notice=show_locale_notice,
        **_locale_ctx(loc, site_url=cfg.site_url, base_path=base_path, page_path=page_path),
        **nav_ctx,
        **_site_footer_ctx(
            base_path,
            obdobi=ob,
            closing_seed=f"{ob}/{paths.schuze}/{content.datum}",
            locale=loc,
        ),
        **favicons,
    )


def _static_asset_url(site_url: str, base_path: str, name: str) -> str:
    base = base_path.rstrip("/")
    prefix = f"{base}/static" if base else "/static"
    return f"{site_url.rstrip('/')}{prefix}/{name}"


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
) -> dict[str, str | int]:
    if image_url:
        og_image_url = image_url
        og_image_width = image_width or _OG_SHARE_SIZE[0]
        og_image_height = image_height or _OG_SHARE_SIZE[1]
        og_image_alt = image_alt or "Poslušně hlásím"
    else:
        image_name, image_w, image_h = _social_image_asset()
        og_image_url = _static_asset_url(site_url, base_path, image_name)
        og_image_width = image_w
        og_image_height = image_h
        og_image_alt = image_alt or "Poslušně hlásím, Švejk"
    return {
        "og_title": title,
        "og_description": description,
        "og_image_url": og_image_url,
        "og_image_width": og_image_width,
        "og_image_height": og_image_height,
        "og_image_alt": og_image_alt,
        "og_type": og_type,
    }


def plain_text_from_content(
    content: DenContent,
    *,
    datum_label: str,
    edition_url: str,
    archive_url: str,
    pivo_url: str,
    proslo_label: str,
    zamitnuto_label: str,
) -> str:
    lines = [
        f"POSLUŠNĚ HLÁSÍM · {datum_label}",
        "",
        f"Stav zápasu: {content.proslo} : {content.zamitnuto}",
        f"{proslo_label} / {zamitnuto_label}",
    ]
    if content.board_note_lines:
        lines.extend(["", *content.board_note_lines])
    for item in content.items:
        lines.extend(
            [
                "",
                f"{item.num:02d} · {item.kick} · {item.stamp}",
                item.nadpis,
                item.lead,
            ]
        )
        if item.mean:
            lines.append(f"Co to znamená pro vás: {item.mean}")
        if item.kuriozita:
            lines.append(item.kuriozita)
        for label, href in item.kuriozita_nav:
            lines.append(f"{label}: {href}")
    zaver = (content.zaver_body or content.zaver or "").strip()
    if zaver:
        key = (content.zaver_key or "").strip()
        lines.extend(["", f"„{key} {zaver}".strip() if key else f"„{zaver}"])
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
    content = build_den_content(day_path, paths)
    edition_href = edition_pages_href(
        edition.obdobi, edition.schuze, edition.datum_unl, base_path
    )
    archive_href = archiv_pages_href(base_path)
    pivo_href = pivo_pages_href(base_path)
    site = site_url.rstrip("/")
    edition_url = f"{site}{edition_href}"
    archive_url = f"{site}{archive_href}"
    pivo_url = f"{site}{pivo_href}"
    datum_label = datum_design(edition.datum_unl, content.den)
    subject = f"Nové vydání · {datum_label}"
    plain = plain_text_from_content(
        content,
        datum_label=datum_label,
        edition_url=edition_url,
        archive_url=archive_url,
        pivo_url=pivo_url,
        proslo_label=_proslo_board_label(content.proslo),
        zamitnuto_label=_zamitnuto_board_label(content.zamitnuto),
    )
    _apply_content_item_links(
        content,
        paths,
        obdobi=edition.obdobi,
        link_mode="pages",
        base_path=base_path,
        site_url=site,
    )
    css = _EMAIL_CSS.read_text(encoding="utf-8")
    tpl = _jinja_env().get_template("noviny-email.html")
    html = tpl.render(
        content=content,
        css=css,
        datum_design=datum_label,
        proslo_label=_proslo_board_label(content.proslo),
        zamitnuto_label=_zamitnuto_board_label(content.zamitnuto),
        edition_url=edition_url,
        archive_url=archive_url,
        pivo_url=pivo_url,
        # PNG místo SVG — Outlook a část Gmailu SVG v <img> nezobrazí.
        svejk_img_url=_static_asset_url(site, base_path, "favicon.png"),
    )
    return subject, plain, html


def render_doi_email_html(
    *,
    site_url: str | None = None,
    base_path: str = "",
    locale: str = "cs",
) -> tuple[str, str, str]:
    """HTML + plain text pro potvrzovací e-mail (double opt-in) v Ecomailu."""
    from svejk.build.nav import soukromi_pages_href
    from svejk.locale import load_strings, localized_path, normalize_locale

    cfg = NewsletterConfig.from_env()
    site = (site_url or cfg.site_url).rstrip("/")
    loc = normalize_locale(locale)
    t = load_strings(loc)
    doi = t["doi"]
    base = base_path.rstrip("/")
    privacy_path = soukromi_pages_href(base, loc)
    confirm_path = localized_path("/potvrzeno/", loc)
    privacy_url = f"{site}{privacy_path}"
    confirm_redirect_url = f"{site}{confirm_path}"
    subject = doi["subject"]
    tpl = _jinja_env().get_template("doi-email.html")
    html = tpl.render(
        locale=loc,
        t=t,
        privacy_url=privacy_url,
        confirm_redirect_url=confirm_redirect_url,
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
    locale: str = "cs",
) -> str:
    css = _CSS.read_text(encoding="utf-8") if inline_css else ""
    if css_href is None:
        css_href = static_css_path(base_path)
    if fonts_css_href is None:
        fonts_css_href = static_fonts_css_path(base_path)
    favicons = static_favicon_paths(base_path)
    cfg = NewsletterConfig.from_env()
    editions = list_site_editions(obdobi)
    if not editions:
        raise ValueError(f"Žádná vydání pro období {obdobi}")

    latest = editions[-1]
    paths = SchuzePaths.create(latest.obdobi, latest.schuze)
    loc = normalize_locale(locale)
    months = archive_by_month(
        paths,
        latest.datum_unl,
        link_mode="pages",
        obdobi=obdobi,
        base_path=base_path,
        locale=loc,
    )
    canonical_url = f"{cfg.site_url.rstrip('/')}{archiv_pages_href(base_path, loc)}"
    page_path = _page_path_from_canonical(canonical_url, cfg.site_url)
    t = load_strings(loc)
    og = _og_context(
        site_url=cfg.site_url,
        base_path=base_path,
        title=t["archive"]["title"] + " · Poslušně hlásím",
        description=t["archive"]["meta"].format(obdobi=obdobi),
    )
    tpl = _jinja_env().get_template("archiv.html")
    return tpl.render(
        obdobi=obdobi,
        archive_months=months,
        canonical_url=canonical_url,
        **og,
        inline_css=inline_css,
        css=css,
        css_href=css_href,
        fonts_css_href=fonts_css_href,
        cookie_privacy_url=soukromi_pages_href(base_path, loc),
        **_locale_ctx(loc, site_url=cfg.site_url, base_path=base_path, page_path=page_path),
        **_site_nav_ctx(obdobi, base_path, locale=loc),
        **_site_footer_ctx(base_path, obdobi=obdobi, closing_seed="archiv", locale=loc),
        **favicons,
    )


def render_404_html(
    obdobi: int,
    *,
    inline_css: bool = False,
    css_href: str | None = None,
    fonts_css_href: str | None = None,
    base_path: str = "",
    locale: str = "cs",
) -> str:
    """Vlastní 404 stránka pro GitHub Pages."""
    css = _CSS.read_text(encoding="utf-8") if inline_css else ""
    if css_href is None:
        css_href = static_css_path(base_path)
    if fonts_css_href is None:
        fonts_css_href = static_fonts_css_path(base_path)
    favicons = static_favicon_paths(base_path)
    cfg = NewsletterConfig.from_env()
    editions = list_site_editions(obdobi)
    if not editions:
        raise ValueError(f"Žádná vydání pro období {obdobi}")

    latest = editions[-1]
    from svejk.timeline import den_v_tydnu

    loc = normalize_locale(locale)
    latest_label = datum_design(
        latest.datum_unl, den_v_tydnu(latest.datum_unl), locale=loc
    )
    base = base_path.rstrip("/")
    home = localized_path("/", loc)
    home = f"{base}{home}" if base else home
    canonical_url = f"{cfg.site_url.rstrip('/')}{home}"
    page_path = _page_path_from_canonical(canonical_url, cfg.site_url)
    tpl = _jinja_env().get_template("404-stranka.html")
    return tpl.render(
        latest_label=latest_label,
        newsletter=cfg,
        canonical_url=canonical_url,
        inline_css=inline_css,
        css=css,
        css_href=css_href,
        fonts_css_href=fonts_css_href,
        cookie_privacy_url=soukromi_pages_href(base_path, loc),
        **_locale_ctx(loc, site_url=cfg.site_url, base_path=base_path, page_path=page_path),
        **_site_nav_ctx(obdobi, base_path, locale=loc),
        **_site_footer_ctx(base_path, obdobi=obdobi, closing_seed="404", locale=loc),
        **favicons,
    )


def render_potvrzeno_html(
    obdobi: int,
    *,
    inline_css: bool = False,
    css_href: str | None = None,
    fonts_css_href: str | None = None,
    base_path: str = "",
    locale: str = "cs",
) -> str:
    """Stránka po potvrzení double opt-in (přesměrování z Ecomailu)."""
    css = _CSS.read_text(encoding="utf-8") if inline_css else ""
    if css_href is None:
        css_href = static_css_path(base_path)
    if fonts_css_href is None:
        fonts_css_href = static_fonts_css_path(base_path)
    favicons = static_favicon_paths(base_path)
    cfg = NewsletterConfig.from_env()
    editions = list_site_editions(obdobi)
    if not editions:
        raise ValueError(f"Žádná vydání pro období {obdobi}")

    latest = editions[-1]
    loc = normalize_locale(locale)
    potvrzeno_path = localized_path("/potvrzeno/", loc)
    canonical_url = f"{cfg.site_url.rstrip('/')}{potvrzeno_path}"
    page_path = _page_path_from_canonical(canonical_url, cfg.site_url)
    from svejk.timeline import den_v_tydnu

    latest_label = datum_design(
        latest.datum_unl, den_v_tydnu(latest.datum_unl), locale=loc
    )
    tpl = _jinja_env().get_template("potvrzeno.html")
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
        cookie_privacy_url=soukromi_pages_href(base_path, loc),
        **_locale_ctx(loc, site_url=cfg.site_url, base_path=base_path, page_path=page_path),
        **_site_nav_ctx(obdobi, base_path, locale=loc),
        **_site_footer_ctx(base_path, obdobi=obdobi, closing_seed="potvrzeno", locale=loc),
        **favicons,
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
    locale: str = "cs",
) -> str | None:
    data = load_vyznamenani(paths, datum_unl, kind)
    if not data:
        return None
    loc = normalize_locale(locale)
    data = localized_vyznamenani_data(data, loc)
    css = _CSS.read_text(encoding="utf-8") if inline_css else ""
    if css_href is None:
        css_href = static_css_path(base_path)
    if fonts_css_href is None:
        fonts_css_href = static_fonts_css_path(base_path)
    favicons = static_favicon_paths(base_path)
    cfg = NewsletterConfig.from_env()
    obdobi = int(data.get("obdobi") or paths.obdobi)
    schuze = int(data.get("schuze") or paths.schuze)
    d = datetime.strptime(datum_unl, "%d.%m.%Y")
    datum_label = vyznamenani_datum_label(datum_unl, loc)
    pocet = int(data.get("pocet") or len(data.get("radky") or []))
    meta = page_meta(kind, pocet=pocet, datum_label=datum_label, locale=loc)
    sibling_kind: VyznamenaniKind | None = (
        "prosli" if kind == "neprosli" else "neprosli" if kind == "prosli" else None
    )
    sibling_data = (
        load_vyznamenani(paths, datum_unl, sibling_kind) if sibling_kind else None
    )
    if link_mode == "pages":
        edition_href = edition_pages_href(obdobi, schuze, datum_unl, base_path, loc)
        canonical_url = (
            f"{cfg.site_url.rstrip('/')}"
            f"{vyznamenani_pages_href(obdobi, schuze, datum_unl, kind, base_path, loc)}"
        )
        sibling_href = (
            vyznamenani_href(
                obdobi,
                schuze,
                datum_unl,
                sibling_kind,
                link_mode="pages",
                base_path=base_path,
                locale=loc,
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
        sibling_label(sibling_kind, loc) if sibling_kind else ""
    )
    page_description = meta["gloss"]
    og_title = f"{meta['title']} · {datum_label} · Poslušně hlásím"
    og = _og_context(
        site_url=cfg.site_url,
        base_path=base_path,
        title=og_title,
        description=page_description,
    )
    votes_by_cislo = _load_votes_by_cislo(paths, datum_unl)
    explain = page_explain(kind, data, votes_by_cislo, locale=loc)
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
        fonts_css_href=fonts_css_href,
        cookie_privacy_url=soukromi_pages_href(base_path, loc),
        **_locale_ctx(loc, site_url=cfg.site_url, base_path=base_path, page_path=page_path),
        **_site_nav_ctx(
            paths.obdobi,
            base_path,
            current_schuze=schuze,
            current_datum=datum_unl,
            locale=loc,
        ),
        **_site_footer_ctx(
            base_path,
            obdobi=paths.obdobi,
            closing_seed=f"vyznamenani/{kind}/{datum_unl}",
            locale=loc,
        ),
        **favicons,
        **og,
    )


def render_vyznamenani_neprosli_html(
    paths: SchuzePaths,
    datum_unl: str,
    **kwargs: Any,
) -> str | None:
    return render_vyznamenani_table_html(paths, datum_unl, "neprosli", **kwargs)


def render_slovnicek_html(
    obdobi: int,
    *,
    inline_css: bool = False,
    css_href: str | None = None,
    fonts_css_href: str | None = None,
    base_path: str = "",
    locale: str = "cs",
) -> str:
    css = _CSS.read_text(encoding="utf-8") if inline_css else ""
    if css_href is None:
        css_href = static_css_path(base_path)
    if fonts_css_href is None:
        fonts_css_href = static_fonts_css_path(base_path)
    favicons = static_favicon_paths(base_path)
    cfg = NewsletterConfig.from_env()
    editions = list_site_editions(obdobi)
    if not editions:
        raise ValueError(f"Žádná vydání pro období {obdobi}")

    loc = normalize_locale(locale)
    canonical_url = f"{cfg.site_url.rstrip('/')}{slovnicek_pages_href(base_path, loc)}"
    page_path = _page_path_from_canonical(canonical_url, cfg.site_url)
    gp = load_strings(loc)["glossary_page"]
    og = _og_context(
        site_url=cfg.site_url,
        base_path=base_path,
        title=gp["title"],
        description=gp["meta"],
    )
    tpl = _jinja_env().get_template("slovnicek-stranka.html")
    slovnicek = [
        {"question": q, "answer": a, "anchor": slovnicek_anchor(q)}
        for q, a in slovnicek_for_locale(loc)
    ]
    return tpl.render(
        slovnicek=slovnicek,
        canonical_url=canonical_url,
        **og,
        inline_css=inline_css,
        css=css,
        css_href=css_href,
        fonts_css_href=fonts_css_href,
        cookie_privacy_url=soukromi_pages_href(base_path, loc),
        **_locale_ctx(loc, site_url=cfg.site_url, base_path=base_path, page_path=page_path),
        **_site_nav_ctx(obdobi, base_path, locale=loc),
        **_site_footer_ctx(base_path, obdobi=obdobi, closing_seed="slovnicek", locale=loc),
        **favicons,
    )


def render_pivo_html(
    obdobi: int,
    *,
    inline_css: bool = False,
    css_href: str | None = None,
    fonts_css_href: str | None = None,
    base_path: str = "",
    locale: str = "cs",
) -> str:
    css = _CSS.read_text(encoding="utf-8") if inline_css else ""
    if css_href is None:
        css_href = static_css_path(base_path)
    if fonts_css_href is None:
        fonts_css_href = static_fonts_css_path(base_path)
    favicons = static_favicon_paths(base_path)
    cfg = NewsletterConfig.from_env()
    editions = list_site_editions(obdobi)
    if not editions:
        raise ValueError(f"Žádná vydání pro období {obdobi}")

    loc = normalize_locale(locale)
    canonical_url = f"{cfg.site_url.rstrip('/')}{pivo_pages_href(base_path, loc)}"
    page_path = _page_path_from_canonical(canonical_url, cfg.site_url)
    bp = load_strings(loc)["beer_page"]
    og = _og_context(
        site_url=cfg.site_url,
        base_path=base_path,
        title=bp["title"],
        description=bp["meta"],
    )
    tpl = _jinja_env().get_template("pivo-stranka.html")
    return tpl.render(
        canonical_url=canonical_url,
        **og,
        pivo_tiers=pivo_tiers(loc),
        pivo_menu_pay=True,
        stripe_portal_href=_stripe_url("STRIPE_PORTAL_URL", STRIPE_PORTAL_URL),
        inline_css=inline_css,
        css=css,
        css_href=css_href,
        fonts_css_href=fonts_css_href,
        cookie_privacy_url=soukromi_pages_href(base_path, loc),
        **_locale_ctx(loc, site_url=cfg.site_url, base_path=base_path, page_path=page_path),
        **_site_nav_ctx(obdobi, base_path, locale=loc),
        **_site_footer_ctx(base_path, obdobi=obdobi, closing_seed="pivo", locale=loc),
        **favicons,
    )


def render_dekuju_html(
    obdobi: int,
    *,
    inline_css: bool = False,
    css_href: str | None = None,
    fonts_css_href: str | None = None,
    base_path: str = "",
    locale: str = "cs",
) -> str:
    """Stránka po úspěšné platbě (redirect ze Stripe)."""
    css = _CSS.read_text(encoding="utf-8") if inline_css else ""
    if css_href is None:
        css_href = static_css_path(base_path)
    if fonts_css_href is None:
        fonts_css_href = static_fonts_css_path(base_path)
    favicons = static_favicon_paths(base_path)
    cfg = NewsletterConfig.from_env()
    editions = list_site_editions(obdobi)
    if not editions:
        raise ValueError(f"Žádná vydání pro období {obdobi}")

    loc = normalize_locale(locale)
    canonical_url = f"{cfg.site_url.rstrip('/')}{dekuju_pages_href(base_path, loc)}"
    page_path = _page_path_from_canonical(canonical_url, cfg.site_url)
    tpl = _jinja_env().get_template("dekuju-stranka.html")
    return tpl.render(
        canonical_url=canonical_url,
        inline_css=inline_css,
        css=css,
        css_href=css_href,
        fonts_css_href=fonts_css_href,
        cookie_privacy_url=soukromi_pages_href(base_path, loc),
        **_locale_ctx(loc, site_url=cfg.site_url, base_path=base_path, page_path=page_path),
        **_site_nav_ctx(obdobi, base_path, locale=loc),
        **_site_footer_ctx(base_path, obdobi=obdobi, closing_seed="dekuju", locale=loc),
        **favicons,
    )


def render_soukromi_html(
    obdobi: int,
    *,
    inline_css: bool = False,
    css_href: str | None = None,
    fonts_css_href: str | None = None,
    base_path: str = "",
    locale: str = "cs",
) -> str:
    """Zásady ochrany osobních údajů (odběr, analytika, platby)."""
    css = _CSS.read_text(encoding="utf-8") if inline_css else ""
    if css_href is None:
        css_href = static_css_path(base_path)
    if fonts_css_href is None:
        fonts_css_href = static_fonts_css_path(base_path)
    favicons = static_favicon_paths(base_path)
    cfg = NewsletterConfig.from_env()
    loc = normalize_locale(locale)
    canonical_url = f"{cfg.site_url.rstrip('/')}{soukromi_pages_href(base_path, loc)}"
    page_path = _page_path_from_canonical(canonical_url, cfg.site_url)
    pp = load_strings(loc)["privacy_page"]
    og = _og_context(
        site_url=cfg.site_url,
        base_path=base_path,
        title=pp["title"],
        description=pp["meta"],
    )
    tpl = _jinja_env().get_template("soukromi.html")
    return tpl.render(
        site_url=cfg.site_url.rstrip("/"),
        contact_email=cfg.contact_email,
        canonical_url=canonical_url,
        **og,
        inline_css=inline_css,
        css=css,
        css_href=css_href,
        fonts_css_href=fonts_css_href,
        cookie_privacy_url=soukromi_pages_href(base_path, loc),
        **_locale_ctx(loc, site_url=cfg.site_url, base_path=base_path, page_path=page_path),
        **_site_nav_ctx(obdobi, base_path, locale=loc),
        **_site_footer_ctx(
            base_path,
            obdobi=obdobi,
            active_page="privacy",
            closing_seed="soukromi",
            locale=loc,
        ),
        **favicons,
    )


def render_podminky_html(
    obdobi: int,
    *,
    inline_css: bool = False,
    css_href: str | None = None,
    fonts_css_href: str | None = None,
    base_path: str = "",
    locale: str = "cs",
) -> str:
    """Podmínky používání webu, odběru a dobrovolných příspěvků."""
    css = _CSS.read_text(encoding="utf-8") if inline_css else ""
    if css_href is None:
        css_href = static_css_path(base_path)
    if fonts_css_href is None:
        fonts_css_href = static_fonts_css_path(base_path)
    favicons = static_favicon_paths(base_path)
    cfg = NewsletterConfig.from_env()
    loc = normalize_locale(locale)
    canonical_url = f"{cfg.site_url.rstrip('/')}{podminky_pages_href(base_path, loc)}"
    page_path = _page_path_from_canonical(canonical_url, cfg.site_url)
    tp = load_strings(loc)["terms_page"]
    og = _og_context(
        site_url=cfg.site_url,
        base_path=base_path,
        title=tp["title"],
        description=tp["meta"],
    )
    tpl = _jinja_env().get_template("podminky-stranka.html")
    return tpl.render(
        site_url=cfg.site_url.rstrip("/"),
        contact_email=cfg.contact_email,
        canonical_url=canonical_url,
        **og,
        inline_css=inline_css,
        css=css,
        css_href=css_href,
        fonts_css_href=fonts_css_href,
        cookie_privacy_url=soukromi_pages_href(base_path, loc),
        **_locale_ctx(loc, site_url=cfg.site_url, base_path=base_path, page_path=page_path),
        **_site_nav_ctx(obdobi, base_path, locale=loc),
        **_site_footer_ctx(
            base_path,
            obdobi=obdobi,
            active_page="terms",
            closing_seed="podminky",
            locale=loc,
        ),
        **favicons,
    )


def render_podpora_html(
    obdobi: int,
    *,
    inline_css: bool = False,
    css_href: str | None = None,
    fonts_css_href: str | None = None,
    base_path: str = "",
    locale: str = "cs",
) -> str:
    """Zákaznická podpora — kontakt, platby, odběr."""
    css = _CSS.read_text(encoding="utf-8") if inline_css else ""
    if css_href is None:
        css_href = static_css_path(base_path)
    if fonts_css_href is None:
        fonts_css_href = static_fonts_css_path(base_path)
    favicons = static_favicon_paths(base_path)
    cfg = NewsletterConfig.from_env()
    loc = normalize_locale(locale)
    canonical_url = f"{cfg.site_url.rstrip('/')}{podpora_pages_href(base_path, loc)}"
    page_path = _page_path_from_canonical(canonical_url, cfg.site_url)
    sp = load_strings(loc)["support_page"]
    og = _og_context(
        site_url=cfg.site_url,
        base_path=base_path,
        title=sp["title"],
        description=sp["meta"],
    )
    tpl = _jinja_env().get_template("podpora-stranka.html")
    return tpl.render(
        site_url=cfg.site_url.rstrip("/"),
        contact_email=cfg.contact_email,
        canonical_url=canonical_url,
        **og,
        inline_css=inline_css,
        css=css,
        css_href=css_href,
        fonts_css_href=fonts_css_href,
        cookie_privacy_url=soukromi_pages_href(base_path, loc),
        **_locale_ctx(loc, site_url=cfg.site_url, base_path=base_path, page_path=page_path),
        **_site_nav_ctx(obdobi, base_path, locale=loc),
        **_site_footer_ctx(
            base_path,
            obdobi=obdobi,
            active_page="support",
            closing_seed="podpora",
            locale=loc,
        ),
        **favicons,
    )
