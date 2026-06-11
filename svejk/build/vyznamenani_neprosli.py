"""Samostatné stránky s tabulkami hlasování o vyznamenáních."""

from __future__ import annotations

import json
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
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in data.get("radky") or []:
        stats = _row_vote_stats(row, votes_by_cislo or {})
        item = {
            "jmeno": row.get("jmeno") or "",
            "skore": f"{row.get('pro', 0)}:{row.get('proti', 0)}",
            "kluby_pro": _kluby_pro_label(row.get("kluby_pro") or []),
            "kluby_proti": _kluby_proti_label(row.get("kluby_proti") or []),
        }
        if stats["pritomno"]:
            item["pritomno"] = str(stats["pritomno"])
            item["potreba"] = str(stats["potreba"])
            item["zdrzel"] = str(stats["zdrzel"])
            item["nehlasoval"] = str(stats["nehlasoval"])
            if kind == "neprosli":
                item["chybelo"] = str(stats["chybelo"]) if stats["chybelo"] else "0"
        rows.append(item)
    return rows


def page_explain(
    kind: VyznamenaniKind,
    data: dict[str, Any],
    votes_by_cislo: dict[int, dict[str, int]],
) -> list[str]:
    stats_list = [_row_vote_stats(r, votes_by_cislo) for r in data.get("radky") or []]
    pritomnosti = [s["pritomno"] for s in stats_list if s["pritomno"]]
    potreby = [s["potreba"] for s in stats_list if s["potreba"]]
    if not pritomnosti or not potreby:
        return []

    min_p, max_p = min(pritomnosti), max(pritomnosti)
    min_need, max_need = min(potreby), max(potreby)

    if kind == "neprosli":
        paras = [
            (
                "Nestáčí mít víc hlasů pro než proti. Návrh projde jen tehdy, když je pro "
                "víc než polovina poslanců přítomných ve sněmovně — ti, kdo se zdrželi "
                "nebo vůbec nehlasovali, laťku zvedají stejně jako volič proti."
            ),
            (
                f"Čtvrtého června bylo v sále {min_p} až {max_p} poslanců, takže ke schválení "
                f"většinou stačilo {min_need} až {max_need} hlasů pro."
            ),
        ]
        examples: list[str] = []
        for row in data.get("radky") or []:
            s = _row_vote_stats(row, votes_by_cislo)
            if not s["chybelo"]:
                continue
            jmeno = row.get("jmeno") or ""
            if jmeno == "Luboš Dobrovský":
                examples.append(
                    f"Luboš Dobrovský dostal {s['pro']} proti {row.get('proti', 0)}, "
                    f"přítomných bylo {s['pritomno']}, stačilo {s['potreba']} — "
                    f"chyběly {s['chybelo']} hlasy. Zbytek se zdržel ({s['zdrzel']}) "
                    f"nebo nehlasoval ({s['nehlasoval']})."
                )
            elif jmeno == "Václav Moravec":
                examples.append(
                    f"Václav Moravec měl {s['pro']}:{row.get('proti', 0)}, ale při "
                    f"{s['pritomno']} přítomných potřeboval {s['potreba']} hlasů pro — "
                    f"hlavně kvůli masivnímu záporu v ANO."
                )
            if len(examples) >= 2:
                break
        paras.extend(examples)
        return paras

    return [
        (
            "Ke schválení nestačilo mít víc hlasů pro než proti. Potřebná byla většina "
            "přítomných poslanců — typicky víc než polovina těch, kdo byli ve sále."
        ),
        (
            f"Čtvrtého června bylo přítomno {min_p} až {max_p} poslanců, takže většinou "
            f"stačilo {min_need} až {max_need} hlasů pro."
        ),
    ]


def page_meta(kind: VyznamenaniKind, *, pocet: int, datum_label: str) -> dict[str, str]:
    meta = _PAGE_META[kind]
    return {
        "title": meta["title"],
        "gloss": meta["gloss"].format(pocet=pocet, datum=datum_label),
        "note": meta["note"],
    }
