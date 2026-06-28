"""SEO: robots.txt, sitemap.xml, llms.txt, meta popisky."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring

from svejk.build.nav import (
    Edition,
    archiv_pages_href,
    edition_pages_href,
    o_webu_pages_href,
    pivo_pages_href,
    podminky_pages_href,
    podpora_pages_href,
    recnici_pages_href,
    slovnicek_pages_href,
    soukromi_pages_href,
    steno_sources_pages_href,
    vyznamenani_pages_href,
)
from svejk.build.recnici import has_recnici
from svejk.build.steno_sources import has_steno_sources
from svejk.build.vyznamenani_neprosli import (
    VyznamenaniKind,
    load_vyznamenani,
    page_meta,
    vyznamenani_datum_label,
)
from svejk.newsletter.feed import _edition_description
from svejk.paths import SchuzePaths

_VYZNAMENANI_KINDS: tuple[VyznamenaniKind, ...] = ("neprosli", "prosli", "zvoleni")

_STATIC_PAGES: tuple[tuple[str, str], ...] = (
    ("O webu", "o-webu"),
    ("Archiv vydání", "archiv"),
    ("Švejkov slovníček", "slovnicek"),
    ("Kup Švejkovi pivo", "pivo"),
    ("Podmínky odběru", "podminky"),
    ("Podpořte projekt", "podpora"),
    ("Ochrana údajů", "soukromi"),
)

_STATIC_HREF_FN = {
    "o-webu": o_webu_pages_href,
    "archiv": archiv_pages_href,
    "slovnicek": slovnicek_pages_href,
    "pivo": pivo_pages_href,
    "podminky": podminky_pages_href,
    "podpora": podpora_pages_href,
    "soukromi": soukromi_pages_href,
}

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


def _edition_date_label(datum_unl: str, den: str = "") -> str:
    if datum_unl and "." in datum_unl:
        d, m, y = datum_unl.split(".", 2)
        core = f"{int(d)}. {int(m)}. {y}"
    else:
        core = datum_unl
    if den:
        return f"{den.capitalize()} {core}"
    return core


def _dnesni_ucet_headline(dnesni_ucet: str) -> str:
    """První věta z dnešního účtu, záloha, když chybí nadpis článku."""
    raw = " ".join((dnesni_ucet or "").split())
    if not raw:
        return ""
    first = raw.split(". ", 1)[0].strip()
    return first if first.endswith(".") else f"{first.rstrip('.')}"


def article_headline(
    *,
    dnesni_ucet: str,
    meta_description: str = "",
    first_item_nadpis: str = "",
    edition_title: str = "",
    max_len: int = 110,
) -> str:
    """Téma dne pro <title> a schema.org, nadpis článku, ne meta description."""
    _ = meta_description
    if first_item_nadpis.strip():
        return _truncate_text(first_item_nadpis.strip(), max_len=max_len)
    from_account = _dnesni_ucet_headline(dnesni_ucet)
    if from_account:
        return _truncate_text(from_account, max_len=max_len)
    return _truncate_text(edition_title, max_len=max_len)


def edition_meta_description(
    *,
    dnesni_ucet: str,
    first_item_nadpis: str = "",
    proslo: int = 0,
    zamitnuto: int = 0,
    max_len: int = 155,
) -> str:
    """Unikátní meta description, skóre dne + shrnutí, ne kopie <title>."""
    parts: list[str] = []
    if proslo or zamitnuto:
        parts.append(f"Skóre dne {proslo}:{zamitnuto}.")
    account = " ".join((dnesni_ucet or "").split())
    if account:
        parts.append(account)
    elif first_item_nadpis.strip():
        parts.append(first_item_nadpis.strip())
    raw = " ".join(parts)
    return meta_description(raw, max_len=max_len) if raw else ""


def homepage_page_title(**_kwargs: object) -> str:
    """Stabilní <title> pro úvodní stránku, bez denního tématu ani data."""
    return "Poslušně hlásím · Deník ze Sněmovny"


def homepage_og_title() -> str:
    return "Poslušně hlásím · Deník ze Sněmovny"


def edition_page_title(
    *,
    dnesni_ucet: str,
    meta_description: str = "",
    first_item_nadpis: str = "",
    datum_unl: str,
    den: str = "",
    datum_design: str = "",
    max_len: int = 72,
) -> str:
    """<title> pro vydání: Poslušně hlásím, datum: téma dne."""
    _ = meta_description
    date_label = _edition_date_label(datum_unl, den) if datum_unl else (datum_design or "")
    prefix = f"Poslušně hlásím, {date_label}: " if date_label else "Poslušně hlásím: "
    budget = max(12, max_len - len(prefix))
    headline = article_headline(
        dnesni_ucet=dnesni_ucet,
        first_item_nadpis=first_item_nadpis,
        edition_title=datum_design,
        max_len=budget,
    )
    if not headline.strip():
        return _truncate_text(
            f"Poslušně hlásím, {date_label}" if date_label else "Poslušně hlásím",
            max_len=max_len,
        )
    title = f"{prefix}{headline}"
    return title if len(title) <= max_len else _truncate_text(title, max_len=max_len)


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
) -> dict:
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
    return data


_WEBSITE_DESCRIPTION = (
    "Deník z jednání Poslanecké sněmovny ve stylu Haška, "
    "srozumitelné shrnutí hlasování a zákonů pro lidi, kteří do sněmovny nemusí."
)


def website_json_ld(
    *,
    site_url: str,
    site_name: str = "Poslušně hlásím",
    description: str = _WEBSITE_DESCRIPTION,
    logo_url: str | None = None,
    base_path: str = "",
) -> dict:
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
    return data


def faq_json_ld(
    *,
    url: str,
    entries: list[tuple[str, str]],
) -> dict:
    """FAQPage schema pro slovníček."""
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "@id": url,
        "url": url,
        "mainEntity": [
            {
                "@type": "Question",
                "name": question,
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": answer,
                },
            }
            for question, answer in entries
        ],
    }


def _static_page_links(
    *,
    site_url: str,
    base_path: str = "",
) -> list[tuple[str, str]]:
    base = site_url.rstrip("/")
    return [
        (label, f"{base}{_STATIC_HREF_FN[key](base_path)}")
        for label, key in _STATIC_PAGES
    ]


def _iter_vyznamenani_editions(
    editions: list[Edition],
) -> list[tuple[Edition, VyznamenaniKind]]:
    found: list[tuple[Edition, VyznamenaniKind]] = []
    for edition in editions:
        paths = SchuzePaths.create(edition.obdobi, edition.schuze)
        for kind in _VYZNAMENANI_KINDS:
            if load_vyznamenani(paths, edition.datum_unl, kind):
                found.append((edition, kind))
    return found


def write_security_txt(
    out_dir: Path,
    *,
    site_url: str,
    contact_email: str = "svejk@poslusnehlasim.cz",
    expires: datetime | None = None,
) -> Path:
    """RFC 9116 security.txt v .well-known/."""
    base = site_url.rstrip("/")
    exp = expires or datetime.now(timezone.utc).replace(
        year=datetime.now(timezone.utc).year + 1
    )
    lines = [
        f"Contact: mailto:{contact_email}",
        "Preferred-Languages: cs",
        f"Canonical: {base}/.well-known/security.txt",
        f"Expires: {exp.strftime('%Y-%m-%dT%H:%M:%SZ')}",
    ]
    path = out_dir / ".well-known" / "security.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


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
        last = editions[-1].when
        add_url(f"{base}{archiv_pages_href(base_path)}", last)
        add_url(f"{base}{o_webu_pages_href(base_path)}", last)
        add_url(f"{base}{slovnicek_pages_href(base_path)}", last)
        add_url(f"{base}{pivo_pages_href(base_path)}", last)
        add_url(f"{base}{podminky_pages_href(base_path)}", last)
        add_url(f"{base}{podpora_pages_href(base_path)}", last)
        add_url(f"{base}{soukromi_pages_href(base_path)}", last)
        add_url(f"{base}/feed.xml", last)

    for edition in editions:
        href = edition_pages_href(edition.obdobi, edition.schuze, edition.datum_unl, base_path)
        add_url(f"{base}{href}", edition.when)

    for edition, kind in _iter_vyznamenani_editions(editions):
        href = vyznamenani_pages_href(
            edition.obdobi, edition.schuze, edition.datum_unl, kind, base_path
        )
        add_url(f"{base}{href}", edition.when)

    for edition in editions:
        paths = SchuzePaths.create(edition.obdobi, edition.schuze)
        if has_steno_sources(paths, edition.datum_unl):
            href = steno_sources_pages_href(
                edition.obdobi, edition.schuze, edition.datum_unl, base_path
            )
            add_url(f"{base}{href}", edition.when)
        if has_recnici(paths, edition.datum_unl):
            href = recnici_pages_href(
                edition.obdobi, edition.schuze, edition.datum_unl, base_path
            )
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

    static_links = "\n".join(
        f"- [{label}]({href})"
        for label, href in _static_page_links(site_url=site_url, base_path=base_path)
    )
    llms = f"""# Poslušně hlásím

