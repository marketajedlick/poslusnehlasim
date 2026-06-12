"""SEO: robots.txt, sitemap.xml, llms.txt, meta popisky."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring

from svejk.build.nav import (
    Edition,
    archiv_pages_href,
    edition_pages_href,
    slovnicek_pages_href,
)
from svejk.newsletter.feed import _edition_description

_AI_BOTS = (
    "GPTBot",
    "ChatGPT-User",
    "OAI-SearchBot",
    "ClaudeBot",
    "anthropic-ai",
    "Google-Extended",
    "PerplexityBot",
    "Applebot-Extended",
    "cohere-ai",
)


def meta_description(text: str, *, max_len: int = 155) -> str:
    one = " ".join(text.split())
    if len(one) <= max_len:
        return one
    cut = one[: max_len - 1].rsplit(" ", 1)[0]
    return cut + "…"


def publisher_logo_url(site_url: str, base_path: str = "") -> str:
    base = site_url.rstrip("/")
    prefix = f"{base_path.rstrip('/')}/static" if base_path else "/static"
    if not prefix.startswith("/"):
        prefix = "/" + prefix
    return f"{base}{prefix}/apple-touch-icon.png"


def mtime_iso(path: Path) -> str:
    """ISO 8601 UTC z času poslední změny souboru (pro dateModified)."""
    ts = path.stat().st_mtime
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def article_headline(
    *,
    dnesni_ucet: str,
    meta_description: str,
    first_item_nadpis: str = "",
    edition_title: str = "",
    max_len: int = 110,
) -> str:
    """Nadpis pro schema.org — shrnutí dne, ne datum v hlavičce."""
    raw = " ".join((dnesni_ucet or "").split())
    if raw:
        return _truncate_text(meta_description or raw, max_len=max_len)
    if first_item_nadpis:
        return _truncate_text(first_item_nadpis, max_len=max_len)
    return _truncate_text(edition_title, max_len=max_len)


def edition_page_title(
    *,
    dnesni_ucet: str,
    meta_description: str,
    first_item_nadpis: str = "",
    datum_unl: str,
    den: str = "",
    datum_design: str = "",
    max_len: int = 65,
) -> str:
    """<title> pro vydání: téma dne · datum · Poslušně hlásím."""
    if datum_unl and "." in datum_unl:
        d, m, y = datum_unl.split(".", 2)
        date_bit = f"{d}/{m}/{y}"
    else:
        date_bit = datum_design or datum_unl
    if den:
        date_bit = f"{den.lower()} {date_bit}"
    suffix = f" · {date_bit} · Poslušně hlásím"
    budget = max_len - len(suffix)
    if budget < 8:
        return _truncate_text(f"Poslušně hlásím · {date_bit}", max_len=max_len)
    headline = article_headline(
        dnesni_ucet=dnesni_ucet,
        meta_description=meta_description,
        first_item_nadpis=first_item_nadpis,
        edition_title=datum_design,
        max_len=budget,
    )
    if not headline.strip():
        return _truncate_text(f"Poslušně hlásím · {date_bit}", max_len=max_len)
    return f"{headline}{suffix}"


def _truncate_text(text: str, *, max_len: int) -> str:
    one = " ".join(text.split())
    if len(one) <= max_len:
        return one
    cut = one[: max_len - 1].rsplit(" ", 1)[0]
    return cut + "…"


def _publisher_block(*, site_url: str, site_name: str, logo_url: str) -> dict:
    return {
        "@type": "Organization",
        "name": site_name,
        "url": site_url.rstrip("/") + "/",
        "logo": {
            "@type": "ImageObject",
            "url": logo_url,
            "width": 200,
            "height": 280,
        },
    }


def article_json_ld(
    *,
    headline: str,
    description: str,
    url: str,
    date_unl: str,
    site_url: str,
    site_name: str = "Poslušně hlásím",
    image_url: str | None = None,
    logo_url: str | None = None,
    date_modified: str | None = None,
    edition_title: str = "",
    article_body: str = "",
    parts: list[dict[str, str | int]] | None = None,
    base_path: str = "",
) -> str:
    published = datetime.strptime(date_unl, "%d.%m.%Y").strftime("%Y-%m-%d")
    logo = logo_url or publisher_logo_url(site_url, base_path)
    article_image = image_url or logo
    publisher = _publisher_block(
        site_url=site_url, site_name=site_name, logo_url=logo
    )
    data: dict = {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "@id": url,
        "mainEntityOfPage": {"@type": "WebPage", "@id": url},
        "headline": headline,
        "description": description,
        "url": url,
        "datePublished": published,
        "dateModified": date_modified or published,
        "inLanguage": "cs",
        "isAccessibleForFree": True,
        "articleSection": "Poslanecká sněmovna",
        "author": publisher,
        "publisher": publisher,
        "image": [article_image],
        "isPartOf": {
            "@type": "WebSite",
            "name": site_name,
            "url": site_url.rstrip("/") + "/",
        },
    }
    if edition_title and edition_title != headline:
        data["alternativeHeadline"] = edition_title
    if article_body:
        data["articleBody"] = article_body
    if parts:
        data["hasPart"] = [
            {
                "@type": "NewsArticle",
                "headline": part["headline"],
                "articleBody": part["body"],
                "position": part["position"],
            }
            for part in parts
        ]
    return json.dumps(data, ensure_ascii=False)


_WEBSITE_DESCRIPTION = (
    "Deník z jednání Poslanecké sněmovny ve stylu Haška — "
    "srozumitelné shrnutí hlasování a zákonů pro lidi, kteří do sněmovny nemusí."
)


def website_json_ld(
    *,
    site_url: str,
    site_name: str = "Poslušně hlásím",
    description: str = _WEBSITE_DESCRIPTION,
    logo_url: str | None = None,
    base_path: str = "",
) -> str:
    """WebSite + publisher pro homepage."""
    base = site_url.rstrip("/")
    logo = logo_url or publisher_logo_url(site_url, base_path)
    data = {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "@id": f"{base}/#website",
        "url": f"{base}/",
        "name": site_name,
        "description": description,
        "inLanguage": "cs",
        "publisher": _publisher_block(
            site_url=site_url, site_name=site_name, logo_url=logo
        ),
    }
    return json.dumps(data, ensure_ascii=False)


def write_robots_txt(out_dir: Path, *, site_url: str) -> Path:
    base = site_url.rstrip("/")
    lines = [
        "User-agent: *",
        "Allow: /",
        "",
    ]
    for bot in _AI_BOTS:
        lines.extend([f"User-agent: {bot}", "Allow: /", ""])
    lines.extend([
        f"Sitemap: {base}/sitemap.xml",
        f"# LLM index: {base}/llms.txt",
    ])
    path = out_dir / "robots.txt"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_sitemap_xml(
    out_dir: Path,
    editions: list[Edition],
    *,
    site_url: str,
    base_path: str = "",
) -> Path:
    base = site_url.rstrip("/")
    urlset = Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")

    def add_url(loc: str, lastmod: datetime) -> None:
        url = SubElement(urlset, "url")
        SubElement(url, "loc").text = loc
        SubElement(url, "lastmod").text = lastmod.astimezone(timezone.utc).strftime(
            "%Y-%m-%d"
        )

    add_url(f"{base}/", editions[-1].when if editions else datetime.now(timezone.utc))
    if editions:
        add_url(f"{base}{archiv_pages_href(base_path)}", editions[-1].when)
        add_url(f"{base}{slovnicek_pages_href(base_path)}", editions[-1].when)
        add_url(f"{base}/soukromi/", editions[-1].when)

    for edition in editions:
        href = edition_pages_href(edition.obdobi, edition.schuze, edition.datum_unl, base_path)
        add_url(f"{base}{href}", edition.when)

    xml = b'<?xml version="1.0" encoding="UTF-8"?>\n' + tostring(urlset, encoding="utf-8")
    path = out_dir / "sitemap.xml"
    path.write_bytes(xml)
    return path


def write_llms_txt(
    out_dir: Path,
    editions: list[Edition],
    *,
    site_url: str,
    base_path: str = "",
    obdobi: int = 2025,
) -> tuple[Path, Path]:
    """llms.txt a llms-full.txt pro AI crawlery (ChatGPT, Claude, …)."""
    base = site_url.rstrip("/")
    latest = editions[-1]
    latest_href = edition_pages_href(
        latest.obdobi, latest.schuze, latest.datum_unl, base_path
    )

    llms = f"""# Poslušně hlásím

