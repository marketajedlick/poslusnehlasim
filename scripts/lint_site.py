#!/usr/bin/env python3
"""Kontrola vyexportovaného webu (site/) na chyby, které vidí čtenář.

Použití: python scripts/lint_site.py site
Exit 1, pokud najde chybu. Běží v CI po export-pages.
"""

from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

# Vzory v textu, které vznikají chybou převodu čísel na slova.
_TEXT_PATTERNS = {
    "rok_navic": re.compile(r"\b(?:ledna|února|března|dubna|května|června|července|srpna|září|října|listopadu|prosince|letech|až) rok (?:19|20)\d\d\b"),
    "radova_slovy": re.compile(
        r"\b(?:jedna|dva|dvě|tři|čtyři|pět|šest|sedm|osm|devět|deset|jedenáct|dvanáct|"
        r"dvacet|třicet|čtyřicet|padesát)\. (?:hodin|čtení|schůz|bod|kol)"
    ),
    "desetinne_slovy": re.compile(r"\b(?:nula|jedna|dva|tři|čtyři|pět|šest|sedm|osm|devět),(?:nula|jedna|dva|tři|čtyři|pět|šest|sedm|osm|devět)\b"),
    "procenta_slovy": re.compile(r"\b(?:jedna|dva|tři|čtyři|pět|šest|sedm|osm|devět|deset|dvacet|třicet|čtyřicet|padesát|šedesát|sedmdesát|osmdesát|devadesát) %"),
    "dlouha_pomlcka": re.compile("[–—]"),
}


class _Lint(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.a_depth = 0
        self.nested_a = 0
        self.h1 = 0
        self.skip = 0
        self.text: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            if self.a_depth:
                self.nested_a += 1
            self.a_depth += 1
        elif tag == "h1":
            self.h1 += 1
        elif tag in ("script", "style"):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag == "a" and self.a_depth:
            self.a_depth -= 1
        elif tag in ("script", "style") and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.text.append(data)


def _is_redirect(html: str) -> bool:
    return 'http-equiv="refresh"' in html[:2000]


def lint_file(path: Path, rel: str) -> list[str]:
    html = path.read_text(encoding="utf-8")
    if _is_redirect(html):
        return []
    p = _Lint()
    p.feed(html)
    errors: list[str] = []
    if p.nested_a:
        errors.append(f"{rel}: vnořené <a> ({p.nested_a}×)")
    is_edition = rel.startswith("vydani/") and rel.count("/") in (2, 3) and "/steno/" not in rel
    if is_edition and rel.split("/")[1][:2] == "20" and p.h1 == 0:
        errors.append(f"{rel}: chybí <h1>")
    text = " ".join(" ".join(p.text).split())
    for code, rx in _TEXT_PATTERNS.items():
        m = rx.search(text)
        if m:
            ctx = text[max(0, m.start() - 30) : m.end() + 30]
            errors.append(f"{rel}: {code}: …{ctx}…")
    return errors


def main(argv: list[str]) -> int:
    root = Path(argv[1] if len(argv) > 1 else "site")
    if not root.is_dir():
        print(f"Chybí složka {root}", file=sys.stderr)
        return 2
    errors: list[str] = []
    for path in sorted(root.rglob("*.html")):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(("preview/", "admin/", "share/")):
            continue
        errors.extend(lint_file(path, rel))
    for e in errors:
        print(e)
    print(f"lint_site: {len(errors)} chyb", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
