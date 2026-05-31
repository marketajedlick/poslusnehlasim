"""SEO: robots.txt, sitemap.xml, llms.txt, meta popisky."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring

from svejk.build.nav import Edition, edition_pages_href
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


def article_json_ld(
    *,
    headline: str,
    description: str,
    url: str,
    date_unl: str,
    site_url: str,
    site_name: str = "Poslušně hlásím",
) -> str:
    published = datetime.strptime(date_unl, "%d.%m.%Y").strftime("%Y-%m-%d")
    data = {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": headline,
        "description": description,
        "url": url,
        "datePublished": published,
        "inLanguage": "cs",
        "isAccessibleForFree": True,
        "isPartOf": {
            "@type": "WebSite",
            "name": site_name,
            "url": site_url.rstrip("/") + "/",
        },
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

> Deník z jednání Poslanecké sněmovny ČR ve stylu Haška — srozumitelné shrnutí hlasování a zákonů pro lidi, kteří do sněmovny nemusí.

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
        "# Poslušně hlásím — index vydání",
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
