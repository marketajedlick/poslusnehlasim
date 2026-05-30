"""RSS kanál nových vydání (pro Buttondown automatizaci nebo čtečky)."""

from __future__ import annotations

import html
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring

from svejk.build.io import read_json
from svejk.build.nav import Edition, edition_pages_href, list_obdobi_editions
from svejk.newsletter.config import NewsletterConfig
from svejk.paths import SchuzePaths


def _edition_page_url(edition: Edition, *, site_url: str, base_path: str) -> str:
    href = edition_pages_href(
        edition.obdobi,
        edition.schuze,
        edition.datum_unl,
        base_path,
    )
    return f"{site_url.rstrip('/')}{href}"


def _edition_description(edition: Edition) -> str:
    from svejk.build.day_content import build_den_content

    paths = SchuzePaths.create(edition.obdobi, edition.schuze)
    d = datetime.strptime(edition.datum_unl, "%d.%m.%Y")
    day_path = paths.facts_by_day / f"{d.strftime('%Y-%m-%d')}.json"
    if not day_path.is_file():
        return ""
    content = build_den_content(day_path, paths)
    parts: list[str] = []
    if content.dnesni_ucet:
        parts.append(content.dnesni_ucet)
    for item in content.items[:3]:
        parts.append(item.nadpis)
    zaver = (content.zaver_body or content.zaver or "").strip()
    if zaver:
        parts.append(zaver)
    return " · ".join(parts)


def _pub_date(edition: Edition) -> str:
    when = edition.when.replace(tzinfo=timezone.utc)
    return format_datetime(when, usegmt=True)


def write_feed_xml(
    obdobi: int,
    out_path: Path,
    *,
    config: NewsletterConfig | None = None,
    base_path: str = "",
    max_items: int = 40,
) -> Path:
    cfg = config or NewsletterConfig.from_env()
    editions = list_obdobi_editions(obdobi)
    if not editions:
        raise FileNotFoundError(f"Žádná vydání pro období {obdobi}")

    channel = Element("channel")
    SubElement(channel, "title").text = "Poslušně hlásím"
    SubElement(channel, "link").text = cfg.site_url
    SubElement(channel, "description").text = (
        "Nová vydání deníku z Poslanecké sněmovny ve stylu Švejka."
    )
    SubElement(channel, "language").text = "cs"

    for edition in reversed(editions[-max_items:]):
        paths = SchuzePaths.create(edition.obdobi, edition.schuze)
        day = paths.facts_by_day / (
            datetime.strptime(edition.datum_unl, "%d.%m.%Y").strftime("%Y-%m-%d") + ".json"
        )
        if not day.is_file():
            continue
        day_json = read_json(day)
        from svejk.build.day_content import datum_design

        den = day_json.get("den") or ""
        title = datum_design(edition.datum_unl, den)
        link = _edition_page_url(edition, site_url=cfg.site_url, base_path=base_path)
        desc = _edition_description(edition)
        item = SubElement(channel, "item")
        SubElement(item, "title").text = title
        SubElement(item, "link").text = link
        SubElement(item, "guid", isPermaLink="true").text = link
        SubElement(item, "pubDate").text = _pub_date(edition)
        if desc:
            SubElement(item, "description").text = html.escape(desc)

    rss = Element("rss", version="2.0")
    rss.append(channel)
    xml = b'<?xml version="1.0" encoding="UTF-8"?>\n' + tostring(rss, encoding="utf-8")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(xml)
    return out_path
