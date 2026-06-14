"""HTML výstup novin-dlouhe (design varianta C)."""

from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from svejk.build.day_content import DenContent, build_den_content, datum_design
from svejk.build.glossary_markup import glossary_markup
from svejk.glossary import SLOVNIČEK
from svejk.build.publish import list_site_editions
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


def pivo_tiers() -> list[dict[str, Any]]:
    """Hospodský ceník — tři položky, pay_href vede na Stripe Payment Links."""
    return [
        {
            "id": "velke",
            "kind": "once",
            "name": "Velké pivo",
            "price": "65 Kč",
            "note": "starý osvědčený prostředek proti trudnomyslnosti",
            "cta": "Přispět jednorázově",
            "pay_href": _stripe_url("STRIPE_PIVO_URL", STRIPE_PIVO_URL),
        },
        {
            "id": "rum",
            "kind": "once",
            "name": "Rum",
            "price": "95 Kč",
            "note": "Kořalku nepiju, jen rum.",
            "cta": "Přispět jednorázově",
            "pay_href": _stripe_url("STRIPE_RUM_URL", STRIPE_RUM_URL),
        },
        {
            "id": "stamgast",
            "kind": "monthly",
            "name": "Štamgast",
            "price": "65 Kč měsíčně",
            "note": "pro ty, kdo chodí pravidelně, i když zrovna není poplach",
            "cta": "Stát se Štamgastem",
            "pay_href": _stripe_url("STRIPE_STAMGAST_URL", STRIPE_STAMGAST_URL),
            "highlight": True,
        },
    ]


from svejk.build.vyznamenani_neprosli import (
    VyznamenaniKind,
    inject_mean_links,
    load_vyznamenani,
    page_explain,
    page_meta,
    resolve_vyznamenani_page_links,
    table_rows,
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


def _proslo_board_label(n: int) -> str:
    if n == 1:
        return "věc schválili"
    if 2 <= n <= 4:
        return "věci schválili"
    return "věcí schválili"


def _zamitnuto_board_label(n: int) -> str:
    if n == 1:
        return "návrh zamítli"
    if 2 <= n <= 4:
        return "návrhy zamítli"
    return "návrhů zamítli"


def _proslo_score_phrase(n: int) -> str:
    if n == 1:
        return "1 věc prošla"
    if 2 <= n <= 4:
        return f"{n} věci prošly"
    return f"{n} věcí prošlo"


def _zamitnuto_score_phrase(n: int) -> str:
    return f"{n} zamítnuto"


def _board_score_summary(proslo: int, zamitnuto: int) -> tuple[str, str]:
    main = (
        f"Dnešní skóre: {_proslo_score_phrase(proslo)}, "
        f"{_zamitnuto_score_phrase(zamitnuto)}."
    )
    return main, "(Klikni pro detail hlasování)"


def _board_score_ctx(proslo: int, zamitnuto: int) -> dict[str, str]:
    summary, hint = _board_score_summary(proslo, zamitnuto)
    return {
        "board_summary": summary,
        "board_summary_hint": hint,
    }


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
            item.kuriozita_nav = [
                (label, _abs_href(href, site_url))
                for label, href in resolve_vyznamenani_page_links(
                    paths,
                    content.datum,
                    item.kuriozita_links,
                    obdobi=obdobi,
                    schuze=paths.schuze,
                    link_mode=link_mode,
                    base_path=base_path,
                )
            ]


def _jinja_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES)),
        autoescape=select_autoescape(["html"]),
    )
    env.filters["split_paragraphs"] = _split_paragraphs
    env.filters["glossary"] = glossary_markup
    return env


_FOOTER_CLOSINGS = (
    "Poslušně hlásím, že dnešní vydání končí. Poslanci šli domů a my taky.",
    "V hospodě už zavírají. Další vydání zase po schůzi.",
    "Poslušně hlásím, že demokracie je běh na dlouhou trať a někdy i na dlouhou schůzi.",
    "Poslanci odešli, stenozáznam zůstal.",
)

_DEFAULT_FOOTER_CONTACT = "svejk@poslusnehlasim.cz"


def _footer_closing(seed: str) -> str:
    idx = sum(ord(c) for c in seed) % len(_FOOTER_CLOSINGS)
    return _FOOTER_CLOSINGS[idx]


