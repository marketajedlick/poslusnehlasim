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
    smlouvy_pages_href,
    steno_sources_pages_href,
    vyznamenani_pages_href,
    resolve_edition,
)
from svejk.build.urls import datum_unl_to_iso
from svejk.build.mezin_smlouvy import has_smlouvy
from svejk.build.recnici import has_recnici
from svejk.build.steno_sources import has_steno_sources
from svejk.build.vyznamenani_neprosli import (
    VyznamenaniKind,
    load_vyznamenani,
    page_meta,
    vyznamenani_datum_label,
)
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


SITE_NAME = "Poslušně hlásím"
SITE_DOMAIN = "poslusnehlasim.cz"
SITE_TAGLINE = "Deník sněmovny"
SITE_TITLE_TAGLINE = "denní zpravodaj z Poslanecké sněmovny"
SITE_META_DESCRIPTION = (
    "Satirický deník z Poslanecké sněmovny. Každý jednací den srozumitelně: "
    "o čem poslanci hlasovali, co zaznělo v rozpravě a co to znamená. "
    "Bez stenoprotokolové mlhy."
)
ORGANIZATION_DESCRIPTION = (
    "Satirický denní zpravodaj z jednání Poslanecké sněmovny Parlamentu ČR. "
    "Srozumitelné shrnutí rozprav a hlasování za každý jednací den."
)
WEBSITE_SCHEMA_NAME = f"{SITE_NAME}, deník Poslanecké sněmovny"


def site_meta_description() -> str:
    return SITE_META_DESCRIPTION


def site_brand_line() -> str:
    return f"{SITE_NAME} · {SITE_DOMAIN} · {SITE_TAGLINE}"


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


def _edition_date_label_short(datum_unl: str) -> str:
    """Datum do <title> bez dne v týdnu (úspora znaků pro klíčová slova)."""
    if datum_unl and "." in datum_unl:
        d, m, y = datum_unl.split(".", 2)
        return f"{int(d)}. {int(m)}. {y}"
    return datum_unl


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
    datum_unl: str = "",
    proslo: int = 0,
    zamitnuto: int = 0,
    max_len: int = 155,
) -> str:
    """Unikátní meta popis pro Google: perex dne + kontext sněmovny a datum."""
    _ = proslo, zamitnuto
    import re

    from svejk.build.glossary_markup import strip_glossary_markup

    def _strip_html(text: str) -> str:
        return re.sub(r"<[^>]+>", "", strip_glossary_markup(text)).strip()

    perex = article_headline(
        dnesni_ucet=_strip_html(dnesni_ucet),
        first_item_nadpis=_strip_html(first_item_nadpis),
        max_len=120,
    )
    if not perex:
        return SITE_META_DESCRIPTION
    perex_clean = perex.rstrip(".")
    date_label = _edition_date_label_short(datum_unl) if datum_unl else ""
    if date_label:
        raw = f"{perex_clean}. Denní přehled z Poslanecké sněmovny, {date_label}."
    else:
        raw = f"{perex_clean}. Denní přehled z Poslanecké sněmovny."
    return meta_description(raw, max_len=max_len)


def homepage_page_title(**_kwargs: object) -> str:
    """Stabilní <title> pro úvodní stránku, bez denního tématu ani data."""
    return f"{SITE_NAME}, {SITE_TITLE_TAGLINE}"


def homepage_og_title() -> str:
    """Fallback og:title bez kontextu vydání (statické stránky)."""
    return f"{SITE_NAME}, {SITE_TITLE_TAGLINE}"


def homepage_share_og_title(
    *,
    dnesni_ucet: str,
    first_item_nadpis: str = "",
    datum_unl: str,
    den: str = "",
    max_len: int = 120,
) -> str:
    """og:title pro homepage — sdílení ukazuje aktuální vydání, ne brand <title>."""
    return edition_page_title(
        dnesni_ucet=dnesni_ucet,
        first_item_nadpis=first_item_nadpis,
        datum_unl=datum_unl,
        den=den,
        max_len=max_len,
    )


def edition_page_title(
    *,
    dnesni_ucet: str,
    meta_description: str = "",
    first_item_nadpis: str = "",
    datum_unl: str,
    den: str = "",
    datum_design: str = "",
    max_len: int = 90,
) -> str:
    """<title> pro vydání: Sněmovna datum: téma | značka."""
    _ = meta_description, den, datum_design
    date_label = _edition_date_label_short(datum_unl) if datum_unl else ""
    suffix = f" | {SITE_NAME}"
    if date_label:
        prefix = f"Sněmovna {date_label}: "
    else:
        prefix = "Sněmovna: "
    budget = max(12, max_len - len(prefix) - len(suffix))
    headline = article_headline(
        dnesni_ucet=dnesni_ucet,
        first_item_nadpis=first_item_nadpis,
        edition_title=datum_design,
        max_len=budget,
    )
    if not headline.strip():
        core = f"{prefix.rstrip(': ')}{suffix}" if date_label else f"Sněmovna{suffix}"
        return _truncate_text(core, max_len=max_len)
    title = f"{prefix}{headline}{suffix}"
    return title if len(title) <= max_len else _truncate_text(title, max_len=max_len)


def _truncate_text(text: str, *, max_len: int) -> str:
    one = " ".join(text.split())
    if len(one) <= max_len:
        return one
    cut = one[: max_len - 1].rsplit(" ", 1)[0]
    return cut + "…"


