"""Společný model dne pro markdown i HTML výstup."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from svejk.build.io import read_json
from svejk.text_norm import bez_dlouhych_pomlc
from svejk.build.witty import (
    glosa_generic,
    lead_svejkovsky,
    mean_vysvetleni,
    nadpis_z_clanku,
)
from svejk.listy import (
    _dnesni_ucet,
    _format_koho_veta,
    _glosa_je_nedostatecna,
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

_MESICE_GEN = (
    "ledna",
    "února",
    "března",
    "dubna",
    "května",
    "června",
    "července",
    "srpna",
    "září",
    "října",
    "listopadu",
    "prosince",
)


@dataclass
class DenItem:
    num: int
    kick: str
    nadpis: str
    nadpis_radky: list[str]
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
    cal_den: str
    cal_day: str
    cal_month: str
    dnesni_ucet: str
    items: list[DenItem] = field(default_factory=list)
    proslo: int = 0
    zamitnuto: int = 0
    board_stats: str = ""
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
        first = re.split(r"[\s\-]", nadpis, maxsplit=1)[0]
        if len(first) >= 4:
            return first
    return "Sněmovna"


def _lead_kratky(fact: dict[str, Any], topic: dict[str, Any] | None) -> str:
    fakty = fact.get("fakty") or []
    vysv = (topic.get("tema_vysvetleni") or "").strip() if topic else ""
    tema_generic = not vysv or _glosa_je_nedostatecna(vysv)

    steno_fakty = [f for f in fakty if (f.get("source") or "") == "steno"]
    if tema_generic and steno_fakty:
        t = (steno_fakty[0].get("text") or "").strip()
        if t:
            return t if t.endswith((".", "!", "?")) else f"{t}."

    if vysv and not tema_generic:
        vysv = bez_dlouhych_pomlc(vysv)
        part = re.split(r"\s*-\s*", vysv, maxsplit=1)[0].strip()
        first = re.split(r"(?<=[.!?])\s+", part, maxsplit=1)[0].strip()
        if first:
            return first if first.endswith((".", "!", "?")) else f"{first}."

    if fakty:
        t = (fakty[0].get("text") or "").strip()
        if t:
            return t if t.endswith((".", "!", "?")) else f"{t}."

    predmet = (fact.get("predmet_lidsky") or "").strip()
    if predmet:
        p = predmet[0].upper() + predmet[1:]
        return p if p.endswith((".", "!", "?")) else f"{p}."

    return lead_z_fact(fact)


def parliament_lead_z_fact(fact: dict[str, Any], topic: dict[str, Any] | None) -> str:
    """Kotva z hlasování, u maratonu přesnější než „schválili změny v …“."""
    n = int(fact.get("pocet_hlasovani") or 0)
    predmet = (fact.get("predmet_lidsky") or "bod programu").strip()
    verdikt = fact.get("verdikt", "schvaleno")
    prijato = int((topic or {}).get("pocet_prijato") or 0)
    zamitnuto = int((topic or {}).get("pocet_zamitnuto") or 0)

    if n > 3:
        if verdikt == "schvaleno" and zamitnuto > prijato and prijato > 0:
            return (
                f"Po {n} hlasováních o {predmet} většina pozměňovacích návrhů padla, "
                f"na závěr ale něco prošlo."
            )
        if verdikt == "schvaleno" and zamitnuto > prijato:
            return f"Po {n} hlasováních o {predmet} na závěr procedurálně něco prošlo."
        if verdikt == "zamiteno":
            return f"{n}× hlasovali o {predmet}, návrh neprošel."
        if verdikt == "odlozeno":
            return f"Po {n} hlasováních o {predmet} to poslanci odložili."

    return lead_z_fact(fact)


def _mean_z_dopadu(dopad: str, lead: str) -> str:
    if not dopad:
        return ""
    if lead and lead.rstrip(".") in dopad:
        rest = dopad.replace(lead.rstrip("."), "", 1).strip(" .")
        return rest or dopad
    return dopad


def _verdikt_fráze_zaver(item: DenItem, pocet_hlasovani: int) -> str:
    v = item.verdikt
    if pocet_hlasovani > 5:
        if v == "schvaleno":
            return f"po {pocet_hlasovani} hlasováních na závěr něco prošlo"
        if v == "zamiteno":
            return f"{pocet_hlasovani}× se hlasovalo a návrh neprošel"
        if v == "odlozeno":
            return "debata skončila odkladem"
    if v == "schvaleno":
        return "návrh prošel"
    if v == "zamiteno":
        return "návrh neprošel"
    if v == "odlozeno":
        return "věc se odložila"
    return "bod je v článku výše rozepsaný"


def _nadpis_kratce(nadpis: str) -> str:
    t = (nadpis or "").strip()
    if len(t) <= 55:
        return f"„{t}“"
    return f"„{t[:52]}…“"


def zaver_z_obsahu(content: DenContent, day: dict[str, Any]) -> str:
    override = (day.get("zaver") or "").strip()
    if override:
        if override.lower().startswith("poslušně"):
            return override
        return f"Poslušně hlásím, {override[0].lower()}{override[1:]}"

    items = content.items
    meta: dict[int, dict[str, Any]] = day.get("items_meta") or {}

    if not items:
        proslo = content.proslo
        zam = content.zamitnuto
        if proslo or zam:
            return (
                f"Poslušně hlásím, že dnes ve sněmovně "
                f"{proslo} {'věc' if proslo == 1 else 'věci'} prošly a {zam} "
                f"{'návrh' if zam == 1 else 'návrhů'} padlo, v tomto vydání bez detailního článku."
            )
        return "Poslušně hlásím, že dnešní vydání je prázdné, sněmovna asi jen klokotala."

    if len(items) == 1:
        it = items[0]
        ph = int((meta.get(str(it.num)) or {}).get("pocet_hlasovani") or 0)
        vf = _verdikt_fráze_zaver(it, ph)
        return (
            f"Poslušně hlásím, že dnešní vydání stojí na jednom bodu, "
            f"{_nadpis_kratce(it.nadpis)}: {vf}; zbytek najdete v textu výše."
        )

    if len(items) == 2:
        a, b = items[0], items[1]
        return (
            f"Poslušně hlásím, že dnes byly na programu dva hlavní body, "
            f"{_nadpis_kratce(a.nadpis)} a {_nadpis_kratce(b.nadpis)}; "
            f"obojí je rozepsané v článcích výše."
        )

    prvni = items[0].nadpis
    posledni = items[-1].nadpis
    return (
        f"Poslušně hlásím, že dnešní vydání shrnuje {len(items)} bodů programu "
        f"od {_nadpis_kratce(prvni)} po {_nadpis_kratce(posledni)}, detaily jsou v textech výše."
    )


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


def calendar_parts(datum_unl: str, den: str) -> tuple[str, str, str]:
    d = datetime.strptime(datum_unl, "%d.%m.%Y")
    return den.capitalize(), str(d.day), f"{_MESICE_GEN[d.month - 1]} {d.year}"


def board_stats_line(stats: dict[str, Any]) -> str:
    parts: list[str] = []
    hlas = int(stats.get("pocet_hlas") or 0)
    if hlas:
        parts.append(f"{hlas} hlasování")
    minuty = int(stats.get("minuty") or 0)
    if minuty:
        parts.append(f"{minuty} minut v sále")
    end = (stats.get("end_cas") or "").strip()
    if end:
        parts.append(f"konec ve {end}")
    return " · ".join(parts)


def split_nadpis_radky(nadpis: str, *, max_lines: int = 2) -> list[str]:
    text = (nadpis or "").strip()
    if not text:
        return [""]
    for sep in (" - ",):
        if sep in text:
            parts = [p.strip() for p in text.split(sep, 1) if p.strip()]
            if len(parts) <= max_lines:
                return parts
    words = text.split()
    if len(words) <= 4:
        return [text]
    mid = len(words) // 2
    return [" ".join(words[:mid]), " ".join(words[mid:])]


def _result_note(stats: dict[str, Any], *, state: dict) -> str:
    if stats.get("dlouha_debata"):
        return "Nejdřív se dlouho hádali o pořadu dne; zákony prošly až po dohadování."
    note = _shrnuti_radka(stats, state=state)
    if stats.get("zamitnuto", 0) > stats.get("proslo", 0):
        return note
    if stats.get("minuty", 0) >= 360:
        return "Schůze se protáhla, poslední body padly až večer."
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

    cal_den, cal_day, cal_month = calendar_parts(datum, den_cap)
    content = DenContent(
        datum=datum,
        den=den_cap,
        cal_den=cal_den,
        cal_day=cal_day,
        cal_month=cal_month,
        dnesni_ucet=_dnesni_ucet(stats, state=state),
        proslo=int(stats.get("proslo") or 0),
        zamitnuto=int(stats.get("zamitnuto") or 0),
        board_stats=board_stats_line(stats),
        result_note=_result_note(stats, state=state),
    )

    num = 0
    items_meta: dict[str, dict[str, Any]] = {}
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
        topic = topics.get(slug)
        parliament_lead = parliament_lead_z_fact(fact, topic)
        nadpis = nadpis_z_clanku(fact, topic)
        ph = int(fact.get("pocet_hlasovani") or 0)
        has_steno_lead = any((f.get("source") or "") == "steno" for f in (fact.get("fakty") or []))
        vysv = (topic.get("tema_vysvetleni") or "").strip() if topic else ""

        def _lead_fallback() -> str:
            lead = _lead_kratky(fact, topic)
            if ph > 3 and not has_steno_lead and (not vysv or glosa_generic(vysv)):
                return parliament_lead
            return lead

        use_poslusne = num == 1
        svejk_lead = lead_svejkovsky(
            fact,
            topic,
            state=state,
            use_poslusne=use_poslusne,
            fallback=_lead_fallback,
        )
        vysvetleni = mean_vysvetleni(
            fact,
            topic,
            svejk_lead,
            dopad_fallback=dopad,
            mean_from_dopad=_mean_z_dopadu,
        )
        items_meta[str(num)] = {"pocet_hlasovani": ph, "slug": slug}
        content.items.append(
            DenItem(
                num=num,
                kick=_kick_z_fact(fact),
                nadpis=nadpis,
                nadpis_radky=split_nadpis_radky(nadpis),
                lead=svejk_lead,
                mean=vysvetleni,
                dopad=dopad,
                parliament_lead=parliament_lead,
                verdikt=fact.get("verdikt", "schvaleno"),
                variant="i2" if num % 2 == 0 else "",
            )
        )

    override = (day.get("zaver") or "").strip()
    if override:
        zaver = (
            override
            if override.lower().startswith("poslušně")
            else f"Poslušně hlásím, {override[0].lower()}{override[1:]}"
        )
    else:
        zaver = _zaverecna_veta(stats, state=state)
    content.zaver = zaver
    content.zaver_key, content.zaver_body = split_zaver(zaver)
    _sanitize_den_content(content)

    return content


def _sanitize_den_content(content: DenContent) -> None:
    content.dnesni_ucet = bez_dlouhych_pomlc(content.dnesni_ucet)
    content.board_stats = bez_dlouhych_pomlc(content.board_stats)
    content.result_note = bez_dlouhych_pomlc(content.result_note)
    content.zaver = bez_dlouhych_pomlc(content.zaver)
    content.zaver_key = bez_dlouhych_pomlc(content.zaver_key)
    content.zaver_body = bez_dlouhych_pomlc(content.zaver_body)
    for item in content.items:
        item.kick = bez_dlouhych_pomlc(item.kick)
        item.nadpis = bez_dlouhych_pomlc(item.nadpis)
        item.nadpis_radky = [bez_dlouhych_pomlc(x) for x in item.nadpis_radky]
        item.lead = bez_dlouhych_pomlc(item.lead)
        item.mean = bez_dlouhych_pomlc(item.mean)
        item.dopad = bez_dlouhych_pomlc(item.dopad)
        item.parliament_lead = bez_dlouhych_pomlc(item.parliament_lead)


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
