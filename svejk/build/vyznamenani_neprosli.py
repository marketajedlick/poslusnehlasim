"""Samostatné stránky s tabulkami hlasování o vyznamenáních."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal

from svejk.build.io import read_json
from svejk.build.nav import vyznamenani_pages_href
from svejk.paths import SchuzePaths

VyznamenaniKind = Literal["neprosli", "prosli"]

_KLUB_ORDER = (
    "ANO",
    "ODS",
    "STAN",
    "Piráti",
    "KDU-ČSL",
    "TOP 09",
    "SPD",
    "Motoristé",
)

_PAGE_META: dict[VyznamenaniKind, dict[str, str]] = {
    "neprosli": {
        "title": "Kdo neprošel",
        "gloss": (
            "{pocet} návrhů na státní vyznamenání, které Sněmovna {datum} zamítla. "
            "U každého jména souhrn hlasů po poslaneckých klubech."
        ),
        "note": (
            "Potřebná je většina přítomných poslanců. U některých jmen proto padli i ti, "
            "kdo měli víc hlasů pro než proti."
        ),
    },
    "prosli": {
        "title": "Koho Sněmovna doporučila",
        "gloss": (
            "{pocet} jmen, která Sněmovna {datum} poslala prezidentovi jako doporučení "
            "k vyznamenání. U každého jména souhrn hlasů po poslaneckých klubech."
        ),
        "note": (
            "Prezident má poslední slovo. Tady jsou jen návrhy, které ve sněmovně "
            "získaly potřebnou většinu přítomných."
        ),
    },
}


def vyznamenani_json_path(
    paths: SchuzePaths, datum_unl: str, kind: VyznamenaniKind
) -> Path:
    from datetime import datetime

    d = datetime.strptime(datum_unl, "%d.%m.%Y")
    return paths.facts / f"vyznamenani-{kind}-{d.strftime('%Y-%m-%d')}.json"


def load_vyznamenani(
    paths: SchuzePaths, datum_unl: str, kind: VyznamenaniKind
) -> dict[str, Any] | None:
    fp = vyznamenani_json_path(paths, datum_unl, kind)
    if not fp.is_file():
        return None
    return read_json(fp)


def load_vyznamenani_neprosli(paths: SchuzePaths, datum_unl: str) -> dict[str, Any] | None:
    return load_vyznamenani(paths, datum_unl, "neprosli")


def vyznamenani_href(
    obdobi: int,
    schuze: int,
    datum_unl: str,
    kind: VyznamenaniKind,
    *,
    link_mode: str,
    base_path: str = "",
) -> str:
    if link_mode == "pages":
        return vyznamenani_pages_href(obdobi, schuze, datum_unl, kind, base_path)
    from datetime import datetime

    d = datetime.strptime(datum_unl, "%d.%m.%Y")
    return f"{d.strftime('%Y-%m-%d')}-{kind}.html"


def vyznamenani_neprosli_href(
    obdobi: int,
    schuze: int,
    datum_unl: str,
    *,
    link_mode: str,
    base_path: str = "",
) -> str:
    return vyznamenani_href(
        obdobi, schuze, datum_unl, "neprosli", link_mode=link_mode, base_path=base_path
    )


def inject_mean_link(text: str, phrase: str, href: str) -> str:
    if not text or not phrase or not href or phrase not in text:
        return text
    escaped = re.escape(phrase)
    repl = f'<a class="mean-link" href="{href}">{phrase}</a>'
    return re.sub(escaped, repl, text, count=1)


def inject_mean_links(text: str, links: list[tuple[str, str]]) -> str:
    out = text
    for phrase, href in sorted(links, key=lambda x: -len(x[0])):
        out = inject_mean_link(out, phrase, href)
    return out


def inject_mean_link_md(text: str, phrase: str, href: str) -> str:
    if not text or not phrase or not href or phrase not in text:
        return text
    escaped = re.escape(phrase)
    repl = f"[{phrase}]({href})"
    return re.sub(escaped, repl, text, count=1)


def inject_mean_links_md(text: str, links: list[tuple[str, str]]) -> str:
    out = text
    for phrase, href in sorted(links, key=lambda x: -len(x[0])):
        out = inject_mean_link_md(out, phrase, href)
    return out


def _kluby_proti_label(kluby: list[dict[str, Any]]) -> str:
    if not kluby:
        return "—"
    parts = [f"{k['klub']} {k['proti']}" for k in kluby if k.get("proti")]
    return ", ".join(parts) if parts else "—"


def _kluby_pro_label(kluby: list[dict[str, Any]]) -> str:
    if not kluby:
        return "—"
    ordered = sorted(
        kluby,
        key=lambda k: (
            _KLUB_ORDER.index(k["klub"])
            if k.get("klub") in _KLUB_ORDER
            else len(_KLUB_ORDER),
            -int(k.get("pro") or 0),
        ),
    )
    parts = [f"{k['klub']} {k['pro']}" for k in ordered if k.get("pro")]
    return ", ".join(parts) if parts else "—"


def table_rows(data: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in data.get("radky") or []:
        rows.append(
            {
                "jmeno": row.get("jmeno") or "",
                "skore": f"{row.get('pro', 0)}:{row.get('proti', 0)}",
                "kluby_pro": _kluby_pro_label(row.get("kluby_pro") or []),
                "kluby_proti": _kluby_proti_label(row.get("kluby_proti") or []),
            }
        )
    return rows


def page_meta(kind: VyznamenaniKind, *, pocet: int, datum_label: str) -> dict[str, str]:
    meta = _PAGE_META[kind]
    return {
        "title": meta["title"],
        "gloss": meta["gloss"].format(pocet=pocet, datum=datum_label),
        "note": meta["note"],
    }