> Deník z jednání Poslanecké sněmovny ČR ve stylu Haška: srozumitelné shrnutí hlasování a zákonů pro lidi, kteří do sněmovny nemusí.

Poslušně hlásím publikuje po každém jednacím dni stručné vydání: kolik věcí prošlo, co se schválilo nebo zamítlo a co to znamená v praxi.

## Hlavní stránky

- [Úvod / nejnovější vydání]({base}/): aktuální deník
- [Nejnovější vydání ({latest.datum_unl})]({base}{latest_href}): poslední schůze
- [RSS kanál nových vydání]({base}/feed.xml): odběr nových vydání
- [Mapa webu]({base}/sitemap.xml): všechna vydání
- [Podrobný index pro AI]({base}/llms-full.txt): seznam vydání s popisky

## Ostatní stránky

{static_links}

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
        "## Ostatní stránky",
        "",
        f"- [Úvod / nejnovější vydání]({base}/)",
    ]
    for label, href in _static_page_links(site_url=site_url, base_path=base_path):
        full_lines.append(f"- [{label}]({href})")
    full_lines.extend(["", "## Vydání", ""])
    for edition in editions:
        href = edition_pages_href(
            edition.obdobi, edition.schuze, edition.datum_unl, base_path
        )
        den = den_v_tydnu(edition.datum_unl)
        title = datum_design(edition.datum_unl, den)
        desc = _edition_description(edition)
        line = f"- [{title}]({base}{href})"
        if desc:
            line += f": {desc}"
        full_lines.append(line)

    vyznamenani_entries = _iter_vyznamenani_editions(editions)
    if vyznamenani_entries:
        full_lines.extend(["", "## Tabulky hlasování", ""])
        for edition, kind in vyznamenani_entries:
            paths = SchuzePaths.create(edition.obdobi, edition.schuze)
            data = load_vyznamenani(paths, edition.datum_unl, kind)
            if not data:
                continue
            datum_label = vyznamenani_datum_label(edition.datum_unl)
            pocet = int(data.get("pocet") or len(data.get("radky") or []))
            meta = page_meta(kind, pocet=pocet, datum_label=datum_label)
            href = vyznamenani_pages_href(
                edition.obdobi, edition.schuze, edition.datum_unl, kind, base_path
            )
            title = datum_design(edition.datum_unl, den_v_tydnu(edition.datum_unl))
            line = f"- [{meta['title']} · {title}]({base}{href}): {meta['gloss']}"
            full_lines.append(line)

    steno_editions = [
        e for e in editions
        if has_steno_sources(SchuzePaths.create(e.obdobi, e.schuze), e.datum_unl)
    ]
    recnici_editions = [
        e for e in editions
        if has_recnici(SchuzePaths.create(e.obdobi, e.schuze), e.datum_unl)
    ]

    if steno_editions or recnici_editions:
        full_lines.extend(["", "## Stenozáznamy a řečníci", ""])
        for edition in steno_editions:
            href = steno_sources_pages_href(
                edition.obdobi, edition.schuze, edition.datum_unl, base_path
            )
            den = den_v_tydnu(edition.datum_unl)
            title = datum_design(edition.datum_unl, den)
            full_lines.append(f"- [Stenozáznam · {title}]({base}{href})")
        for edition in recnici_editions:
            href = recnici_pages_href(
                edition.obdobi, edition.schuze, edition.datum_unl, base_path
            )
            den = den_v_tydnu(edition.datum_unl)
            title = datum_design(edition.datum_unl, den)
            full_lines.append(f"- [Řečníci · {title}]({base}{href})")

    full_path = out_dir / "llms-full.txt"
    full_path.write_text("\n".join(full_lines) + "\n", encoding="utf-8")
    return out_dir / "llms.txt", full_path