def _footer_stats_line(obdobi: int) -> str:
    editions = list_site_editions(obdobi)
    n_editions = len(editions)
    n_schuze = len({e.schuze for e in editions})
    if n_schuze == 1:
        schuze_part = "1 schůze"
    elif 2 <= n_schuze <= 4:
        schuze_part = f"{n_schuze} schůze"
    else:
        schuze_part = f"{n_schuze} schůzí"
    return f"{n_editions} vydání • {schuze_part} • 100 % veřejná data"


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
        "support_href": podpora_pages_href(base_path),
        "footer_closing": _footer_closing(seed),
        "footer_stats": _footer_stats_line(obdobi),
        "footer_contact_email": contact,
        "footer_active_page": active_page,
    }


def _edition_back_label(datum_unl: str) -> str:
    d = datetime.strptime(datum_unl, "%d.%m.%Y")
    return f"{d.day}. {d.month}. {d.year}"


def _site_nav_ctx(obdobi: int, base_path: str = "") -> dict[str, str]:
    editions = list_site_editions(obdobi)
    latest_href = ""
    edition_back_href = ""
    edition_back_label = ""
    if editions:
        latest = editions[-1]
        latest_href = edition_pages_href(
            latest.obdobi, latest.schuze, latest.datum_unl, base_path
        )
        edition_back_href = latest_href
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
    return env.get_template("site-footer.html").render(
        **_site_footer_ctx(base_path, obdobi=obdobi, closing_seed="snapshot")
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
        ) or f"Deník z Poslanecké sněmovny, {datum_design(content.datum, content.den)}."
    if not canonical_url:
        href = edition_pages_href(ob, paths.schuze, content.datum, base_path)
        canonical_url = f"{cfg.site_url.rstrip('/')}{href}"
    nav_ctx = _site_nav_ctx(ob, base_path) if link_mode == "pages" else {
        "archive_href": None,
        "latest_href": None,
        "slovnicek_href": None,
        "pivo_href": None,
    }
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

    og_share_title = edition_og_title(content.datum, content.den)
    og_headline = edition_og_headline(
        dnesni_ucet=content.dnesni_ucet,
        first_item_nadpis=content.items[0].nadpis if content.items else "",
        datum_unl=content.datum,
        den=content.den,
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
            )
    tpl = _jinja_env().get_template("noviny-dlouhe.html")
    return tpl.render(
        content=content,
        schuze=paths.schuze,
        dup_day=dup_day,
        datum_design=datum_design(content.datum, content.den),
        proslo_label=_proslo_board_label(content.proslo),
        zamitnuto_label=_zamitnuto_board_label(content.zamitnuto),
        **_board_score_ctx(content.proslo, content.zamitnuto),
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
        pivo_tiers=pivo_tiers(),
        **nav_ctx,
        **_site_footer_ctx(
            base_path,
            obdobi=ob,
            closing_seed=f"{ob}/{paths.schuze}/{content.datum}",
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
    proslo_label: str,
    zamitnuto_label: str,
) -> str:
    summary, hint = _board_score_summary(content.proslo, content.zamitnuto)
    lines = [
        f"POSLUŠNĚ HLÁSÍM · {datum_label}",
        "",
        f"Stav zápasu: {content.proslo} : {content.zamitnuto}",
        f"{proslo_label} / {zamitnuto_label}",
        summary,
        hint,
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
            f"Archiv: {archive_url}",
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
        **_board_score_ctx(content.proslo, content.zamitnuto),
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
) -> tuple[str, str, str]:
    """HTML + plain text pro potvrzovací e-mail (double opt-in) v Ecomailu."""
    cfg = NewsletterConfig.from_env()
    site = (site_url or cfg.site_url).rstrip("/")
    subject = "Poslušně hlásím: potvrď odběr novinek"
    tpl = _jinja_env().get_template("doi-email.html")
    html = tpl.render(
        privacy_url=cfg.privacy_url,
        confirm_redirect_url=cfg.confirm_redirect_url,
    )
    plain = "\n".join(
        [
            "POSLUŠNĚ HLÁSÍM: potvrď odběr novinek",
            "",
            "Deník sněmovny už čeká. Ještě je ale třeba",
            "jeden krok. Potvrď, že e-mail patří opravdu tobě",
            "a chceš deník odebírat.",
            "",
            "Poslušně hlásím, že bez potvrzení ti nemůžeme poslat ani řádku. Klikni a je vyřízeno.",
            "",
            "Potvrď odběr kliknutím na odkaz v HTML verzi tohoto e-mailu.",
            "",
            f"Po potvrzení tě přesměrujeme na: {cfg.confirm_redirect_url}",
            "Pokud tento e-mail přišel omylem, není třeba nic dělat.",
            f"Co děláme s e-mailovou adresou: {cfg.privacy_url}",
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
    months = archive_by_month(
        paths,
        latest.datum_unl,
        link_mode="pages",
        obdobi=obdobi,
        base_path=base_path,
    )
    canonical_url = f"{cfg.site_url.rstrip('/')}{archiv_pages_href(base_path)}"
    og = _og_context(
        site_url=cfg.site_url,
        base_path=base_path,
        title="Archiv vydání · Poslušně hlásím",
        description=f"Všechna vydání deníku z Poslanecké sněmovny, období {obdobi}.",
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
        **_site_nav_ctx(obdobi, base_path),
        **_site_footer_ctx(base_path, obdobi=obdobi, closing_seed="archiv"),
        **favicons,
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

    latest_label = datum_design(latest.datum_unl, den_v_tydnu(latest.datum_unl))
    base = base_path.rstrip("/")
    home = f"{base}/" if base else "/"
    canonical_url = f"{cfg.site_url.rstrip('/')}{home}"
    tpl = _jinja_env().get_template("404-stranka.html")
    return tpl.render(
        latest_label=latest_label,
        newsletter=cfg,
        canonical_url=canonical_url,
        inline_css=inline_css,
        css=css,
        css_href=css_href,
        fonts_css_href=fonts_css_href,
        **_site_nav_ctx(obdobi, base_path),
        **_site_footer_ctx(base_path, obdobi=obdobi, closing_seed="404"),
        **favicons,
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
    canonical_url = f"{cfg.site_url.rstrip('/')}/potvrzeno/"
    from svejk.timeline import den_v_tydnu

    latest_label = datum_design(latest.datum_unl, den_v_tydnu(latest.datum_unl))
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
        **_site_nav_ctx(obdobi, base_path),
        **_site_footer_ctx(base_path, obdobi=obdobi, closing_seed="potvrzeno"),
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
) -> str | None:
    data = load_vyznamenani(paths, datum_unl, kind)
    if not data:
        return None
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
    datum_label = f"{d.day}. {d.month}. {d.year}"
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
        canonical_url = (
            f"{cfg.site_url.rstrip('/')}"
            f"{vyznamenani_pages_href(obdobi, schuze, datum_unl, kind, base_path)}"
        )
        sibling_href = (
            vyznamenani_href(
                obdobi, schuze, datum_unl, sibling_kind, link_mode="pages", base_path=base_path
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
    sibling_label = (
        "Koho Sněmovna doporučila"
        if sibling_kind == "prosli"
        else "Kdo neprošel"
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
    explain = page_explain(kind, data, votes_by_cislo)
    tpl = _jinja_env().get_template("vyznamenani-tabulka-stranka.html")
    return tpl.render(
        rows=table_rows(data, kind=kind, votes_by_cislo=votes_by_cislo),
        kind=kind,
        show_vote_threshold=bool(votes_by_cislo),
        page_explain=explain,
        datum_label=datum_label,
        edition_href=edition_href,
        sibling_href=sibling_href if sibling_data else "",
        sibling_label=sibling_label if sibling_data else "",
        page_title=meta["title"],
        page_gloss=meta["gloss"],
        page_note=meta["note"],
        page_description=page_description,
        canonical_url=canonical_url,
        inline_css=inline_css,
        css=css,
        css_href=css_href,
        fonts_css_href=fonts_css_href,
        **_site_nav_ctx(paths.obdobi, base_path),
        **_site_footer_ctx(
            base_path,
            obdobi=paths.obdobi,
            closing_seed=f"vyznamenani/{kind}/{datum_unl}",
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
    canonical_url = f"{cfg.site_url.rstrip('/')}{slovnicek_pages_href(base_path)}"
    og = _og_context(
        site_url=cfg.site_url,
        base_path=base_path,
        title="Švejkův slovníček · Poslušně hlásím",
        description="Krátké vysvětlení pojmů z Poslanecké sněmovny pro lidi, kteří politiku běžně nesledují.",
    )
    tpl = _jinja_env().get_template("slovnicek-stranka.html")
    return tpl.render(
        slovnicek=SLOVNIČEK,
        canonical_url=canonical_url,
        **og,
        inline_css=inline_css,
        css=css,
        css_href=css_href,
        fonts_css_href=fonts_css_href,
        **_site_nav_ctx(obdobi, base_path),
        **_site_footer_ctx(base_path, obdobi=obdobi, closing_seed="slovnicek"),
        **favicons,
    )


def render_pivo_html(
    obdobi: int,
    *,
    inline_css: bool = False,
    css_href: str | None = None,
    fonts_css_href: str | None = None,
    base_path: str = "",
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
    canonical_url = f"{cfg.site_url.rstrip('/')}{pivo_pages_href(base_path)}"
    og = _og_context(
        site_url=cfg.site_url,
        base_path=base_path,
        title="Kup Švejkovi pivo · Poslušně hlásím",
        description="Dobrovolný příspěvek na provoz deníku z Poslanecké sněmovny. Noviny zůstávají zdarma.",
    )
    tpl = _jinja_env().get_template("pivo-stranka.html")
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
        **_site_nav_ctx(obdobi, base_path),
        **_site_footer_ctx(base_path, obdobi=obdobi, closing_seed="pivo"),
        **favicons,
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
    canonical_url = f"{cfg.site_url.rstrip('/')}{dekuju_pages_href(base_path)}"
    tpl = _jinja_env().get_template("dekuju-stranka.html")
    return tpl.render(
        canonical_url=canonical_url,
        inline_css=inline_css,
        css=css,
        css_href=css_href,
        fonts_css_href=fonts_css_href,
        **_site_nav_ctx(obdobi, base_path),
        **_site_footer_ctx(base_path, obdobi=obdobi, closing_seed="dekuju"),
        **favicons,
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
    css = _CSS.read_text(encoding="utf-8") if inline_css else ""
    if css_href is None:
        css_href = static_css_path(base_path)
    if fonts_css_href is None:
        fonts_css_href = static_fonts_css_path(base_path)
    favicons = static_favicon_paths(base_path)
    cfg = NewsletterConfig.from_env()
    canonical_url = f"{cfg.site_url.rstrip('/')}{soukromi_pages_href(base_path)}"
    og = _og_context(
        site_url=cfg.site_url,
        base_path=base_path,
        title="Zásady ochrany osobních údajů · Poslušně hlásím",
        description="Jak Poslušně hlásím zpracovává e-mail, cookies, analytiku a platby.",
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
        **_site_nav_ctx(obdobi, base_path),
        **_site_footer_ctx(
            base_path,
            obdobi=obdobi,
            active_page="privacy",
            closing_seed="soukromi",
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
) -> str:
    """Podmínky používání webu, odběru a dobrovolných příspěvků."""
    css = _CSS.read_text(encoding="utf-8") if inline_css else ""
    if css_href is None:
        css_href = static_css_path(base_path)
    if fonts_css_href is None:
        fonts_css_href = static_fonts_css_path(base_path)
    favicons = static_favicon_paths(base_path)
    cfg = NewsletterConfig.from_env()
    canonical_url = f"{cfg.site_url.rstrip('/')}{podminky_pages_href(base_path)}"
    og = _og_context(
        site_url=cfg.site_url,
        base_path=base_path,
        title="Podmínky používání · Poslušně hlásím",
        description="Pravidla používání webu Poslušně hlásím, odběru novinek a dobrovolných příspěvků.",
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
        **_site_nav_ctx(obdobi, base_path),
        **_site_footer_ctx(
            base_path,
            obdobi=obdobi,
            active_page="terms",
            closing_seed="podminky",
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
) -> str:
    """Zákaznická podpora — kontakt, platby, odběr."""
    css = _CSS.read_text(encoding="utf-8") if inline_css else ""
    if css_href is None:
        css_href = static_css_path(base_path)
    if fonts_css_href is None:
        fonts_css_href = static_fonts_css_path(base_path)
    favicons = static_favicon_paths(base_path)
    cfg = NewsletterConfig.from_env()
    canonical_url = f"{cfg.site_url.rstrip('/')}{podpora_pages_href(base_path)}"
    og = _og_context(
        site_url=cfg.site_url,
        base_path=base_path,
        title="Zákaznická podpora · Poslušně hlásím",
        description="Kontakt a pomoc s odběrem novinek, platbami a webem Poslušně hlásím.",
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
        **_site_nav_ctx(obdobi, base_path),
        **_site_footer_ctx(
            base_path,
            obdobi=obdobi,
            active_page="support",
            closing_seed="podpora",
        ),
        **favicons,
    )
