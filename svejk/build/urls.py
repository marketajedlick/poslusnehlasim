"""URL schéma webu: /vydani/YYYY-MM-DD/ a legacy cesty pro redirecty."""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from typing import Protocol


class _EditionDate(Protocol):
    datum_unl: str


def datum_unl_to_iso(datum_unl: str) -> str:
    return datetime.strptime(datum_unl, "%d.%m.%Y").strftime("%Y-%m-%d")


def datum_iso_to_unl(datum_iso: str) -> str:
    return datetime.strptime(datum_iso, "%Y-%m-%d").strftime("%d.%m.%Y")


def slugify(text: str, *, max_len: int = 48) -> str:
    norm = unicodedata.normalize("NFKD", text)
    ascii_text = norm.encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    return slug[:max_len] or "topic"


def edition_slug(edition: _EditionDate) -> str:
    return datum_unl_to_iso(edition.datum_unl)


def poslanec_slug(jmeno: str, prijmeni: str) -> str:
    return slugify(f"{jmeno} {prijmeni}")


def article_anchor_id(*, slug: str = "", num: int = 0) -> str:
    """HTML fragment pro deep-link na článek ve vydání."""
    return slug or f"article-{num}"


def edition_article_href(
    datum_unl: str,
    *,
    slug: str = "",
    num: int = 0,
    base_path: str = "",
) -> str:
    return f"{vydani_pages_href(datum_unl, base_path)}#{article_anchor_id(slug=slug, num=num)}"


def _join_href(base_path: str, path: str) -> str:
    if not path.startswith("/"):
        path = "/" + path
    base = base_path.rstrip("/")
    return f"{base}{path}" if base else path


def vydani_pages_href(datum_unl: str, base_path: str = "") -> str:
    iso = datum_unl_to_iso(datum_unl)
    return _join_href(base_path, f"/vydani/{iso}/")


def vydani_subpage_href(datum_unl: str, subpage: str, base_path: str = "") -> str:
    iso = datum_unl_to_iso(datum_unl)
    sub = subpage.strip("/")
    return _join_href(base_path, f"/vydani/{iso}/{sub}/")


def edition_export_relpath(datum_unl: str) -> str:
    return f"vydani/{datum_unl_to_iso(datum_unl)}/index.html"


def edition_subpage_export_relpath(datum_unl: str, subpage: str) -> str:
    return f"vydani/{datum_unl_to_iso(datum_unl)}/{subpage.strip('/')}/index.html"


def edition_legacy_pages_href(
    obdobi: int,
    schuze: int,
    datum_unl: str,
    base_path: str = "",
) -> str:
    return _join_href(
        base_path, f"/noviny/{obdobi}/{schuze}/{datum_unl}.html"
    )


def edition_legacy_short_href(
    obdobi: int,
    datum_unl: str,
    base_path: str = "",
) -> str:
    return _join_href(base_path, f"/noviny/{obdobi}/{datum_unl}.html")


def edition_legacy_subpage_href(
    obdobi: int,
    schuze: int,
    datum_unl: str,
    suffix: str,
    base_path: str = "",
) -> str:
    return _join_href(
        base_path, f"/noviny/{obdobi}/{schuze}/{datum_unl}-{suffix}.html"
    )


def archiv_legacy_href(base_path: str = "") -> str:
    return _join_href(base_path, "/archiv.html")


def slovnicek_legacy_href(base_path: str = "") -> str:
    return _join_href(base_path, "/slovnicek.html")
