"""Export statického webu pro GitHub Pages."""

from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from svejk.build.day_content import build_den_content
from svejk.build.html import css_asset_version, render_den_html, static_css_path
from svejk.build.nav import (
    clear_edition_cache,
    edition_pages_href,
    list_obdobi_editions,
    resolve_edition,
)
from svejk.paths import SchuzePaths, processed_root

_STATIC = Path(__file__).resolve().parent.parent / "static"
_CSS = _STATIC / "noviny-dlouhe.css"


def _base_path() -> str:
    return os.environ.get("SVEJK_BASE_PATH", "").rstrip("/")


def _redirect_html(target: str) -> str:
    return (
        "<!DOCTYPE html>\n"
        '<html lang="cs">\n'
        '<head>\n'
        '<meta charset="utf-8" />\n'
        f'<meta http-equiv="refresh" content="0;url={target}" />\n'
        f'<link rel="canonical" href="{target}" />\n'
        "<title>Přesměrování…</title>\n"
        "</head>\n"
        f'<body></body>\n'
        "</html>\n"
    )


def _render_edition_html(
    edition,
    obdobi: int,
    *,
    base: str,
    css_href: str,
) -> str | None:
    paths = SchuzePaths.create(edition.obdobi, edition.schuze)
    d = datetime.strptime(edition.datum_unl, "%d.%m.%Y")
    day_path = paths.facts_by_day / f"{d.strftime('%Y-%m-%d')}.json"
    if not day_path.is_file():
        return None
    content = build_den_content(day_path, paths)
    return render_den_html(
        content,
        paths,
        day_path,
        inline_css=False,
        css_href=css_href,
        link_mode="pages",
        obdobi=obdobi,
        base_path=base,
    )


def run_export_pages(
    obdobi: int,
    out_dir: Path | str,
    *,
    base_path: str | None = None,
    cname: str | None = None,
) -> dict[str, Any]:
    """Vyexportuje všechna vydání období do složky pro GitHub Pages."""
    clear_edition_cache()
    base = _base_path() if base_path is None else base_path.rstrip("/")
    out = Path(out_dir)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    (out / ".nojekyll").touch()
    domain = cname if cname is not None else os.environ.get("SVEJK_PAGES_CNAME", "poslusnehlasim.cz")
    if domain:
        (out / "CNAME").write_text(domain.strip() + "\n", encoding="utf-8")

    static_dir = out / "static"
    static_dir.mkdir()
    shutil.copy2(_CSS, static_dir / "noviny-dlouhe.css")
    css_href = static_css_path(base, version=css_asset_version())

    editions = list_obdobi_editions(obdobi)
    if not editions:
        raise FileNotFoundError(
            f"Žádná vydání v {processed_root()}/{obdobi}-s* — spusť build pro období {obdobi}."
        )

    written: list[str] = []
    for edition in editions:
        html = _render_edition_html(edition, obdobi, base=base, css_href=css_href)
        if html is None:
            continue
        dest = out / "noviny" / str(edition.obdobi) / str(edition.schuze) / f"{edition.datum_unl}.html"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(html, encoding="utf-8")
        written.append(str(dest.relative_to(out)))

    seen_dates: set[str] = set()
    for edition in editions:
        if edition.datum_unl in seen_dates:
            continue
        seen_dates.add(edition.datum_unl)
        resolved = resolve_edition(obdobi, edition.datum_unl)
        if not resolved:
            continue
        html = _render_edition_html(resolved, obdobi, base=base, css_href=css_href)
        if html is None:
            continue
        short = out / "noviny" / str(obdobi) / f"{edition.datum_unl}.html"
        short.parent.mkdir(parents=True, exist_ok=True)
        short.write_text(html, encoding="utf-8")
        written.append(str(short.relative_to(out)))

    latest = editions[-1]
    latest_href = edition_pages_href(latest.obdobi, latest.schuze, latest.datum_unl, base)
    latest_html = _render_edition_html(latest, obdobi, base=base, css_href=css_href)
    if latest_html is None:
        (out / "index.html").write_text(_redirect_html(latest_href), encoding="utf-8")
    else:
        (out / "index.html").write_text(latest_html, encoding="utf-8")

    page_count = sum(1 for p in written if p.endswith(".html") and p.count("/") >= 3)
    return {
        "obdobi": obdobi,
        "files": len(written) + 1,
        "pages": page_count,
        "latest": latest_href,
        "out_dir": str(out),
    }
