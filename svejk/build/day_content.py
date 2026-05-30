"""Společný model dne pro markdown i HTML výstup."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from svejk.build.io import read_json
from svejk.listy import (
    _dnesni_ucet,
    _format_koho_veta,
    _shrnuti_radka,
    _vysledek_dne,
    _zaverecna_veta,
)
from svejk.noviny import _new_state
from svejk.paths import SchuzePaths
from svejk.timeline import BlokDne, DenSchuze, den_v_tydnu

_KICK_RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("zkumav", "zdrav", "nemocnic", "laborator", "diagnost"), "Zdravotnictví"),
    (("živnost", "pojistn", "odvod", "sociáln", "soc. zab"), "Živnostníci"),
    (("penzij", "důchod", "spoření"), "Penze"),
    (("stavebn", "developersk", "územní"), "Stavby"),
    (("investič", "finan", "bank"), "Finance"),
    (("rostlin", "postřik", "pesticid", "hnojen"), "Zemědělství"),
    (("výbor", "orgán", "volba", "personál", "komis"), "Personálka"),
    (("energ", "elektr", "plyn"), "Energetika"),
    (("doprav", "silnic", "železn"), "Doprava"),
)

_VERDIKT_STAMP = {
    "schvaleno": "Schváleno",
    "zamiteno": "Zamítnuto",
    "odlozeno": "Odloženo",
}


@dataclass
class DenItem:
    num: int
    kick: str
    nadpis: str
    lead: str
    mean: str
    dopad: str
    parliament_lead: str
    verdikt: str
    variant: str = ""

    @property
    def stamp(self) -> str:
        return _VERDIKT_STAMP.get(self.verdikt, "Schváleno")


@dataclass
class DenContent:
    datum: str
    den: str
    dnesni_ucet: str
    items: list[DenItem] = field(default_factory=list)
    proslo: int = 0
    zamitnuto: int = 0
    result_note: str = ""
    zaver: str = ""
    zaver_key: str = "Poslušně hlásím,"
    zaver_body: str = ""


def lead_z_fact(fact: dict[str, Any]) -> str:
    predmet = (fact.get("predmet_lidsky") or "").strip()
    verdikt = fact.get("verdikt", "schvaleno")
    n = fact.get("pocet_hlasovani", 0)

    if verdikt == "schvaleno":
        lead = f"poslanci schválili změny v {predmet}." if predmet else "poslanci schválili změnu."
    elif verdikt == "zamiteno":
        lead = f"poslanci zamítli změny v {predmet}." if predmet else "poslanci změnu zamítli."
    elif verdikt == "odlozeno":
        lead = f"poslanci odložili změny v {predmet}." if predmet else "poslanci změnu odložili."
    else:
        lead = f"poslanci řešili {predmet or 'bod programu'}."

    if n > 1 and verdikt == "schvaleno":
        lead = f"Po {n}× hlasování {lead[0].lower()}{lead[1:]}"
    return lead.strip().capitalize()


def dopad_z_fact(fact: dict[str, Any]) -> str:
    parts: list[str] = []
    for k in fact.get("koho") or []:
        if k and k not in parts:
            parts.append(k if k.startswith("Koho") else _format_koho_veta(k))
    for f in fact.get("fakty") or []:
        t = (f.get("text") or "").strip()
        if t and t not in parts:
            parts.append(t)
    return " ".join(parts)


def _kick_z_fact(fact: dict[str, Any]) -> str:
    blob = " ".join(
        [
            fact.get("nazev") or "",
            fact.get("nadpis") or "",
            fact.get("predmet_lidsky") or "",
        ]
    ).lower()
    for keys, label in _KICK_RULES:
        if any(k in blob for k in keys):
            return label
    nadpis = (fact.get("nadpis") or "").strip()
    if nadpis:
        first = re.split(r"[\s—–-]", nadpis, maxsplit=1)[0]
        if len(first) >= 4:
            return first
    return "Sněmovna"


def _lead_kratky(fact: dict[str, Any], topic: dict[str, Any] | None) -> str:
    if topic:
        vysv = (topic.get("tema_vysvetleni") or "").strip()
        if vysv:
            part = re.split(r"\s*[—–]\s*", vysv, maxsplit=1)[0].strip()
            if part.endswith("."):
                return part
            first = re.split(r"(?<=[.!?])\s+", part, maxsplit=1)[0].strip()
            if first:
                return first if first.endswith(".") else f"{first}."

    fakty = fact.get("fakty") or []
    if fakty:
        t = (fakty[0].get("text") or "").strip()
        if t:
            return t if t.endswith(".") else f"{t}."

    predmet = (fact.get("predmet_lidsky") or "").strip()
    if predmet:
        p = predmet[0].upper() + predmet[1:]
        return p if p.endswith(".") else f"{p}."

    return lead_z_fact(fact)


def _mean_z_dopadu(dopad: str, lead: str) -> str:
    if not dopad:
        return ""
    if lead and lead.rstrip(".") in dopad:
        rest = dopad.replace(lead.rstrip("."), "", 1).strip(" .")
        return rest or dopad
    return dopad


def split_zaver(text: str) -> tuple[str, str]:
    m = re.match(r"^(Poslušně hlásím,?)\s*(.*)$", text, re.I)
    if not m:
        return "", text
    body = m.group(2).strip()
    if body and not body[0].isupper():
        body = body[0].lower() + body[1:]
    return m.group(1), body


def datum_design(datum_unl: str, den: str) -> str:
    d = datetime.strptime(datum_unl, "%d.%m.%Y")
    return f"{den.capitalize()} {d.day:02d} / {d.month:02d} / {d.year}"


def _result_note(stats: dict[str, Any], *, state: dict) -> str:
    if stats.get("dlouha_debata"):
        return "Nejdřív se dlouho hádali o pořadu dne; zákony prošly až po dohadování."
    note = _shrnuti_radka(stats, state=state)
    if stats.get("zamitnuto", 0) > stats.get("proslo", 0):
        return note
    if stats.get("minuty", 0) >= 360:
        return "Schůze se protáhla — poslední body padly až večer."
    return ""


def _topics_by_slug(paths: SchuzePaths) -> dict[str, dict[str, Any]]:
    tp = paths.topics_json
    if not tp.is_file():
        return {}
    data = read_json(tp)
    return {t["slug"]: t for t in data.get("topics") or [] if t.get("slug")}


def build_den_content(
    day_path: Path,
    paths: SchuzePaths,
    *,
    state: dict | None = None,
) -> DenContent:
    if state is None:
        state = _new_state()
    state["poslusne_count"] = 0

    day = read_json(day_path)
    datum = day["datum"]
    den_cap = day.get("den") or den_v_tydnu(datum)
    stats = {
        "pocet_hlas": 0,
        "minuty": 0,
        "end_cas": "",
        "proslo": 0,
        "zamitnuto": 0,
        "dlouha_debata": False,
        **(day.get("stats") or {}),
    }
    slugs = day.get("topic_slugs") or []
    topics = _topics_by_slug(paths)

    content = DenContent(
        datum=datum,
        den=den_cap,
        dnesni_ucet=_dnesni_ucet(stats, state=state),
        proslo=int(stats.get("proslo") or 0),
        zamitnuto=int(stats.get("zamitnuto") or 0),
        result_note=_result_note(stats, state=state),
    )

    num = 0
    for slug in slugs:
        fp = paths.facts_by_topic / f"{slug}.json"
        if not fp.is_file():
            continue
        fact = read_json(fp)
        if not fact.get("publikovat"):
            continue
        dopad = dopad_z_fact(fact)
        if not dopad:
            continue

        num += 1
        parliament_lead = lead_z_fact(fact)
        short_lead = _lead_kratky(fact, topics.get(slug))
        content.items.append(
            DenItem(
                num=num,
                kick=_kick_z_fact(fact),
                nadpis=fact.get("nadpis") or slug,
                lead=short_lead,
                mean=_mean_z_dopadu(dopad, short_lead),
                dopad=dopad,
                parliament_lead=parliament_lead,
                verdikt=fact.get("verdikt", "schvaleno"),
                variant="i2" if num % 2 == 0 else "",
            )
        )

    zaver = _zaverecna_veta(stats, state=state)
    content.zaver = zaver
    content.zaver_key, content.zaver_body = split_zaver(zaver)

    return content


def vysledek_radky(content: DenContent, paths: SchuzePaths, day_path: Path) -> list[str]:
    day = read_json(day_path)
    slugs = day.get("topic_slugs") or []
    stats = {
        "pocet_hlas": 0,
        "minuty": 0,
        "end_cas": "",
        "proslo": 0,
        "zamitnuto": 0,
        "dlouha_debata": False,
        **(day.get("stats") or {}),
    }
    dummy_day = DenSchuze(datum=content.datum, den=content.den, bloky=[])
    zakony: list[BlokDne] = []
    for s in slugs:
        fp = paths.facts_by_topic / f"{s}.json"
        if not fp.is_file():
            continue
        f = read_json(fp)
        zakony.append(
            BlokDne(
                cas_od="12:00",
                cas_do="",
                typ="law",
                svejk="",
                nazev=f.get("nazev", s),
                proslo=bool(f.get("proslo", True)),
            )
        )
    state = _new_state()
    return _vysledek_dne(dummy_day, zakony, stats, state=state)
