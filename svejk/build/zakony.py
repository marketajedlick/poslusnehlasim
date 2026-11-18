"""Stránky zákonů: celá cesta jednoho návrhu od podání po účinnost.

Data jsou ručně kurátorovaná v `processed/zakony/{slug}.json` (redakce), build je
jen obohatí o odkazy na stenozáznamy a hlasování a ověří, že citace sedí na
stenoprotokol. Struktura souboru je popsaná v `processed/zakony/README.md`.

URL: `/zakony/` (rozcestník) a `/zakony/{slug}/` (detail).
"""

from __future__ import annotations

import json
import re
import warnings
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from svejk.build.nav import (
    edition_pages_href,
    slovnicek_term_pages_href,
    zakon_pages_href,
    zakony_pages_href,
)
from svejk.paths import SchuzePaths, processed_root
from svejk.text_norm import bez_dlouhych_pomlc

STAV_LABEL = {
    "hotovo": "Hotovo",
    "probiha": "Teď tady",
    "ceka": "Čeká",
    "neprobehlo": "Neproběhlo",
}

PSP_HLASOVANI_URL = "https://www.psp.cz/sqw/hlasy.sqw?g={id}"
PSP_TISK_URL = "https://www.psp.cz/sqw/historie.sqw?o={obdobi_psp}&t={tisk}"


def zakony_dir() -> Path:
    return processed_root() / "zakony"


@lru_cache(maxsize=None)
def _steno_refs(obdobi: int, schuze: int) -> dict[str, Any]:
    path = SchuzePaths.create(obdobi, schuze).aligned / "steno_refs.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def _votes(obdobi: int, schuze: int) -> dict[int, dict[str, Any]]:
    path = SchuzePaths.create(obdobi, schuze).votes_jsonl
    out: dict[int, dict[str, Any]] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            v = json.loads(line)
            out[int(v["cislo"])] = v
    return out


def _steno_session(steno_id: str) -> tuple[int, int] | None:
    m = re.match(r"^(\d{4})_(\d+)_\d+$", steno_id or "")
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def _norm_ws(text: str) -> str:
    return re.sub(r"\s+", " ", bez_dlouhych_pomlc(text or "")).strip()


def _bez_pomlcek(value: Any) -> Any:
    """Web nesmí mít em/en pomlčky (viz text_norm) — i ve stenových citacích."""
    if isinstance(value, str):
        return bez_dlouhych_pomlc(value)
    if isinstance(value, list):
        return [_bez_pomlcek(v) for v in value]
    if isinstance(value, dict):
        return {k: _bez_pomlcek(v) for k, v in value.items()}
    return value


def steno_ref(steno_id: str) -> dict[str, Any] | None:
    sess = _steno_session(steno_id)
    if not sess:
        return None
    return _steno_refs(*sess).get(steno_id)


def _enrich_citace(cit: dict[str, Any], *, slug: str) -> dict[str, Any]:
    out = dict(cit)
    ref = steno_ref(cit.get("steno_id", ""))
    if ref:
        out.setdefault("href", ref.get("url", ""))
        if cit.get("citace") and _norm_ws(cit["citace"]) not in _norm_ws(ref.get("text", "")):
            warnings.warn(
                f"zakony/{slug}: citace {cit.get('steno_id')} ({cit.get('jmeno')}) "
                "nesedí na stenoprotokol",
                stacklevel=2,
            )
    autor = cit.get("jmeno", "")
    if cit.get("strana"):
        autor = f"{autor} ({cit['strana']})"
    out["autor"] = autor
    return out


def _enrich_hlasovani(h: dict[str, Any], *, obdobi: int, schuze: int | None) -> dict[str, Any]:
    out = dict(h)
    if schuze is not None and h.get("cislo") is not None:
        v = _votes(obdobi, schuze).get(int(h["cislo"]))
        if v:
            for key in ("pro", "proti", "zdrzel", "pritomno", "cas", "datum"):
                out.setdefault(key, v.get(key))
            out.setdefault("prijato", v.get("vysledek") == "A")
            if v.get("id_hlasovani"):
                out.setdefault("href", PSP_HLASOVANI_URL.format(id=v["id_hlasovani"]))
    pro = int(out.get("pro") or 0)
    proti = int(out.get("proti") or 0)
    total = max(pro + proti, 1)
    out["pro_pct"] = round(100 * pro / total, 1)
    out["proti_pct"] = round(100 - out["pro_pct"], 1)
    out.setdefault("prijato", pro > proti)
    return out


def _enrich_faze(faze: dict[str, Any], *, obdobi: int, base_path: str) -> dict[str, Any]:
    out = dict(faze)
    out["stav_label"] = STAV_LABEL.get(faze.get("stav", ""), "")
    if faze.get("slovnicek"):
        out["slovnicek_href"] = slovnicek_term_pages_href(faze["slovnicek"], base_path)
        out["slovnicek_label"] = faze.get("slovnicek_label") or "Co to je? →"
    schuze = faze.get("schuze")
    existing = _site_edition_keys(obdobi)

    def _vydani_link(v: dict[str, Any]) -> dict[str, Any] | None:
        datum = v.get("datum_unl", "")
        if not datum or not v.get("schuze"):
            return None
        if existing and (int(v["schuze"]), datum) not in existing:
            return None
        href = edition_pages_href(obdobi, int(v["schuze"]), datum, base_path)
        if v.get("slug"):
            href = f"{href}#{v['slug']}"
        return {**v, "href": href}

    kroky = []
    for krok in faze.get("kroky") or []:
        k = dict(krok)
        k_schuze = krok.get("schuze", schuze)
        if krok.get("hlasovani"):
            k["hlasovani"] = _enrich_hlasovani(krok["hlasovani"], obdobi=obdobi, schuze=k_schuze)
        if krok.get("hlasovani_skupina"):
            k["hlasovani_skupina"] = [
                _enrich_hlasovani(h, obdobi=obdobi, schuze=k_schuze)
                for h in krok["hlasovani_skupina"]
            ]
        if krok.get("steno_id"):
            ref = steno_ref(krok["steno_id"])
            if ref:
                k.setdefault("steno_href", ref.get("url", ""))
        if krok.get("vydani"):
            k["vydani"] = _vydani_link(krok["vydani"])
        kroky.append(k)
    out["kroky"] = kroky
    out["vydani"] = [x for x in (_vydani_link(v) for v in faze.get("vydani") or []) if x]
    return out


