"""HTML výstup novin-dlouhe (design varianta C)."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from svejk.build.day_content import DenContent, build_den_content, datum_design
from svejk.build.glossary_markup import glossary_markup
from svejk.glossary import SLOVNIČEK
from svejk.build.nav import (
    Edition,
    archiv_pages_href,
    archive_by_month,
    edition_nav,
    edition_pages_href,
    list_obdobi_editions,
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


def _split_paragraphs(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p for p in parts if p]


def _jinja_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES)),
        autoescape=select_autoescape(["html"]),
    )
    env.filters["split_paragraphs"] = _split_paragraphs
    env.filters["glossary"] = glossary_markup
    return env


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
    dup_day = sum(1 for e in list_obdobi_editions(ob) if e.datum_unl == content.datum) > 1
    cfg = NewsletterConfig.from_env()
    if fonts_css_href is None:
        fonts_css_href = static_fonts_css_path(base_path)
        if link_mode == "file":
            # lokální náhledy v processed/ — fonty natáhnou z produkčního webu
            fonts_css_href = f"{cfg.site_url.rstrip('/')}{fonts_css_href}"
    if not meta_description:
        from svejk.build.seo import meta_description as _meta_description

        raw = (content.dnesni_ucet or "").strip()
        if not raw and content.items:
            raw = content.items[0].nadpis
        meta_description = _meta_description(raw) if raw else (
            f"Deník z Poslanecké sněmovny, {datum_design(content.datum, content.den)}."
        )
    if not canonical_url:
        href = edition_pages_href(ob, paths.schuze, content.datum, base_path)
        canonical_url = f"{cfg.site_url.rstrip('/')}{href}"
    archive_href = archiv_pages_href(base_path) if link_mode == "pages" else None
    title = f"Poslušně hlásím · {datum_design(content.datum, content.den)}"
    from svejk.build.seo import article_json_ld as _article_json_ld

    json_ld = _article_json_ld(
        headline=title,
        description=meta_description,
        url=canonical_url,
        date_unl=content.datum,
        site_url=cfg.site_url,
    )
    tpl = _jinja_env().get_template("noviny-dlouhe.html")
    return tpl.render(
        content=content,
        schuze=paths.schuze,
        dup_day=dup_day,
        datum_design=datum_design(content.datum, content.den),
        proslo_label=_proslo_board_label(content.proslo),
        zamitnuto_label=_zamitnuto_board_label(content.zamitnuto),
        svejk_svg=svejk_svg,
        inline_css=inline_css,
        css=css,
        css_href=css_href,
        fonts_css_href=fonts_css_href,
        nav=nav,
        newsletter=cfg,
        canonical_url=canonical_url,
        meta_description=meta_description,
        article_json_ld=json_ld,
        archive_href=archive_href,
        slovnicek=SLOVNIČEK,
        **favicons,
    )


def _static_asset_url(site_url: str, base_path: str, name: str) -> str:
    base = base_path.rstrip("/")
    prefix = f"{base}/static" if base else "/static"
    return f"{site_url.rstrip('/')}{prefix}/{name}"


def plain_text_from_content(
    content: DenContent,
    *,
    datum_label: str,
    edition_url: str,
    archive_url: str,
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
    zaver = (content.zaver_body or content.zaver or "").strip()
    if zaver:
        key = (content.zaver_key or "").strip()
        lines.extend(["", f"„{key} {zaver}".strip() if key else f"„{zaver}"])
    lines.extend(
        [
            "",
            f"Číst celé vydání: {edition_url}",
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
    site = site_url.rstrip("/")
    edition_url = f"{site}{edition_href}"
    archive_url = f"{site}{archive_href}"
    datum_label = datum_design(edition.datum_unl, content.den)
    subject = f"Nové vydání · {datum_label}"
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
    )
    plain = plain_text_from_content(
        content,
        datum_label=datum_label,
        edition_url=edition_url,
        archive_url=archive_url,
        proslo_label=_proslo_board_label(content.proslo),
        zamitnuto_label=_zamitnuto_board_label(content.zamitnuto),
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
    editions = list_obdobi_editions(obdobi)
    if not editions:
        raise ValueError(f"Žádná vydání pro období {obdobi}")

    latest = editions[-1]
    paths = SchuzePaths.create(latest.obdobi, latest.schuze)
    months = archive_by_month(
        paths,
        "",
        link_mode="pages",
        obdobi=obdobi,
        base_path=base_path,
    )
    latest_href = edition_pages_href(
        latest.obdobi, latest.schuze, latest.datum_unl, base_path
    )
    canonical_url = f"{cfg.site_url.rstrip('/')}{archiv_pages_href(base_path)}"
    tpl = _jinja_env().get_template("archiv.html")
    return tpl.render(
        obdobi=obdobi,
        archive_months=months,
        latest_href=latest_href,
        canonical_url=canonical_url,
        inline_css=inline_css,
        css=css,
        css_href=css_href,
        fonts_css_href=fonts_css_href,
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
    editions = list_obdobi_editions(obdobi)
    if not editions:
        raise ValueError(f"Žádná vydání pro období {obdobi}")

    latest = editions[-1]
    latest_href = edition_pages_href(
        latest.obdobi, latest.schuze, latest.datum_unl, base_path
    )
    archive_href = archiv_pages_href(base_path)
    canonical_url = f"{cfg.site_url.rstrip('/')}/potvrzeno/"
    from svejk.timeline import den_v_tydnu

    latest_label = datum_design(latest.datum_unl, den_v_tydnu(latest.datum_unl))
    tpl = _jinja_env().get_template("potvrzeno.html")
    return tpl.render(
        latest_href=latest_href,
        latest_label=latest_label,
        archive_href=archive_href,
        site_url=cfg.site_url.rstrip("/"),
        privacy_url=cfg.privacy_url,
        contact_email=cfg.contact_email,
        canonical_url=canonical_url,
        inline_css=inline_css,
        css=css,
        css_href=css_href,
        fonts_css_href=fonts_css_href,
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
    """Stránka ochrany osobních údajů u odběru novinek."""
    css = _CSS.read_text(encoding="utf-8") if inline_css else ""
    if css_href is None:
        css_href = static_css_path(base_path)
    if fonts_css_href is None:
        fonts_css_href = static_fonts_css_path(base_path)
    favicons = static_favicon_paths(base_path)
    cfg = NewsletterConfig.from_env()
    archive_href = archiv_pages_href(base_path)
    canonical_url = f"{cfg.site_url.rstrip('/')}/soukromi/"
    tpl = _jinja_env().get_template("soukromi.html")
    return tpl.render(
        archive_href=archive_href,
        site_url=cfg.site_url.rstrip("/"),
        contact_email=cfg.contact_email,
        canonical_url=canonical_url,
        inline_css=inline_css,
        css=css,
        css_href=css_href,
        fonts_css_href=fonts_css_href,
        **favicons,
    )
