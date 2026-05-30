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


def static_css_path(base_path: str = "") -> str:
    base = base_path.rstrip("/")
    path = "/static/noviny-dlouhe.css"
    return f"{base}{path}" if base else path


def _proslo_label(n: int) -> str:
    if n == 1:
        return "věc<br/>schválili"
    if 2 <= n <= 4:
        return "věci<br/>schválili"
    return "věcí<br/>schválili"


def _zamitnuto_label(n: int) -> str:
    if n == 1:
        return "návrh<br/>zamítli"
    if 2 <= n <= 4:
        return "návrhy<br/>zamítli"
    return "návrhů<br/>zamítli"


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
    tpl = _jinja_env().get_template("noviny-dlouhe.html")
    return tpl.render(
        content=content,
        datum_design=datum_design(content.datum, content.den),
        proslo_label=_proslo_label(content.proslo),
        zamitnuto_label=_zamitnuto_label(content.zamitnuto),
        inline_css=inline_css,
        css=css,
        css_href=css_href,
        nav=nav,
    )