def _publisher_block(
    *,
    site_url: str,
    site_name: str = SITE_NAME,
    logo_url: str,
    org_id: str | None = None,
) -> dict:
    block: dict = {
        "@type": ["Organization", "NewsMediaOrganization"],
        "name": site_name,
        "alternateName": SITE_DOMAIN,
        "url": site_url.rstrip("/") + "/",
        "logo": {
            "@type": "ImageObject",
            "url": logo_url,
            "width": 200,
            "height": 280,
        },
    }
    if org_id:
        block["@id"] = org_id
    return block


def _org_id(site_url: str) -> str:
    return site_url.rstrip("/") + "/#org"


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
    published_date = datetime.strptime(date_unl, "%d.%m.%Y").strftime("%Y-%m-%d")
    published = f"{published_date}T00:00:00+02:00"
    modified = date_modified or published
    org_id = _org_id(site_url)
    logo = logo_url or publisher_logo_url(site_url, base_path)
    article_image = image_url or logo
    data: dict = {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "@id": url,
        "mainEntityOfPage": url,
        "headline": headline,
        "description": description,
        "url": url,
        "datePublished": published,
        "dateModified": modified,
        "inLanguage": "cs",
        "isAccessibleForFree": True,
        "articleSection": "Poslanecká sněmovna",
        "author": {"@type": "Organization", "@id": org_id},
        "publisher": {"@id": org_id},
        "image": [article_image],
        "about": [
            {
                "@type": "Thing",
                "name": "Poslanecká sněmovna Parlamentu České republiky",
            }
        ],
        "isPartOf": {
            "@type": "WebSite",
            "name": WEBSITE_SCHEMA_NAME,
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


_WEBSITE_DESCRIPTION = SITE_META_DESCRIPTION


def website_json_ld(
    *,
    site_url: str,
    site_name: str = SITE_NAME,
    description: str = _WEBSITE_DESCRIPTION,
    logo_url: str | None = None,
    base_path: str = "",
) -> dict:
    """WebSite + Organization pro homepage."""
    base = site_url.rstrip("/")
    logo = logo_url or publisher_logo_url(site_url, base_path)
    org_id = f"{base}/#org"
    website_id = f"{base}/#website"
    organization = _publisher_block(
        site_url=site_url,
        site_name=site_name,
        logo_url=logo,
        org_id=org_id,
    )
    organization["description"] = ORGANIZATION_DESCRIPTION
    website = {
        "@type": "WebSite",
        "@id": website_id,
        "url": f"{base}/",
        "name": WEBSITE_SCHEMA_NAME,
        "alternateName": SITE_DOMAIN,
        "description": description,
        "inLanguage": "cs",
        "publisher": {"@id": org_id},
    }
    return {
        "@context": "https://schema.org",
        "@graph": [organization, website],
    }


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
    """robots.txt pro export. Vyžaduje vypnutý Cloudflare Managed robots.txt (viz infra/cloudflare/README.md)."""
    base = site_url.rstrip("/")
    lines = [
        "# poslusnehlasim.cz — export-pages. Cloudflare Managed robots.txt musí být vypnutý,",
        "# jinak edge předřadí Disallow pro AI boty nad Allow níže (viz infra/cloudflare/README.md §8).",
        "",
    ]
    for bot in _AI_BOTS:
        lines.extend([f"User-agent: {bot}", "Allow: /", ""])
    lines.extend([
        "User-agent: *",
        "Content-Signal: search=yes,ai-train=no",
        "Allow: /",
        "",
        f"Sitemap: {base}/sitemap.xml",
        f"# LLM index: {base}/llms.txt",
    ])
    path = out_dir / "robots.txt"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def edition_subpage_hrefs(
    edition: Edition,
    *,
    base_path: str = "",
) -> list[str]:
    """Indexovatelné podstránky vydání (steno, smlouvy, tabulky)."""
    paths = SchuzePaths.create(edition.obdobi, edition.schuze)
    datum = edition.datum_unl
    ob, sch = edition.obdobi, edition.schuze
    out: list[str] = []
    if has_steno_sources(paths, datum):
        out.append(steno_sources_pages_href(ob, sch, datum, base_path))
    if has_smlouvy(paths, datum):
        out.append(smlouvy_pages_href(ob, sch, datum, base_path))
    if has_recnici(paths, datum):
        out.append(recnici_pages_href(ob, sch, datum, base_path))
    for kind in _VYZNAMENANI_KINDS:
        if load_vyznamenani(paths, datum, kind):
            out.append(vyznamenani_pages_href(ob, sch, datum, kind, base_path))
    return out


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

    seen_dates: set[str] = set()
    for edition in editions:
        iso = datum_unl_to_iso(edition.datum_unl)
        if iso in seen_dates:
            continue
        seen_dates.add(iso)
        resolved = resolve_edition(edition.obdobi, edition.datum_unl) or edition
        href = edition_pages_href(
            resolved.obdobi, resolved.schuze, resolved.datum_unl, base_path
        )
        add_url(f"{base}{href}", edition.when)
        for sub_href in edition_subpage_hrefs(resolved, base_path=base_path):
            add_url(f"{base}{sub_href}", edition.when)

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
    llms = f"""# {SITE_NAME}

> {SITE_META_DESCRIPTION}

{SITE_NAME} ({SITE_DOMAIN}) publikuje po každém jednacím dni stručné vydání: kolik věcí prošlo, co se schválilo nebo zamítlo a co to znamená v praxi.

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
    from svejk.newsletter.feed import _edition_description

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
