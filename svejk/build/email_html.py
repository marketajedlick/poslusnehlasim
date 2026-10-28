"""Newsletter: HTML a plain text e-mailu vydání, DOI e-mail.

Vyčleněno z html.py (dřív 2 457 řádků)."""

from __future__ import annotations

from functools import lru_cache

import copy
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, pass_context, select_autoescape
from markupsafe import Markup

from svejk.build.day_content import DenContent, build_den_content, datum_day_month, datum_design
from svejk.build.io import read_json
from svejk.build.seo import SITE_NAME, edition_published_iso, site_meta_description
from svejk.build.steno_sources import steno_sources_href
from svejk.glossary import slovnicek_anchor, slovnicek_display_term, slovnicek_entries, slovnicek_term_label
from svejk.build.publish import list_site_editions
from svejk.strings import footer_closings, footer_stats_line, load_strings, schuze_count_label
from svejk.build.nav import (
    Edition,
    archiv_pages_href,
    archive_by_month,
    archive_text_list,
    build_session_calendar,
    edition_nav,
    edition_pages_href,
    o_webu_pages_href,
    pivo_pages_href,
    dekuju_pages_href,
    podminky_pages_href,
    podpora_pages_href,
    subscribe_pages_href,
    slovnicek_pages_href,
    slovnicek_term_pages_href,
    soukromi_pages_href,
    vyznamenani_pages_href,
    steno_sources_pages_href,
    smlouvy_pages_href,
    recnici_pages_href,
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
    pt = load_strings().get("pivo_tiers", {})
    monthly_badge = pt.get("monthly_badge", "MĚSÍČNĚ")
    return [
        {
            "id": "velke",
            "kind": "once",
            "name": pt.get("velke_name", "Velké pivo"),
            "price": "65 Kč",
            "note": pt.get("velke_note", "starý osvědčený prostředek proti trudnomyslnosti"),
            "cta": pt.get("velke_cta", "Přispět jednorázově"),
            "pay_href": _stripe_url("STRIPE_PIVO_URL", STRIPE_PIVO_URL),
        },
        {
            "id": "rum",
            "kind": "once",
            "name": pt.get("rum_name", "Rum"),
            "price": "95 Kč",
            "note": pt.get("rum_note", "Kořalku nepiju, jen rum."),
            "cta": pt.get("rum_cta", "Přispět jednorázově"),
            "pay_href": _stripe_url("STRIPE_RUM_URL", STRIPE_RUM_URL),
        },
        {
            "id": "stamgast",
            "kind": "monthly",
            "name": pt.get("stamgast_name", "Štamgast"),
            "price": "65 Kč",
            "price_badge": monthly_badge,
            "note": pt.get("stamgast_note", "pro ty, kdo chodí pravidelně, i když zrovna není poplach"),
            "cta": pt.get("stamgast_cta", "Stát se Štamgastem"),
            "pay_href": _stripe_url("STRIPE_STAMGAST_URL", STRIPE_STAMGAST_URL),
        },
    ]


from svejk.build.vyznamenani_neprosli import (
    VyznamenaniKind,
    inject_mean_links,
    load_vyznamenani,
    page_explain,
    page_meta,
    resolve_vyznamenani_page_links,
    sibling_label,
    table_rows,
    vyznamenani_datum_label,
    vyznamenani_href,
    _load_votes_by_cislo,
)
from svejk.build.steno_sources import (
    apply_steno_links_to_content,
    collect_steno_sources,
    has_steno_sources,
)
from svejk.build.recnici import (
    load_recnici,
    recnici_datum_label,
    recnici_href,
    recnici_page_meta,
    recnici_rows,
    resolve_recnici_page_links,
)
from svejk.newsletter.config import NewsletterConfig
from svejk.paths import SchuzePaths
from svejk.timeline import den_v_tydnu

from svejk.build.html import (  # noqa: F401
    _DOI_EMAIL_CSS,
    _EMAIL_CSS,
    _FIELD_LINK_STYLE,
    _apply_content_item_links,
    _jinja_env,
)


def plain_text_from_content(
    content: DenContent,
    *,
    datum_label: str,
    edition_url: str,
    archive_url: str,
    pivo_url: str,
) -> str:
    from svejk.build.glossary_markup import strip_glossary_markup

    def _plain(text: str) -> str:
        if not text:
            return ""
        return re.sub(r"<[^>]+>", "", strip_glossary_markup(text)).strip()

    lines = [f"POSLUŠNĚ HLÁSÍM · {datum_label}", ""]
    zaver = _plain(content.zaver or "")
    if zaver:
        lines.append(f"„{zaver}“")
    for item in content.items:
        lines.extend(
            [
                "",
                f"{item.num:02d} · {item.kick} · {item.stamp}",
                _plain(item.nadpis),
                _plain(item.lead),
            ]
        )
        if item.citace_text:
            cite = f"„{_plain(item.citace_text)}“"
            if item.citace_autor:
                cite = f"{cite} ({item.citace_autor})"
            lines.append(cite)
        if item.lead_tail and item.kuriozita:
            lines.append(_plain(item.kuriozita))
            lines.append(_plain(item.lead_tail))
        elif item.lead_tail:
            lines.append(_plain(item.lead_tail))
        if item.pointa:
            lines.append(_plain(item.pointa))
        if item.citace2_text:
            cite2 = f"„{_plain(item.citace2_text)}“"
            if item.citace2_autor:
                cite2 = f"{cite2} ({item.citace2_autor})"
            lines.append(cite2)
        if item.pointa_tail:
            lines.append(_plain(item.pointa_tail))
        if item.mean:
            mean_label = load_strings()["edition"]["mean_label"]
            lines.append(f"{mean_label} {_plain(item.mean)}")
        if item.kuriozita and not item.lead_tail:
            lines.append(_plain(item.kuriozita))
        for label, href in item.kuriozita_nav:
            lines.append(f"{label}: {href}")
    lines.extend(
        [
            "",
            f"Číst vydání: {edition_url}",
            f"Archiv všech vydání: {archive_url}",
            f"Kup Švejkovi pivo: {pivo_url}#stamgast",
            "",
            "Odhlášení odběru: odkaz v patičce e-mailu od Ecomailu.",
        ]
    )
    return "\n".join(lines)


def _make_internal_links_absolute(text: str, site_url: str) -> str:
    """Přepíše relativní href (/noviny/...) na absolutní URL pro e-mail."""
    if not text or "href=\"/" not in text:
        return text
    site = site_url.rstrip("/")
    return re.sub(
        r'href="(/[^"]*)"',
        lambda m: f'href="{site}{m.group(1)}"',
        text,
    )


def _inline_email_body_link_styles(text: str, *, field: str = "lead") -> str:
    """Inline styly pro klienty, které neberou <style> z hlavičky."""
    if not text:
        return text
    if '<span class="hl">' in text:
        text = text.replace(
            '<span class="hl">',
            '<span class="hl" style="display:inline;background:rgba(210,60,30,.25);border-radius:2px;padding:0 2px;margin:0 -2px;">',
        )
    if "<a " not in text:
        return text
    color = _FIELD_LINK_STYLE.get(field, _FIELD_LINK_STYLE["lead"])
    style = f'style="{color};text-decoration:underline;font-weight:inherit;"'
    text = text.replace('class=\\"steno-link\\"', 'class="steno-link"')
    text = text.replace('class=\\"mean-link\\"', 'class="mean-link"')
    return re.sub(
        r'<a class="(steno-link|mean-link)"',
        lambda m: f'<a class="{m.group(1)}" {style}',
        text,
    )


def _apply_email_links_absolute(content: Any, site_url: str) -> None:
    """Po doplnění odkazů udělá všechny interní hrefs absolutní."""
    site = site_url.rstrip("/")
    from svejk.build.article_fields import ARTICLE_CITACE_PREFIXES, ARTICLE_TEXT_FIELDS

    for item in content.items:
        for field in ARTICLE_TEXT_FIELDS:
            val = getattr(item, field, None)
            if val:
                val = _make_internal_links_absolute(val, site_url)
                val = _inline_email_body_link_styles(val, field=field)
                setattr(item, field, val)
        for prefix in ARTICLE_CITACE_PREFIXES:
            href = (getattr(item, f"{prefix}_href", None) or "").strip()
            if href.startswith("/"):
                setattr(item, f"{prefix}_href", f"{site}{href}")
        if item.kuriozita_nav:
            item.kuriozita_nav = [
                (label, f"{site}{href}" if href.startswith("/") else href)
                for label, href in item.kuriozita_nav
            ]
    for field in ("dnesni_ucet", "result_note", "zaver", "zaver_body"):
        val = getattr(content, field, None)
        if val:
            val = _make_internal_links_absolute(val, site_url)
            val = _inline_email_body_link_styles(val, field=field)
            setattr(content, field, val)


def _prepare_content_for_email(content: DenContent) -> None:
    """Tooltipy v e-mailu nefungují — nech jen viditelný text."""
    from svejk.build.glossary_markup import strip_glossary_markup

    for field in ("dnesni_ucet", "result_note", "zaver", "zaver_body"):
        val = getattr(content, field, None)
        if val:
            setattr(content, field, strip_glossary_markup(val))
    from svejk.build.article_fields import ARTICLE_TEXT_FIELDS

    for item in content.items:
        for field in ARTICLE_TEXT_FIELDS:
            val = getattr(item, field, None)
            if val:
                setattr(item, field, strip_glossary_markup(val))


def newsletter_subject(day: dict[str, Any], *, datum_label: str) -> str:
    """Předmět Ecomail kampaně: redakční `nwl_predmet`, jinak první řádek účtu."""
    custom = " ".join((day.get("nwl_predmet") or "").split())
    if custom:
        return custom
    ucet = (day.get("dnesni_ucet") or "").split("\n", 1)[0].strip()
    if ucet:
        return ucet
    return f"Nové vydání · {datum_label}"


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
    site = site_url.rstrip("/")
    # Kopie: níž se do obsahu vkládají odkazy, cache musí zůstat čistá pro web.
    content = copy.deepcopy(
        build_den_content(day_path, paths, link_mode="pages", base_path=base_path)
    )
    edition_href = edition_pages_href(
        edition.obdobi, edition.schuze, edition.datum_unl, base_path
    )
    archive_href = archiv_pages_href(base_path)
    pivo_href = pivo_pages_href(base_path)
    edition_url = f"{site}{edition_href}"
    archive_url = f"{site}{archive_href}"
    pivo_url = f"{site}{pivo_href}"
    steno_href = steno_sources_pages_href(
        edition.obdobi, paths.schuze, edition.datum_unl, base_path
    )
    steno_page_url = (
        f"{site}{steno_href}"
        if steno_href and has_steno_sources(paths, edition.datum_unl)
        else ""
    )
    datum_label = datum_design(edition.datum_unl, content.den)
    day = read_json(day_path) if day_path.is_file() else {}
    subject = newsletter_subject(day, datum_label=datum_label)
    _apply_content_item_links(
        content,
        paths,
        obdobi=edition.obdobi,
        link_mode="pages",
        base_path=base_path,
        site_url=site,
    )
    _apply_email_links_absolute(content, site)
    _prepare_content_for_email(content)
    plain = plain_text_from_content(
        content,
        datum_label=datum_label,
        edition_url=edition_url,
        archive_url=archive_url,
        pivo_url=pivo_url,
    )
    css = _EMAIL_CSS.read_text(encoding="utf-8")
    tpl = _jinja_env().get_template("noviny-email.html")
    html = tpl.render(
        content=content,
        css=css,
        t=load_strings(),
        datum_design=datum_label,
        edition_url=edition_url,
        archive_url=archive_url,
        pivo_url=pivo_url,
        static_base=f"{site}/static",
        steno_page_url=steno_page_url,
    )
    return subject, plain, html


def render_doi_email_html(
    *,
    site_url: str | None = None,
    base_path: str = "",
) -> tuple[str, str, str]:
    """HTML + plain text pro potvrzovací e-mail (double opt-in) v Ecomailu."""
    from svejk.build.nav import soukromi_pages_href

    cfg = NewsletterConfig.from_env()
    site = (site_url or cfg.site_url).rstrip("/")
    t = load_strings()
    doi = t["doi"]
    base = base_path.rstrip("/")
    privacy_path = soukromi_pages_href(base)
    confirm_path = "/potvrzeno/"
    privacy_url = f"{site}{privacy_path}"
    confirm_redirect_url = f"{site}{confirm_path}"
    subject = doi["subject"]
    css = _DOI_EMAIL_CSS.read_text(encoding="utf-8")
    tpl = _jinja_env().get_template("doi-email.html")
    html = tpl.render(
        t=t,
        css=css,
        privacy_url=privacy_url,
        confirm_redirect_url=confirm_redirect_url,
        svejk_head_url=f"{site}/static/favicon.png",
        static_base=f"{site}/static",
    )
    plain = "\n".join(
        [
            doi["plain_lead"],
            "",
            doi["intro"],
            "",
            f"{doi['quote_key']} {doi['quote_body']}",
            "",
            doi["plain_cta"],
            "",
            doi["inbox_tip"],
            "",
            f"{doi['plain_after_confirm']} {confirm_redirect_url}",
            doi["footer"],
            f"{doi['privacy_link']}: {privacy_url}",
        ]
    )
    return subject, plain, html
