"""HTML výstup novin-dlouhe (design varianta C)."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from svejk.build.day_content import DenContent, datum_design
from svejk.build.nav import edition_nav
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
    tpl = _jinja_env().get_template("noviny-dlouhe.html")
    return tpl.render(
        content=content,
        datum_design=datum_design(content.datum, content.den),
        proslo_label=_proslo_board_label(content.proslo),
        zamitnuto_label=_zamitnuto_board_label(content.zamitnuto),
        svejk_svg=svejk_svg,
        inline_css=inline_css,
        css=css,
        css_href=css_href,
        nav=nav,
    )