@lru_cache(maxsize=None)
def _site_edition_keys(obdobi: int) -> frozenset[tuple[int, str]]:
    """(schuze, datum_unl) vydání, která jsou na webu — na jiná neodkazujeme."""
    from svejk.build.publish import list_site_editions

    return frozenset((e.schuze, e.datum_unl) for e in list_site_editions(obdobi))


def _side(data: dict[str, Any] | None, *, slug: str) -> dict[str, Any]:
    if not data:
        return {}
    out = dict(data)
    out["citace"] = [_enrich_citace(c, slug=slug) for c in data.get("citace") or []]
    return out


def _datum_label(datum: str) -> str:
    """'23.10.2026' → '23. 10. 2026'."""
    try:
        d = datetime.strptime(datum, "%d.%m.%Y")
    except (TypeError, ValueError):
        return datum or ""
    return f"{d.day}. {d.month}. {d.year}"


def load_zakon(path: Path, *, base_path: str = "") -> dict[str, Any]:
    raw = _bez_pomlcek(json.loads(path.read_text(encoding="utf-8")))
    slug = raw.get("slug") or path.stem
    obdobi = int(raw.get("obdobi", 2025))
    z = dict(raw)
    z["slug"] = slug
    z["href"] = zakon_pages_href(slug, base_path)
    z["faze"] = [_enrich_faze(f, obdobi=obdobi, base_path=base_path) for f in raw.get("faze") or []]
    z["vlada"] = _side(raw.get("vlada"), slug=slug)
    z["opozice"] = _side(raw.get("opozice"), slug=slug)
    z["aktualizovano_label"] = _datum_label(raw.get("aktualizovano", ""))
    if raw.get("tisk"):
        z.setdefault(
            "psp_href",
            PSP_TISK_URL.format(obdobi_psp=obdobi_psp(obdobi), tisk=raw["tisk"]),
        )
    done = sum(1 for f in z["faze"] if f.get("stav") == "hotovo")
    z["faze_hotovo"] = done
    z["faze_celkem"] = len(z["faze"])
    current = next((f for f in z["faze"] if f.get("stav") == "probiha"), None)
    z["faze_aktualni"] = current.get("nazev", "") if current else ""
    return z


def obdobi_psp(obdobi: int) -> int:
    """Číslo volebního období v URL psp.cz (2025 → 10)."""
    return {2017: 8, 2021: 9, 2025: 10}.get(obdobi, 10)


def list_zakony(base_path: str = "") -> list[dict[str, Any]]:
    d = zakony_dir()
    if not d.is_dir():
        return []
    out = [load_zakon(p, base_path=base_path) for p in sorted(d.glob("*.json"))]
    out = [z for z in out if z.get("publikovat", True)]
    out.sort(key=lambda z: z.get("aktualizovano_iso", ""), reverse=True)
    return out


@lru_cache(maxsize=None)
def _topic_index() -> dict[str, tuple[str, str]]:
    """slug tématu z vydání → (slug zákona, krátký název zákona)."""
    idx: dict[str, tuple[str, str]] = {}
    d = zakony_dir()
    if not d.is_dir():
        return idx
    for p in sorted(d.glob("*.json")):
        raw = json.loads(p.read_text(encoding="utf-8"))
        if not raw.get("publikovat", True):
            continue
        slug = raw.get("slug") or p.stem
        for topic_slug in raw.get("temata") or []:
            idx[topic_slug] = (slug, raw.get("nazev_kratky") or raw.get("nazev", ""))
    return idx


def zakony_for_slovnicek(term_slug: str, base_path: str = "") -> list[dict[str, str]]:
    """Zákony, na jejichž stránce je fáze s odkazem na daný pojem slovníčku."""
    out = []
    for z in list_zakony(base_path):
        faze = next((f for f in z["faze"] if f.get("slovnicek") == term_slug), None)
        if faze:
            out.append(
                {
                    "href": f"{z['href']}#faze-{faze['id']}",
                    "label": z.get("nazev", ""),
                    "faze": faze.get("nazev", ""),
                    "stav": faze.get("stav_label", ""),
                }
            )
    return out


def zakon_for_topic(topic_slug: str, base_path: str = "") -> tuple[str, str] | None:
    """(href, label) stránky zákona pro článek ve vydání, nebo None."""
    hit = _topic_index().get(topic_slug or "")
    if not hit:
        return None
    slug, label = hit
    return zakon_pages_href(slug, base_path), label


__all__ = [
    "list_zakony",
    "load_zakon",
    "zakon_for_topic",
    "zakon_pages_href",
    "zakony_dir",
    "zakony_pages_href",
]
