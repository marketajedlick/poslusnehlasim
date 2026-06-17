"""Společný model dne pro markdown i HTML výstup."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from svejk.build.extract import skore_z_verdiktu
from svejk.build.io import read_json
from svejk.cislo_slovy import (
    krat_hlasovali,
    krat_se_hlasovalo,
    n_hlasovani,
    nahrad_cisla_v_textu,
    po_hlasovanich,
    po_hlasovanich_cap,
)
from svejk.poslanec_strany import dopln_strany_poslancu
from svejk.text_norm import bez_dlouhych_pomlc, lcfirst_preserve_proper
from svejk.build.witty import (
    glosa_generic,
    kuriozita_z_fact,
    lead_svejkovsky,
    mean_vysvetleni,
    nadpis_z_clanku,
    zaver_glosa_dne,
)
from svejk.listy import (
    _dnesni_ucet,
    _format_koho_veta,
    _glosa_je_nedostatecna,
    _shrnuti_radka,
    _vysledek_dne,
)
from svejk.noviny import _new_state
from svejk.paths import SchuzePaths
from svejk.build.facts_i18n import (
    localized_day,
    localized_fact,
    localized_kuriozita_links,
    localized_mean_links,
    pick_field,
    pick_list,
)
from svejk.locale import normalize_locale
from svejk.timeline import BlokDne, DenSchuze, den_v_tydnu

_KICK_RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("zkumav", "zdrav", "nemocnic", "laborator", "diagnost"), "Zdravotnictví"),
    (("sociální podpo", "dávk", "přídav", "příspěvek na bydlení"), "Dávky"),
    (("živnost", "pojistn", "odvod", "soc. zab"), "Živnostníci"),
    (("penzij", "důchod", "spoření"), "Penze"),
    (("stavebn", "developersk", "územní"), "Stavby"),
    (("investič", "finan", "bank"), "Finance"),
    (("rostlin", "postřik", "pesticid", "hnojen"), "Zemědělství"),
    (("výbor", "orgán", "volba", "personál", "komis"), "Personálka"),
    (("energ", "elektr", "plyn"), "Energetika"),
    (("doprav", "silnic", "železn"), "Doprava"),
)

_VERDIKT_STAMP_EN = {
    "schvaleno": "PASSED",
    "zvoleno": "PASSED",
    "zamiteno": "FAILED",
    "odlozeno": "FAILED",
    "debata": "DEBATE",
}

_DEN_CS_TO_EN = {
    "pondělí": "Monday",
    "úterý": "Tuesday",
    "středa": "Wednesday",
    "čtvrtek": "Thursday",
    "pátek": "Friday",
    "sobota": "Saturday",
    "neděle": "Sunday",
}

_MESICE_GEN_EN = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)

_KICK_RULES_EN: tuple[tuple[tuple[str, ...], str], ...] = (
    (("zkumav", "zdrav", "nemocnic", "laborator", "diagnost"), "Healthcare"),
    (("sociální podpo", "dávk", "přídav", "housing"), "Benefits"),
    (("živnost", "pojistn", "odvod", "soc. zab"), "Self-employed"),
    (("penzij", "důchod", "spoření", "pension"), "Pensions"),
    (("stavebn", "developersk", "územní", "building"), "Construction"),
    (("investič", "finan", "bank"), "Finance"),
    (("rostlin", "postřik", "pesticid", "hnojen"), "Agriculture"),
    (("výbor", "orgán", "volba", "personál", "komis"), "Personnel"),
    (("energ", "elektr", "plyn"), "Energy"),
    (("doprav", "silnic", "železn"), "Transport"),
)

_VERDIKT_STAMP = {
    "schvaleno": "Schváleno",
    "zvoleno": "Zvoleno",
    "zamiteno": "Zamítnuto",
    "odlozeno": "Odloženo",
    "debata": "Debata",
}


def _verdikt_stamp(verdikt: str, locale: str = "cs") -> str:
    loc = normalize_locale(locale)
    if loc == "en":
        return _VERDIKT_STAMP_EN.get(verdikt, "PASSED")
    return _VERDIKT_STAMP.get(verdikt, "Schváleno")

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
    kuriozita: str = ""
    citace_text: str = ""
    citace_autor: str = ""
    variant: str = ""
    has_custom_lead: bool = False
    mean_links: list[tuple[str, str]] = field(default_factory=list)
    kuriozita_links: list[tuple[str, str]] = field(default_factory=list)
    kuriozita_nav: list[tuple[str, str]] = field(default_factory=list)
    steno_nav: list[tuple[str, str]] = field(default_factory=list)
    slug: str = ""
    locale: str = "cs"

    @property
    def stamp(self) -> str:
        return _verdikt_stamp(self.verdikt, self.locale)


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
    board_note_lines: list[str] = field(default_factory=list)


def lead_z_fact(fact: dict[str, Any]) -> str:
    predmet = (fact.get("predmet_lidsky") or "").strip()
    verdikt = fact.get("verdikt", "schvaleno")
    n = fact.get("pocet_hlasovani", 0)

    if verdikt == "schvaleno":
        lead = f"poslanci schválili změny v {predmet}." if predmet else "poslanci schválili změnu."
    elif verdikt == "zvoleno":
        lead = f"poslanci zvolili {predmet}." if predmet else "poslanci volbu dokončili."
    elif verdikt == "zamiteno":
        lead = f"poslanci zamítli změny v {predmet}." if predmet else "poslanci změnu zamítli."
    elif verdikt == "odlozeno":
        lead = f"poslanci odložili změny v {predmet}." if predmet else "poslanci změnu odložili."
    elif verdikt == "debata":
        lead = f"poslanci debatovali o {predmet}." if predmet else "poslanci debatovali bez hlasování."
    else:
        lead = f"poslanci řešili {predmet or 'bod programu'}."

    if n > 1 and verdikt == "schvaleno":
        lead = f"{po_hlasovanich_cap(n)} {lead[0].lower()}{lead[1:]}"
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


def _kick_z_fact(fact: dict[str, Any], locale: str = "cs") -> str:
    if (fact.get("_kick_en") or "").strip():
        return fact["_kick_en"].strip()
    rules = _KICK_RULES_EN if normalize_locale(locale) == "en" else _KICK_RULES
    blob = " ".join(
        [
            fact.get("nazev") or "",
            fact.get("nadpis") or "",
            fact.get("predmet_lidsky") or "",
        ]
    ).lower()
    for keys, label in rules:
        if any(k in blob for k in keys):
            return label
    nadpis = (fact.get("nadpis") or "").strip()
    if nadpis:
        first = re.split(r"[\s\-]", nadpis, maxsplit=1)[0]
        if len(first) >= 4:
            return first
    return "The Chamber of Deputies" if normalize_locale(locale) == "en" else "Sněmovna"


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
                f"{po_hlasovanich_cap(n)} o {predmet} většina pozměňovacích návrhů padla, "
                f"na závěr ale něco prošlo."
            )
        if verdikt == "schvaleno" and zamitnuto > prijato:
            return f"{po_hlasovanich_cap(n)} o {predmet} na závěr procedurálně něco prošlo."
        if verdikt == "zamiteno":
            return f"{krat_hlasovali(n)} o {predmet}, návrh neprošel."
        if verdikt == "odlozeno":
            return f"{po_hlasovanich_cap(n)} o {predmet} to poslanci odložili."

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
            return f"{po_hlasovanich(pocet_hlasovani)} na závěr něco prošlo"
        if v == "zamiteno":
            return f"{krat_se_hlasovalo(pocet_hlasovani)} a návrh neprošel"
        if v == "odlozeno":
            return "debata skončila odkladem"
    if v == "schvaleno":
        return "návrh prošel"
    if v == "zvoleno":
        return "volba dopadla"
    if v == "zamiteno":
        return "návrh neprošel"
    if v == "odlozeno":
        return "věc se odložila"
    if v == "debata":
        return "bez hlasování o zákonu"
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
        return f"Poslušně hlásím, {lcfirst_preserve_proper(override)}"

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


def split_zaver(text: str, *, locale: str = "cs") -> tuple[str, str]:
    m = re.match(
        r"^(Poslušně hlásím,?|I (?:hereby|humbly) report,?)\s*(.*)$",
        text,
        re.I,
    )
    if not m:
        return "", text
    body = m.group(2).strip()
    if body and not body[0].isupper():
        body = body[0].lower() + body[1:]
    key = "Poslušně hlásím," if normalize_locale(locale) == "en" else m.group(1)
    return key, body


def datum_design(datum_unl: str, den: str, *, locale: str = "cs") -> str:
    d = datetime.strptime(datum_unl, "%d.%m.%Y")
    loc = normalize_locale(locale)
    den_label = _DEN_CS_TO_EN.get(den.lower(), den).capitalize() if loc == "en" else den.capitalize()
    return f"{den_label} {d.day:02d} / {d.month:02d} / {d.year}"


def calendar_parts(datum_unl: str, den: str, *, locale: str = "cs") -> tuple[str, str, str]:
    d = datetime.strptime(datum_unl, "%d.%m.%Y")
    loc = normalize_locale(locale)
    den_label = _DEN_CS_TO_EN.get(den.lower(), den).capitalize() if loc == "en" else den.capitalize()
    month = _MESICE_GEN_EN[d.month - 1] if loc == "en" else _MESICE_GEN[d.month - 1]
    return den_label, str(d.day), f"{month} {d.year}"


def _kapitalizuj_prvni_pismeno(text: str) -> str:
    for i, c in enumerate(text):
        if c.isalpha():
            return text[:i] + c.upper() + text[i + 1 :]
    return text


def _kapitalizuj_segmenty(text: str, *, sep: str = " · ") -> str:
    if not (text or "").strip():
        return text
    return sep.join(_kapitalizuj_prvni_pismeno(p.strip()) for p in text.split(sep) if p.strip())


def board_stats_line(stats: dict[str, Any]) -> str:
    parts: list[str] = []
    hlas = int(stats.get("pocet_hlas") or 0)
    if hlas:
        parts.append(n_hlasovani(hlas))
    minuty = int(stats.get("minuty") or 0)
    if minuty:
        parts.append(f"{minuty} minut v sále")
    end = (stats.get("end_cas") or "").strip()
    if end:
        parts.append(f"konec ve {end}")
    return _kapitalizuj_segmenty(" · ".join(parts))


def split_nadpis_radky(nadpis: str, *, max_lines: int = 2) -> list[str]:
    text = (nadpis or "").strip()
    if not text:
        return [""]
    if "\n" in text:
        parts = [p.strip() for p in text.splitlines() if p.strip()]
        if parts:
            return parts[:max_lines]
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


_DEN_CONTENT_CACHE: dict[tuple, "DenContent"] = {}


def clear_den_content_cache() -> None:
    _DEN_CONTENT_CACHE.clear()


def build_den_content(
    day_path: Path,
    paths: SchuzePaths,
    *,
    state: dict | None = None,
    locale: str = "cs",
    link_mode: str = "file",
    base_path: str = "",
) -> DenContent:
    loc = normalize_locale(locale)
    if state is None:
        _cache_key = (str(day_path), loc, link_mode, base_path)
        if _cache_key in _DEN_CONTENT_CACHE:
            return _DEN_CONTENT_CACHE[_cache_key]
        state = _new_state()
    else:
        _cache_key = None
    state["poslusne_count"] = 0

    day_raw = read_json(day_path)
    day = localized_day(day_raw, loc)
    datum = day["datum"]
    den_cap = day.get("den") or den_v_tydnu(datum)
    if loc == "en":
        den_cap = _DEN_CS_TO_EN.get(den_cap.lower(), den_cap)
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

    skore_p, skore_z = skore_z_verdiktu(slugs, paths)
    if skore_p or skore_z:
        stats["proslo"] = skore_p
        stats["zamitnuto"] = skore_z

    cal_den, cal_day, cal_month = calendar_parts(datum, den_cap, locale=loc)
    custom_ucet = pick_field(day, "dnesni_ucet", loc) or (day.get("dnesni_ucet") or "").strip()
    custom_note = pick_field(day, "result_note", loc) or (day.get("result_note") or "").strip()
    if custom_note:
        result_note = custom_note
    elif custom_ucet:
        result_note = ""
    else:
        result_note = _result_note(stats, state=state)
    content = DenContent(
        datum=datum,
        den=den_cap,
        cal_den=cal_den,
        cal_day=cal_day,
        cal_month=cal_month,
        dnesni_ucet=custom_ucet or (_dnesni_ucet(stats, state=state) if loc == "cs" else custom_ucet),
        proslo=int(stats.get("proslo") or 0),
        zamitnuto=int(stats.get("zamitnuto") or 0),
        board_stats="",
        result_note=result_note,
    )

    num = 0
    items_meta: dict[str, dict[str, Any]] = {}
    for slug in slugs:
        fp = paths.facts_by_topic / f"{slug}.json"
        if not fp.is_file():
            continue
        fact_raw = read_json(fp)
        if not fact_raw.get("publikovat"):
            continue
        fact = localized_fact(fact_raw, loc)
        dopad = dopad_z_fact(fact)
        if not dopad:
            continue

        num += 1
        topic = topics.get(slug)
        en_lead = pick_field(fact_raw, "lead", loc)
        en_mean = pick_field(fact_raw, "mean", loc)
        has_custom_lead = bool(en_lead or (fact.get("lead") or "").strip())
        parliament_lead = parliament_lead_z_fact(fact, topic)
        nadpis = pick_field(fact_raw, "nadpis", loc) or nadpis_z_clanku(fact, topic)
        ph = int(fact.get("pocet_hlasovani") or 0)
        has_steno_lead = any((f.get("source") or "") == "steno" for f in (fact.get("fakty") or []))
        vysv = (topic.get("tema_vysvetleni") or "").strip() if topic else ""

        def _lead_fallback() -> str:
            lead = _lead_kratky(fact, topic)
            if ph > 3 and not has_steno_lead and (not vysv or glosa_generic(vysv)):
                return parliament_lead
            return lead

        use_poslusne = num == 1 and loc == "cs"
        if en_lead:
            svejk_lead = en_lead
        else:
            svejk_lead = lead_svejkovsky(
                fact,
                topic,
                state=state,
                use_poslusne=use_poslusne,
                fallback=_lead_fallback,
            )
        if en_mean:
            vysvetleni = en_mean
        else:
            vysvetleni = mean_vysvetleni(
                fact,
                topic,
                svejk_lead,
                dopad_fallback=dopad,
                mean_from_dopad=_mean_z_dopadu,
            )
        mean_links = localized_mean_links(fact_raw, loc)
        kuriozita_links = localized_kuriozita_links(fact_raw, loc)
        kuriozita = pick_field(fact_raw, "kuriozita", loc) or kuriozita_z_fact(fact)
        citace_text = pick_field(fact_raw, "citace_text", loc) or (fact.get("citace_text") or "").strip()
        citace_autor = pick_field(fact_raw, "citace_autor", loc) or (fact.get("citace_autor") or "").strip()
        items_meta[str(num)] = {"pocet_hlasovani": ph, "slug": slug}
        content.items.append(
            DenItem(
                num=num,
                kick=_kick_z_fact(fact, loc),
                nadpis=nadpis,
                nadpis_radky=split_nadpis_radky(nadpis),
                lead=svejk_lead,
                mean=vysvetleni,
                kuriozita=kuriozita,
                citace_text=citace_text,
                citace_autor=citace_autor,
                dopad=dopad,
                parliament_lead=parliament_lead,
                has_custom_lead=has_custom_lead,
                verdikt=fact.get("verdikt", "schvaleno"),
                variant="i2" if num % 2 == 0 else "",
                mean_links=mean_links,
                kuriozita_links=kuriozita_links,
                locale=loc,
                slug=slug,
            )
        )

    override = pick_field(day, "zaver", loc) or (day.get("zaver") or "").strip()
    if override:
        if loc == "en":
            body = override
            if body.lower().startswith("že "):
                body = body[3:].strip()
            elif body.lower().startswith("that "):
                body = body[5:].strip()
            zaver = (
                override
                if override.lower().startswith("poslušně")
                else f"Poslušně hlásím, že {lcfirst_preserve_proper(body)}"
            )
        elif override.lower().startswith("poslušně"):
            zaver = override
        else:
            zaver = f"Poslušně hlásím, {lcfirst_preserve_proper(override)}"
    elif loc == "en":
        zaver = zaver_z_obsahu(content, day)
    else:
        zaver = zaver_glosa_dne(
            content.items,
            datum=content.datum,
            proslo=content.proslo,
            zamitnuto=content.zamitnuto,
            stats=stats,
            state=state,
        )
    content.zaver = zaver
    content.zaver_key, content.zaver_body = split_zaver(zaver, locale=loc)
    from svejk.build.steno_sources import apply_steno_links_to_content

    apply_steno_links_to_content(
        content,
        paths,
        link_mode=link_mode,
        base_path=base_path,
        locale=loc,
    )
    _sanitize_den_content(content, locale=loc)

    if _cache_key is not None:
        _DEN_CONTENT_CACHE[_cache_key] = content
    return content


def _sanitize_text_export(text: str, *, locale: str = "cs") -> str:
    if not (text or "").strip():
        return text
    loc = normalize_locale(locale)

    def _plain_chunk(chunk: str) -> str:
        out = dopln_strany_poslancu(bez_dlouhych_pomlc(chunk))
        if loc == "cs":
            out = nahrad_cisla_v_textu(out)
        return out

    def _steno_link_inner(inner: str) -> str:
        out = bez_dlouhych_pomlc(inner)
        if loc == "cs":
            out = nahrad_cisla_v_textu(out)
        return out

    if "<" not in text:
        return _plain_chunk(text)

    steno_link_re = re.compile(
        r'(<a\b[^>]*\bclass="[^"]*steno-link[^"]*"[^>]*>)(.*?)(</a>)',
        re.I | re.S,
    )
    placeholders: dict[str, str] = {}

    def _protect_link(match: re.Match[str]) -> str:
        key = f"[[STENOLINK:{len(placeholders)}]]"
        placeholders[key] = (
            f"{match.group(1)}{_steno_link_inner(match.group(2))}{match.group(3)}"
        )
        return key

    protected = steno_link_re.sub(_protect_link, text)
    parts = re.split(r"(<[^>]+>)", protected)
    out: list[str] = []
    for part in parts:
        if not part:
            continue
        if part.startswith("<"):
            out.append(part)
            continue
        out.append(_plain_chunk(part))
    result = "".join(out)
    for key, val in placeholders.items():
        result = result.replace(key, val)
    return result


def _sanitize_mean_export(text: str, *, locale: str = "cs") -> str:
    """Text bez doplňování stran u jmen poslanců (mean, závěr dne)."""
    if not (text or "").strip():
        return text
    if "<" not in text:
        out = bez_dlouhych_pomlc(text)
        if normalize_locale(locale) == "cs":
            out = nahrad_cisla_v_textu(out)
        return out
    parts = re.split(r"(<[^>]+>)", text)
    out: list[str] = []
    for part in parts:
        if not part:
            continue
        if part.startswith("<"):
            out.append(part)
            continue
        chunk = bez_dlouhych_pomlc(part)
        if normalize_locale(locale) == "cs":
            chunk = nahrad_cisla_v_textu(chunk)
        out.append(chunk)
    return "".join(out)


def _sanitize_vysledek_export(text: str) -> str:
    """Výsledek dne: čísla ponechat (stav zápasu), zbytek stejně jako v textu."""
    return dopln_strany_poslancu(bez_dlouhych_pomlc(text))


def _sanitize_den_content(content: DenContent, *, locale: str = "cs") -> None:
    loc = normalize_locale(locale)
    content.board_stats = _sanitize_text_export(content.board_stats, locale=loc)
    content.result_note = _kapitalizuj_prvni_pismeno(
        _sanitize_text_export(content.result_note, locale=loc)
    )
    content.dnesni_ucet = _kapitalizuj_prvni_pismeno(
        _sanitize_text_export(content.dnesni_ucet, locale=loc)
    )
    board_raw = (content.dnesni_ucet or content.result_note or "").strip()
    content.board_note_lines = [
        ln.strip() for ln in board_raw.splitlines() if ln.strip()
    ]
    content.zaver = _sanitize_mean_export(content.zaver, locale=loc)
    content.zaver_key = _sanitize_mean_export(content.zaver_key, locale=loc)
    content.zaver_body = _sanitize_mean_export(content.zaver_body, locale=loc)
    for item in content.items:
        item.kick = _sanitize_text_export(item.kick, locale=loc)
        item.nadpis = _sanitize_text_export(item.nadpis, locale=loc)
        item.nadpis_radky = [
            _sanitize_text_export(x, locale=loc) for x in item.nadpis_radky
        ]
        item.lead = _sanitize_text_export(item.lead, locale=loc)
        item.mean = _sanitize_text_export(item.mean, locale=loc)
        item.kuriozita = _sanitize_text_export(item.kuriozita, locale=loc)
        item.citace_text = _sanitize_text_export(item.citace_text, locale=loc)
        item.citace_autor = _sanitize_text_export(item.citace_autor, locale=loc)
        item.dopad = _sanitize_text_export(item.dopad, locale=loc)
        item.parliament_lead = _sanitize_text_export(item.parliament_lead, locale=loc)

def vysledek_radky(content: DenContent, paths: SchuzePaths, day_path: Path, *, locale: str = "cs") -> list[str]:
    day_raw = read_json(day_path)
    day = localized_day(day_raw, locale)
    custom = pick_list(day, "vysledek", locale) or day.get("vysledek")
    if custom:
        return [str(r) for r in custom]
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
