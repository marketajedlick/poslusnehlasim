"""Samostatné stránky s tabulkami hlasování o vyznamenáních."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal

from svejk.build.io import read_json
from svejk.build.nav import vyznamenani_pages_href
from svejk.paths import SchuzePaths

VyznamenaniKind = Literal["neprosli", "prosli", "zvoleni"]

_JSON_BASENAME: dict[VyznamenaniKind, str] = {
    "neprosli": "vyznamenani-neprosli",
    "prosli": "vyznamenani-prosli",
    "zvoleni": "hlasovani-zvoleni",
}

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
            "Sloupec Chybělo ukazuje, kolik hlasů pro ještě nestačilo na většinu přítomných."
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
    "zvoleni": {
        "title": "Koho Sněmovna zvolila do Rady ČT",
        "gloss": (
            "{pocet} nových členů Rady České televize, které Sněmovna {datum} "
            "obsadila veřejnou volbou. U každého jména souhrn hlasů po poslaneckých klubech."
        ),
        "note": (
            "Volba byla veřejná. Ke zvolení stačilo mít víc hlasů pro než proti "
            "a splnit kvorum přítomných."
        ),
    },
}


def vyznamenani_json_path(
    paths: SchuzePaths, datum_unl: str, kind: VyznamenaniKind
) -> Path:
    from datetime import datetime

    d = datetime.strptime(datum_unl, "%d.%m.%Y")
    basename = _JSON_BASENAME[kind]
    return paths.facts / f"{basename}-{d.strftime('%Y-%m-%d')}.json"


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


def resolve_vyznamenani_page_links(
    paths: SchuzePaths,
    datum_unl: str,
    links: list[tuple[str, str]],
    *,
    obdobi: int,
    schuze: int,
    link_mode: str,
    base_path: str = "",
) -> list[tuple[str, str]]:
    """Přeloží (popisek, prosli|neprosli) na (popisek, href) jen když data existují."""
    out: list[tuple[str, str]] = []
    for label, page in links:
        if page not in _JSON_BASENAME:
            continue
        kind: VyznamenaniKind = page  # type: ignore[assignment]
        if not load_vyznamenani(paths, datum_unl, kind):
            continue
        href = vyznamenani_href(
            obdobi, schuze, datum_unl, kind, link_mode=link_mode, base_path=base_path
        )
        out.append((label, href))
    return out


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


def _sort_kluby(kluby: list[dict[str, Any]], count_key: str) -> list[dict[str, Any]]:
    return sorted(
        kluby,
        key=lambda k: (
            _KLUB_ORDER.index(k["klub"])
            if k.get("klub") in _KLUB_ORDER
            else len(_KLUB_ORDER),
            -int(k.get(count_key) or 0),
        ),
    )


def _kluby_chips(kluby: list[dict[str, Any]], count_key: str) -> list[dict[str, str]]:
    chips: list[dict[str, str]] = []
    for k in _sort_kluby(kluby, count_key):
        n = int(k.get(count_key) or 0)
        if n:
            chips.append({"klub": k["klub"], "n": str(n)})
    return chips


def _load_votes_by_cislo(paths: SchuzePaths, datum_unl: str) -> dict[int, dict[str, int]]:
    fp = paths.raw / "votes.jsonl"
    if not fp.is_file():
        return {}
    out: dict[int, dict[str, int]] = {}
    for line in fp.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        v = json.loads(line)
        if v.get("datum") != datum_unl:
            continue
        out[int(v["cislo"])] = {
            "pro": int(v.get("pro") or 0),
            "proti": int(v.get("proti") or 0),
            "zdrzel": int(v.get("zdrzel") or 0),
            "nehlasoval": int(v.get("nehlasoval") or 0),
            "pritomno": int(v.get("pritomno") or 0),
        }
    return out


def _potreba_pro(pritomno: int) -> int:
    """Většina přítomných: pro musí být víc než polovina."""
    return pritomno // 2 + 1


def _row_vote_stats(
    row: dict[str, Any], votes_by_cislo: dict[int, dict[str, int]]
) -> dict[str, int]:
    cislo = int(row.get("cislo_hlasovani") or 0)
    v = votes_by_cislo.get(cislo, {})
    pro = int(row.get("pro") or v.get("pro") or 0)
    pritomno = int(v.get("pritomno") or 0)
    potreba = _potreba_pro(pritomno) if pritomno else 0
    return {
        "pro": pro,
        "pritomno": pritomno,
        "potreba": potreba,
        "chybelo": max(0, potreba - pro) if potreba else 0,
        "zdrzel": int(v.get("zdrzel") or 0),
        "nehlasoval": int(v.get("nehlasoval") or 0),
    }


def table_rows(
    data: dict[str, Any],
    *,
    kind: VyznamenaniKind,
    votes_by_cislo: dict[int, dict[str, int]] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in data.get("radky") or []:
        stats = _row_vote_stats(row, votes_by_cislo or {})
        pro = int(row.get("pro") or stats["pro"] or 0)
        proti = int(row.get("proti") or 0)
        if kind == "zvoleni" and proti:
            stats = {**stats, "potreba": proti + 1}
        item: dict[str, Any] = {
            "jmeno": row.get("jmeno") or "",
            "pro": str(pro),
            "proti": str(proti),
            "kluby_pro_chips": _kluby_chips(row.get("kluby_pro") or [], "pro"),
            "kluby_proti_chips": _kluby_chips(row.get("kluby_proti") or [], "proti"),
        }
        if stats["pritomno"]:
            item["pritomno"] = str(stats["pritomno"])
            item["potreba"] = str(stats["potreba"])
            item["zdrzel"] = str(stats["zdrzel"])
            item["nehlasoval"] = str(stats["nehlasoval"])
            if kind == "neprosli":
                item["chybelo"] = str(stats["chybelo"]) if stats["chybelo"] else "0"
        varovani = row.get("varovani")
        if isinstance(varovani, dict) and (varovani.get("shrnuti") or varovani.get("citace")):
            item["varovani"] = {
                k: str(v).strip()
                for k, v in varovani.items()
                if k in ("rečník", "shrnuti", "citace") and str(v).strip()
            }
        rows.append(item)
    if kind == "neprosli":
        rows.sort(
            key=lambda r: (
                int(r.get("chybelo") or 999),
                -int(r.get("pro") or 0),
                (r.get("jmeno") or "").casefold(),
            )
        )
    elif kind in ("prosli", "zvoleni"):
        rows.sort(
            key=lambda r: (
                -int(r.get("pro") or 0),
                (r.get("jmeno") or "").casefold(),
            )
        )
    return rows


_MAJORITY_EXPLAIN = (
    "Nestáčí mít víc hlasů pro než proti. Návrh projde jen tehdy, když je pro "
    "víc než polovina poslanců přítomných ve sněmovně ti, kdo se zdrželi "
    "nebo vůbec nehlasovali, laťku zvedají stejně jako volič proti."
)

_ZVOLENI_EXPLAIN = (
    "Ke zvolení musel kandidát získat víc hlasů pro než proti "
    "a splnit kvorum přítomných poslanců."
)


def page_explain(
    kind: VyznamenaniKind,
    data: dict[str, Any],
    votes_by_cislo: dict[int, dict[str, int]],
) -> list[str]:
    if not votes_by_cislo:
        return []
    if kind == "zvoleni":
        return [_ZVOLENI_EXPLAIN]
    return [_MAJORITY_EXPLAIN]


def page_meta(kind: VyznamenaniKind, *, pocet: int, datum_label: str) -> dict[str, str]:
    meta = _PAGE_META[kind]
    return {
        "title": meta["title"],
        "gloss": meta["gloss"].format(pocet=pocet, datum=datum_label),
        "note": meta["note"],
    }
