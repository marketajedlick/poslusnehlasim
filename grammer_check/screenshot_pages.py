#!/usr/bin/env python3
"""Full-page screenshots of Poslušně hlásím newspaper editions."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from playwright.sync_api import Page, sync_playwright

ARCHIV_URL = "https://poslusnehlasim.cz/archiv.html"
VIEWPORT_WIDTH = 900
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
EDITION_RE = re.compile(r"/noviny/(\d+)/(\d+)/([^/]+)\.html$")


def parse_edition_url(url: str) -> tuple[str, int, int, str] | None:
    match = EDITION_RE.search(urlparse(url).path)
    if not match:
        return None
    obdobi, schuze, datum = match.groups()
    base = url.rsplit("/noviny/", 1)[0] or f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    return base, int(obdobi), int(schuze), datum


def edition_url(base: str, obdobi: int, schuze: int, datum_unl: str) -> str:
    return f"{base.rstrip('/')}/noviny/{obdobi}/{schuze}/{datum_unl}.html"


def discover_pages_archiv(page: Page, archiv_url: str) -> list[str]:
    page.goto(archiv_url, wait_until="networkidle")
    page.evaluate("() => document.fonts.ready")

    urls: list[str] = []
    seen: set[str] = set()

    for link in page.locator("a.archive-chip[href]").all():
        href = link.get_attribute("href")
        if not href:
            continue
        url = urljoin(archiv_url, href)
        if url in seen or not parse_edition_url(url):
            continue
        seen.add(url)
        urls.append(url)

    return urls


def discover_pages_local_all(base: str, obdobi: int = 2025) -> list[str]:
    processed = REPO_ROOT / "processed"
    if not processed.is_dir():
        return []

    urls: list[str] = []
    for schuze_dir in sorted(processed.glob(f"{obdobi}-s*")):
        match = re.search(r"-s(\d+)$", schuze_dir.name)
        if not match:
            continue
        schuze = int(match.group(1))
        out_dir = schuze_dir / "out" / "noviny-dlouhe"
        if not out_dir.is_dir():
            continue
        for html_file in sorted(out_dir.glob("*.html")):
            datum_unl = f"{html_file.stem[8:10]}.{html_file.stem[5:7]}.{html_file.stem[0:4]}"
            urls.append(edition_url(base, obdobi, schuze, datum_unl))
    return urls


def discover_pages_local_schuze(base: str, obdobi: int, schuze: int) -> list[str]:
    out_dir = REPO_ROOT / "processed" / f"{obdobi}-s{schuze}" / "out" / "noviny-dlouhe"
    if not out_dir.is_dir():
        return []
    urls: list[str] = []
    for html_file in sorted(out_dir.glob("*.html")):
        datum_unl = f"{html_file.stem[8:10]}.{html_file.stem[5:7]}.{html_file.stem[0:4]}"
        urls.append(edition_url(base, obdobi, schuze, datum_unl))
    return urls


def _nav_href(page: Page, side: str) -> str | None:
    selector = f".edition-arrow.{side}:not(.disabled)"
    link = page.locator(selector)
    if link.count() == 0:
        return None
    href = link.first.get_attribute("href")
    if not href:
        return None
    return urljoin(page.url, href)


def discover_pages_crawl(
    page: Page,
    start_url: str,
    *,
    obdobi: int,
    schuze: int,
) -> list[str]:
    page.goto(start_url, wait_until="networkidle")
    page.evaluate("() => document.fonts.ready")

    def same_schuze(url: str) -> bool:
        parsed = parse_edition_url(url)
        return parsed is not None and parsed[1] == obdobi and parsed[2] == schuze

    first_url = page.url
    while True:
        prev_href = _nav_href(page, "prev")
        if not prev_href:
            break
        prev_url = urljoin(page.url, prev_href)
        if not same_schuze(prev_url):
            break
        page.goto(prev_url, wait_until="networkidle")
        page.evaluate("() => document.fonts.ready")
        first_url = page.url

    urls = [first_url] if same_schuze(first_url) else []
    current = first_url
    seen = {current}
    while True:
        page.goto(current, wait_until="networkidle")
        next_href = _nav_href(page, "next")
        if not next_href:
            break
        next_url = urljoin(page.url, next_href)
        if next_url in seen or not same_schuze(next_url):
            break
        seen.add(next_url)
        urls.append(next_url)
        current = next_url

    return urls


def screenshot_filename(url: str) -> str:
    parsed = parse_edition_url(url)
    if parsed:
        _, obdobi, schuze, datum = parsed
        return f"{obdobi}-s{schuze}-{datum}.png"
    slug = re.sub(r"[^\w.-]+", "_", urlparse(url).path.strip("/")) or "page"
    return f"{slug}.png"


def wait_for_page(page: Page) -> None:
    page.wait_for_load_state("networkidle")
    page.evaluate("() => document.fonts.ready")
    page.locator("#page-front-sheet").wait_for(state="visible", timeout=15_000)


def take_screenshot(page: Page, url: str, out_dir: Path, *, full_page: bool) -> Path:
    page.goto(url, wait_until="networkidle")
    wait_for_page(page)
    out_path = out_dir / screenshot_filename(url)
    page.screenshot(path=str(out_path), full_page=full_page)
    return out_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Udělá celostránkové screenshoty vydání deníku z poslusnehlasim.cz.",
    )
    parser.add_argument(
        "url",
        nargs="?",
        default=ARCHIV_URL,
        help=f"Výchozí: {ARCHIV_URL}",
    )
    parser.add_argument(
        "-o",
        "--out",
        type=Path,
        default=SCRIPT_DIR / "screenshots",
        help="Složka pro PNG (výchozí: grammer_check/screenshots)",
    )
    parser.add_argument(
        "--only",
        metavar="EDITION_URL",
        help="Jen jedna konkrétní stránka vydání",
    )
    parser.add_argument(
        "--schuze",
        type=int,
        metavar="N",
        help="Jen jedna schůze (URL musí být libovolné vydání z té schůze)",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Seznam URL z processed/ místo archivu na webu",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Přeskočit PNG, které už ve výstupní složce jsou",
    )
    parser.add_argument(
        "--limit",
        type=int,
        metavar="N",
        help="Vyfoť jen prvních N stránek (pro test)",
    )
    parser.add_argument(
        "--viewport",
        type=int,
        default=VIEWPORT_WIDTH,
        help=f"Šířka viewportu v px (výchozí: {VIEWPORT_WIDTH})",
    )
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)

    base = "https://poslusnehlasim.cz"
    archiv_url = args.url if "archiv" in urlparse(args.url).path else ARCHIV_URL

    if args.only:
        urls = [args.only]
    elif args.schuze:
        parsed = parse_edition_url(args.url)
        obdobi = parsed[1] if parsed else 2025
        urls = discover_pages_local_schuze(base, obdobi, args.schuze) if args.local else []
    elif args.local:
        urls = discover_pages_local_all(base)
        print(f"Lokální seznam: {len(urls)} stránek z processed/", file=sys.stderr)
    else:
        urls = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(
            viewport={"width": args.viewport, "height": 900},
            device_scale_factor=2,
        )

        if not urls and args.schuze:
            if args.local:
                print(f"Lokální HTML pro schůzi {args.schuze} nenalezena.", file=sys.stderr)
                browser.close()
                return 1
            archiv_pages = discover_pages_archiv(page, archiv_url)
            seed = [u for u in archiv_pages if (p := parse_edition_url(u)) and p[2] == args.schuze]
            if not seed:
                print(f"Ve archivu není schůze {args.schuze}.", file=sys.stderr)
                browser.close()
                return 1
            urls = discover_pages_crawl(page, seed[0], obdobi=obdobi, schuze=args.schuze)
        elif not urls:
            urls = discover_pages_archiv(page, archiv_url)
            print(f"Archiv: {len(urls)} vydání z {archiv_url}", file=sys.stderr)

        if args.limit:
            urls = urls[: args.limit]

        if not urls:
            print("Nenalezena žádná stránka k vyfocení.", file=sys.stderr)
            browser.close()
            return 1

        print(f"Počet stránek: {len(urls)}")
        done = 0
        skipped = 0
        for index, url in enumerate(urls, start=1):
            out_path = args.out / screenshot_filename(url)
            if args.skip_existing and out_path.is_file():
                skipped += 1
                print(f"[{index}/{len(urls)}] přeskočeno (existuje): {out_path.name}")
                continue
            out_path = take_screenshot(page, url, args.out, full_page=True)
            done += 1
            print(f"[{index}/{len(urls)}] {url} -> {out_path}")

        browser.close()

    summary = f"Hotovo: {done} nových screenshotů"
    if skipped:
        summary += f", {skipped} přeskočeno"
    print(f"{summary} v {args.out.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