> Deník z jednání Poslanecké sněmovny ČR ve stylu Haška: srozumitelné shrnutí hlasování a zákonů pro lidi, kteří do sněmovny nemusí.

Poslušně hlásím publikuje po každém jednacím dni stručné vydání: kolik věcí prošlo, co se schválilo nebo zamítlo a co to znamená v praxi. Texty jsou v češtině.

## Hlavní stránky

- [Úvod / nejnovější vydání]({base}/): aktuální deník
- [Nejnovější vydání ({latest.datum_unl})]({base}{latest_href}): poslední schůze
- [RSS kanál nových vydání]({base}/feed.xml): pro odběr a agregátory
- [Mapa webu]({base}/sitemap.xml): všechna vydání
- [Podrobný index pro AI]({base}/llms-full.txt): seznam vydání s popisky

## Odběr

- E-mailový odběr nových vydání je na každé stránce dole (formulář „Poslušně odebírat“).

## Kontext

- Období: {obdobi}. volební období PS PČR
- Formát: statické HTML stránky, jedno vydání = jeden den jednání sněmovny
"""
    (out_dir / "llms.txt").write_text(llms, encoding="utf-8")

    from svejk.build.day_content import datum_design
    from svejk.timeline import den_v_tydnu

    full_lines = [
        "# Poslušně hlásím, index vydání",
        "",
        f"> Kompletní seznam vydání období {obdobi}. Zdroj: {base}",
        "",
        "## Vydání",
        "",
    ]
    for edition in editions:
        href = edition_pages_href(
            edition.obdobi, edition.schuze, edition.datum_unl, base_path
        )
        title = datum_design(edition.datum_unl, den_v_tydnu(edition.datum_unl))
        desc = _edition_description(edition)
        line = f"- [{title}]({base}{href})"
        if desc:
            line += f": {desc}"
        full_lines.append(line)

    full_path = out_dir / "llms-full.txt"
    full_path.write_text("\n".join(full_lines) + "\n", encoding="utf-8")
    return out_dir / "llms.txt", full_path
