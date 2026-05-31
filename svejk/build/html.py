"""HTML výstup novin-dlouhe (design varianta C)."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from svejk.build.day_content import DenContent, datum_design
from svejk.build.nav import edition_nav, list_obdobi_editions
from svejk.newsletter.config import NewsletterConfig
from svejk.paths import SchuzePaths

_TEMPLATES = Path(__file__).resolve().parent.parent / "templates"
_STATIC = Path(__file__).resolve().parent.parent / "static"
_CSS = _STATIC / "noviny-dlouhe.css"
_SVEJK_SVG = _STATIC / "svejk.svg"


def static_css_path(base_path: str = "", *, version: str | None = None) -> str:
    base = base_path.rstrip("/")
    path = "/static/noviny-dlouhe.css"
    if version:
        path = f"{path}?v={version}"
    return f"{base}{path}" if base else path


def css_asset_version() -> str:
    import hashlib

    return hashlib.sha256(_CSS.read_bytes()).hexdigest()[:10]


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


def _jinja_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATES)),
        autoescape=select_autoescape(["html"]),
    )


def render_den_html(
    content: DenContent,
    paths: SchuzePaths,
    day_path: Path,
    *,
    inline_css: bool = True,
    css_href: str | None = None,
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
    if not meta_description:
        from svejk.build.seo import meta_description as _meta_description

        raw = (content.dnesni_ucet or "").strip()
        if not raw and content.items:
            raw = content.items[0].nadpis
        meta_description = _meta_description(raw) if raw else (
            f"Deník z Poslanecké sněmovny — {datum_design(content.datum, content.den)}."
        )
    if not canonical_url:
        from svejk.build.nav import edition_pages_href

        href = edition_pages_href(
            ob, paths.schuze, content.datum, base_path
        )
        canonical_url = f"{cfg.site_url.rstrip('/')}{href}"
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
        nav=nav,
        newsletter=cfg,
        canonical_url=canonical_url,
        meta_description=meta_description,
        article_json_ld=json_ld,
    )
