#!/usr/bin/env python3
"""Ohlásí čerstvě změněné stránky přes IndexNow (Bing, Seznam, Yandex…).

Čte živou sitemapu a pošle URL s lastmod za posledních N dní (+ úvod a /zakony/).
Spouští se po deployi v pages.yml; selhání deploy nezastaví.

  python scripts/indexnow.py [--days 2] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import date, timedelta
from pathlib import Path
from xml.etree import ElementTree

import re

_SEO = Path(__file__).resolve().parents[1] / "svejk" / "build" / "seo.py"
INDEXNOW_KEY = re.search(r'^INDEXNOW_KEY = "([0-9a-f]+)"', _SEO.read_text(encoding="utf-8"), re.M).group(1)

SITE = "https://poslusnehlasim.cz"
HOST = "poslusnehlasim.cz"
ENDPOINT = "https://api.indexnow.org/indexnow"
NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
ALWAYS = (f"{SITE}/", f"{SITE}/zakony/")


def fresh_urls(sitemap_xml: bytes, days: int) -> list[str]:
    since = date.today() - timedelta(days=days)
    root = ElementTree.fromstring(sitemap_xml)
    urls: list[str] = list(ALWAYS)
    for node in root.findall("s:url", NS):
        loc = (node.findtext("s:loc", default="", namespaces=NS) or "").strip()
        lastmod = (node.findtext("s:lastmod", default="", namespaces=NS) or "").strip()
        if not loc.startswith(SITE):
            continue
        try:
            if date.fromisoformat(lastmod[:10]) >= since:
                urls.append(loc)
        except ValueError:
            continue
    return list(dict.fromkeys(urls))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=2)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    req = urllib.request.Request(f"{SITE}/sitemap.xml", headers={"User-Agent": "poslusnehlasim-indexnow/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        urls = fresh_urls(resp.read(), args.days)
    payload = {
        "host": HOST,
        "key": INDEXNOW_KEY,
        "keyLocation": f"{SITE}/{INDEXNOW_KEY}.txt",
        "urlList": urls[:10000],
    }
    print(f"IndexNow: {len(urls)} URL")
    for u in urls:
        print(" ", u)
    if args.dry_run:
        return 0
    post = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(post, timeout=30) as resp:
        print("IndexNow HTTP", resp.status)
    return 0


if __name__ == "__main__":
    sys.exit(main())
