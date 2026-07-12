"""Společný model dne pro markdown i HTML výstup."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from svejk.build.extract import skore_z_verdiktu
from svejk.build.io import iter_jsonl, read_json
from svejk.build.vote_logic import debata_vysledek_radek, spor_o_porad_schuze
from svejk.cislo_slovy import (
    krat_hlasovali,
    krat_se_hlasovalo,
    n_hlasovani,
    nahrad_cisla_v_textu,
    po_hlasovanich,
    po_hlasovanich_cap,
)
from psp.poslanci import poslanec_registry
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

_VERDIKT_STAMP = {
    "schvaleno": "Schváleno",
    "zvoleno": "Zvoleno",
    "zamiteno": "Zamítnuto",
    "odlozeno": "Odloženo",
    "debata": "Debata",
}


def _verdikt_stamp(verdikt: str) -> str:
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
    citace_href: str = ""
    citace2_text: str = ""
    citace2_autor: str = ""
    citace2_href: str = ""
    pointa: str = ""
    lead_tail: str = ""
    variant: str = ""
    has_custom_lead: bool = False
    mean_links: list[tuple[str, str]] = field(default_factory=list)
    kuriozita_links: list[tuple[str, str]] = field(default_factory=list)
    kuriozita_nav: list[tuple[str, str]] = field(default_factory=list)
    steno_nav: list[tuple[str, str]] = field(default_factory=list)
    slug: str = ""

    @property
    def stamp(self) -> str:
        return _verdikt_stamp(self.verdikt)

    @property
    def anchor_id(self) -> str:
        """HTML `id` pro deep-link na článek (`/vydani/…/#{anchor_id}`)."""
        return self.slug or f"article-{self.num}"


@dataclass
class DenContent:
    datum: str
    den: str
    cal_den: str
    cal_day: str
    cal_month: str
    dnesni_ucet: str
    nadpis_vydani: str = ""
    items: list[DenItem] = field(default_factory=list)
    proslo: int = 0
    zamitnuto: int = 0
    result_note: str = ""
    zaver: str = ""
    zaver_key: str = "Poslušně hlásím,"
    zaver_body: str = ""
    snemovni_listy: dict[str, Any] | None = None
    jazykolam: dict[str, Any] | None = None


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


def _mean_links(fact: dict[str, Any]) -> list[tuple[str, str]]:
    links: list[tuple[str, str]] = []
    for entry in fact.get("mean_links") or []:
        if not isinstance(entry, dict):
            continue
        phrase = (entry.get("phrase") or "").strip()
        page = (entry.get("page") or "").strip()
        if phrase and page:
            links.append((phrase, page))
    legacy = fact.get("mean_link") or {}
    legacy_phrase = (legacy.get("phrase") or "").strip()
    legacy_page = (legacy.get("page") or "neprosli").strip()
    if legacy_phrase and not any(p == legacy_phrase for p, _ in links):
        links.append((legacy_phrase, legacy_page))
    return links


def _kuriozita_links(fact: dict[str, Any]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for entry in fact.get("kuriozita_links") or []:
        if not isinstance(entry, dict):
            continue
        label = (entry.get("label") or "").strip()
        page = (entry.get("page") or "").strip()
        if label and page:
            out.append((label, page))
    return out


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
    month = _MESICE_GEN[d.month - 1]
    return f"{d.day}. {month} {d.year}"


def datum_day_month(datum_unl: str) -> str:
    d = datetime.strptime(datum_unl, "%d.%m.%Y")
    return f"{d.day}. {_MESICE_GEN[d.month - 1]}"


def edition_day_meta(den: str, datum_unl: str) -> str:
    """Řádek pod titulkem dne: Poslanecká sněmovna, úterý 2. července 2026."""
    d = datetime.strptime(datum_unl, "%d.%m.%Y")
    month = _MESICE_GEN[d.month - 1]
    den_label = den.strip().capitalize() if den else ""
    return f"Poslanecká sněmovna, {den_label} {d.day}. {month} {d.year}"


def calendar_parts(datum_unl: str, den: str) -> tuple[str, str, str]:
    d = datetime.strptime(datum_unl, "%d.%m.%Y")
    den_label = den.capitalize()
    month = _MESICE_GEN[d.month - 1]
    return den_label, str(d.day), month


def _kapitalizuj_prvni_pismeno(text: str) -> str:
    for i, c in enumerate(text):
        if c.isalpha():
            return text[:i] + c.upper() + text[i + 1 :]
    return text


def _kapitalizuj_segmenty(text: str, *, sep: str = " · ") -> str:
    if not (text or "").strip():
        return text
    return sep.join(_kapitalizuj_prvni_pismeno(p.strip()) for p in text.split(sep) if p.strip())


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
    debata = debata_vysledek_radek(stats).lstrip("* ").strip()
    if debata.startswith("nejdřív se dlouho hádali"):
        return "Nejdřív se dlouho hádali o pořadu dne; zákony prošly až po dohadování."
    if debata.startswith("celé odpoledne se mluvilo"):
        return "Celé odpoledne se mluvilo o jednom bodu; na konci balík změn neprošel."
    if debata.startswith("dlouhá debata"):
        return "Dlouhá debata u jednoho bodu; závěrečné hlasování až večer."
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
    link_mode: str = "file",
    base_path: str = "",
) -> DenContent:
    if state is None:
        _cache_key = (str(day_path), link_mode, base_path)
        if _cache_key in _DEN_CONTENT_CACHE:
            return _DEN_CONTENT_CACHE[_cache_key]
        state = _new_state()
    else:
        _cache_key = None
    state["poslusne_count"] = 0

    day_raw = read_json(day_path)
    day = day_raw
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

    skore_p, skore_z = skore_z_verdiktu(slugs, paths)
    if not day.get("skore_manual") and (skore_p or skore_z):
        stats["proslo"] = skore_p
        stats["zamitnuto"] = skore_z

    cal_den, cal_day, cal_month = calendar_parts(datum, den_cap)
    custom_ucet = (day.get("dnesni_ucet") or "").strip()
    custom_note = (day.get("result_note") or "").strip()
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
        dnesni_ucet=custom_ucet or _dnesni_ucet(stats, state=state),
        nadpis_vydani=(day.get("nadpis_vydani") or "").strip(),
        proslo=int(stats.get("proslo") or 0),
        zamitnuto=int(stats.get("zamitnuto") or 0),
        result_note=result_note,
        snemovni_listy=day.get("snemovni_listy") or None,
        jazykolam=day.get("jazykolam") or None,
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
        fact = fact_raw
        dopad = dopad_z_fact(fact)
        if not dopad:
            continue

        num += 1
        topic = topics.get(slug)
        custom_lead = (fact.get("lead") or "").strip()
        custom_mean = (fact.get("mean") or "").strip()
        has_custom_lead = bool(custom_lead)
        parliament_lead = parliament_lead_z_fact(fact, topic)
        nadpis = (fact.get("nadpis") or "").strip() or nadpis_z_clanku(fact, topic)
        ph = int(fact.get("pocet_hlasovani") or 0)
        has_steno_lead = any((f.get("source") or "") == "steno" for f in (fact.get("fakty") or []))
        vysv = (topic.get("tema_vysvetleni") or "").strip() if topic else ""

        def _lead_fallback() -> str:
            lead = _lead_kratky(fact, topic)
            if ph > 3 and not has_steno_lead and (not vysv or glosa_generic(vysv)):
                return parliament_lead
            return lead

        use_poslusne = num == 1
        if custom_lead:
            svejk_lead = custom_lead
        else:
            svejk_lead = lead_svejkovsky(
                fact,
                topic,
                state=state,
                use_poslusne=use_poslusne,
                fallback=_lead_fallback,
            )
        if custom_mean:
            vysvetleni = custom_mean
        else:
            vysvetleni = mean_vysvetleni(
                fact,
                topic,
                svejk_lead,
                dopad_fallback=dopad,
                mean_from_dopad=_mean_z_dopadu,
            )
        mean_links = _mean_links(fact_raw)
        kuriozita_links = _kuriozita_links(fact_raw)
        kuriozita = (fact.get("kuriozita") or "").strip() or kuriozita_z_fact(fact)
        citace_text = (fact.get("citace_text") or "").strip()
        citace_autor = (fact.get("citace_autor") or "").strip()
        citace_href = (fact.get("citace_href") or "").strip()
        citace2_text = (fact.get("citace2_text") or "").strip()
        citace2_autor = (fact.get("citace2_autor") or "").strip()
        citace2_href = (fact.get("citace2_href") or "").strip()
        pointa = (fact.get("pointa") or "").strip() if has_custom_lead else ""
        lead_tail = (fact.get("lead_tail") or "").strip()
        items_meta[str(num)] = {"pocet_hlasovani": ph, "slug": slug}
        content.items.append(
            DenItem(
                num=num,
                kick=_kick_z_fact(fact),
                nadpis=nadpis,
                nadpis_radky=split_nadpis_radky(nadpis),
                lead=svejk_lead,
                lead_tail=lead_tail,
                mean=vysvetleni,
                kuriozita=kuriozita,
                citace_text=citace_text,
                citace_autor=citace_autor,
                citace_href=citace_href,
                citace2_text=citace2_text,
                citace2_autor=citace2_autor,
                citace2_href=citace2_href,
                pointa=pointa,
                dopad=dopad,
                parliament_lead=parliament_lead,
                has_custom_lead=has_custom_lead,
                verdikt=fact.get("verdikt", "schvaleno"),
                variant="i2" if num % 2 == 0 else "",
                mean_links=mean_links,
                kuriozita_links=kuriozita_links,
                slug=slug,
            )
        )

    override = (day.get("zaver") or "").strip()
    if override:
        if override.lower().startswith("poslušně"):
            zaver = override
        else:
            zaver = f"Poslušně hlásím, {lcfirst_preserve_proper(override)}"
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
    content.zaver_key, content.zaver_body = split_zaver(zaver)
    _enrich_jazykolam_href(content, paths)
    _sanitize_den_content(content)
    from svejk.build.steno_sources import apply_steno_links_to_content

    apply_steno_links_to_content(
        content,
        paths,
        link_mode=link_mode,
        base_path=base_path,
    )
    from svejk.build.mezin_smlouvy import apply_smlouvy_page_links

    apply_smlouvy_page_links(
        content,
        paths,
        link_mode=link_mode,
        base_path=base_path,
    )
    if _cache_key is not None:
        _DEN_CONTENT_CACHE[_cache_key] = content
    return content


_ALLOWED_INLINE_TAGS = frozenset({"strong", "em", "b", "i", "br"})
_ALLOWED_BLOCK_TAGS = frozenset({"ul", "li"})
_ALLOWED_UL_CLASSES = frozenset({"listy-ul"})
_ALLOWED_SPAN_CLASSES = frozenset({"hl"})
_ALLOWED_LINK_CLASSES = frozenset({"steno-link", "mean-link"})
_OPEN_TAG_RE = re.compile(r"^<(\w+)\b([^>]*)>$", re.I)
_CLOSE_TAG_RE = re.compile(r"^</(\w+)\s*>$", re.I)


def _sanitize_href(href: str) -> str | None:
    href = (href or "").strip()
    if not href:
        return None
    lower = href.lower()
    if lower.startswith(("javascript:", "data:", "vbscript:")):
        return None
    if href.startswith("#") or href.startswith("/"):
        return href
    if lower.startswith("https://") or lower.startswith("http://"):
        return href
    return None


def _filter_allowed_html_tag(tag: str) -> str:
    close = _CLOSE_TAG_RE.match(tag)
    if close:
        name = close.group(1).lower()
        if (
            name in _ALLOWED_INLINE_TAGS
            or name == "a"
            or name in _ALLOWED_BLOCK_TAGS
            or name == "span"
        ):
            return f"</{name}>"
        return ""

    open_m = _OPEN_TAG_RE.match(tag)
    if not open_m:
        return ""

    name = open_m.group(1).lower()
    attrs = open_m.group(2)

    if name in _ALLOWED_INLINE_TAGS:
        if attrs.strip():
            return ""
        return f"<{name}>"

    if name == "li":
        if attrs.strip():
            return ""
        return "<li>"

    if name == "ul":
        class_m = re.search(r'\bclass="([^"]*)"', attrs, re.I)
        if not class_m:
            return ""
        classes = set(class_m.group(1).split())
        if not classes & _ALLOWED_UL_CLASSES:
            return ""
        return '<ul class="listy-ul">'

    if name == "span":
        class_m = re.search(r'\bclass="([^"]*)"', attrs, re.I)
        if not class_m:
            return ""
        classes = set(class_m.group(1).split())
        if not classes & _ALLOWED_SPAN_CLASSES:
            return ""
        return '<span class="hl">'

    if name == "a":
        class_m = re.search(r'\bclass="([^"]*)"', attrs, re.I)
        href_m = re.search(r'\bhref="([^"]*)"', attrs, re.I)
        if not class_m or not href_m:
            return ""
        classes = set(class_m.group(1).split())
        link_class = next((c for c in classes if c in _ALLOWED_LINK_CLASSES), None)
        if not link_class:
            return ""
        href = _sanitize_href(href_m.group(1))
        if not href:
            return ""
        safe_href = html.escape(href, quote=True)
        return f'<a class="{link_class}" href="{safe_href}">'

    return ""


def _sanitize_html_segments(text: str, plain_chunk) -> str:
    if "<" not in text:
        return plain_chunk(text)

    parts = re.split(r"(<[^>]+>)", text)
    out: list[str] = []
    for part in parts:
        if not part:
            continue
        if part.startswith("<"):
            filtered = _filter_allowed_html_tag(part)
            if filtered:
                out.append(filtered)
            continue
        out.append(plain_chunk(part))
    return "".join(out)


def _sanitize_text_export(text: str) -> str:
    if not (text or "").strip():
        return text

    from svejk.build.glossary_markup import highlight_markup

    def _plain_chunk(chunk: str) -> str:
        out = poslanec_registry().annotate(bez_dlouhych_pomlc(chunk)) if chunk.strip() else chunk
        out = nahrad_cisla_v_textu(out)
        return highlight_markup(out)

    def _steno_link_inner(inner: str) -> str:
        out = bez_dlouhych_pomlc(inner)
        out = nahrad_cisla_v_textu(out)
        return highlight_markup(out)

    if "<" not in text:
        return _plain_chunk(text)

    steno_link_re = re.compile(
        r'(<a\b[^>]*\bclass="[^"]*steno-link[^"]*"[^>]*>)(.*?)(</a>)',
        re.I | re.S,
    )
    placeholders: dict[str, str] = {}

    def _protect_link(match: re.Match[str]) -> str:
        opening = _filter_allowed_html_tag(match.group(1))
        if not opening:
            return _steno_link_inner(match.group(2))
        key = f"[[STENOLINK:{len(placeholders)}]]"
        placeholders[key] = (
            f"{opening}{_steno_link_inner(match.group(2))}</a>"
        )
        return key

    protected = steno_link_re.sub(_protect_link, text)
    result = _sanitize_html_segments(protected, _plain_chunk)
    for key, val in placeholders.items():
        result = result.replace(key, val)
    return result


def _sanitize_citace_export(text: str) -> str:
    """Citace ze stenoprotokolu — bez přepisu číslic do slov."""
    if not (text or "").strip():
        return text
    from svejk.build.glossary_markup import highlight_markup

    return highlight_markup(bez_dlouhych_pomlc(text))


def _sanitize_mean_export(text: str) -> str:
    """Text bez doplňování stran u jmen poslanců (mean, závěr dne)."""
    if not (text or "").strip():
        return text

    from svejk.build.glossary_markup import highlight_markup

    def _plain_chunk(chunk: str) -> str:
        out = bez_dlouhych_pomlc(chunk)
        out = nahrad_cisla_v_textu(out)
        return highlight_markup(out)

    return _sanitize_html_segments(text, _plain_chunk)


def _sanitize_nadpis_export(text: str) -> str:
    """Titulky bez doplnění stran z registru poslanců; první písmeno velké."""
    t = (text or "").strip()
    if not t:
        return text
    return _kapitalizuj_prvni_pismeno(bez_dlouhych_pomlc(t))


def _sanitize_vysledek_export(text: str) -> str:
    """Výsledek dne: stejná sanitizace jako běžný text včetně čísel slovně."""
    text = bez_dlouhych_pomlc(text)
    if not text.strip():
        return text
    return poslanec_registry().annotate(nahrad_cisla_v_textu(text))


def _resolve_jazykolam_steno_id(paths: SchuzePaths, j: dict[str, Any]) -> str:
    steno_id = (j.get("steno_id") or "").strip()
    if steno_id:
        return steno_id
    poradi = j.get("poradi")
    if poradi is None:
        return ""
    from svejk.build.steno_sources import _load_steno_index

    for sid, rec in _load_steno_index(paths).items():
        if rec.get("poradi") == poradi:
            return sid
    return ""


def _enrich_jazykolam_href(content: DenContent, paths: SchuzePaths) -> None:
    j = content.jazykolam
    if not j:
        return
    from svejk.build.steno_sources import resolve_psp_url_for_steno, steno_anchor

    steno_id = _resolve_jazykolam_steno_id(paths, j)
    if steno_id:
        j["steno_id"] = steno_id
    text = (j.get("text") or "").strip()
    href = resolve_psp_url_for_steno(paths, steno_id, text) if steno_id and text else ""
    if not href:
        href = (j.get("url") or "").strip()
    if href:
        j["href"] = href
    if steno_id:
        j["steno_anchor"] = steno_anchor(steno_id)


def _sanitize_den_content(content: DenContent) -> None:
    content.result_note = _kapitalizuj_prvni_pismeno(
        _sanitize_text_export(content.result_note)
    )
    content.dnesni_ucet = _kapitalizuj_prvni_pismeno(
        _sanitize_text_export(content.dnesni_ucet)
    )
    content.zaver = _sanitize_mean_export(content.zaver)
    content.zaver_key = _sanitize_mean_export(content.zaver_key)
    content.zaver_body = _sanitize_mean_export(content.zaver_body)
    content.nadpis_vydani = _sanitize_nadpis_export(content.nadpis_vydani)
    for item in content.items:
        item.kick = _sanitize_text_export(item.kick)
        item.nadpis = _sanitize_nadpis_export(item.nadpis)
        item.nadpis_radky = [
            _sanitize_nadpis_export(x) for x in item.nadpis_radky
        ]
        item.lead = _sanitize_text_export(item.lead)
        item.lead_tail = _sanitize_text_export(item.lead_tail)
        item.mean = _sanitize_text_export(item.mean)
        item.kuriozita = _sanitize_text_export(item.kuriozita)
        item.citace_text = _sanitize_citace_export(item.citace_text)
        item.citace_autor = _sanitize_text_export(item.citace_autor)
        item.citace2_text = _sanitize_citace_export(item.citace2_text)
        item.citace2_autor = _sanitize_text_export(item.citace2_autor)
        item.pointa = _sanitize_text_export(item.pointa)
        item.dopad = _sanitize_text_export(item.dopad)
        item.parliament_lead = _sanitize_text_export(item.parliament_lead)


def vysledek_radky(content: DenContent, paths: SchuzePaths, day_path: Path) -> list[str]:
    day = read_json(day_path)
    custom = day.get("vysledek")
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
    if "spor_o_porad" not in stats:
        from svejk.jednaci_den import vote_belongs_to_jednaci_den

        day_votes = [
            v
            for v in iter_jsonl(paths.votes_jsonl)
            if vote_belongs_to_jednaci_den(v, content.datum)
        ]
        stats["spor_o_porad"] = spor_o_porad_schuze(day_votes)
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
