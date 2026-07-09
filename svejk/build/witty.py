"""Švejkovský lead + pointa pod nadpisem; věcné vysvětlení v „Co to znamená pro vás“."""

from __future__ import annotations

import re
from typing import Any, Callable

from svejk.listy import (
    _co_to_znamena,
    _lead_veta,
    _nadpis_bodu,
    _pointa_jednou,
    _prekryvaji,
)
from svejk.mix import _hash_seed
from svejk.obcansky import GENERIC_GLOSA_MARKERS
from svejk.text_norm import bez_dlouhych_pomlc
from svejk.timeline import BlokDne

_VYSVETLENI_MAX_LEN = 280

_GENERIC_VYSV = (
    "technická nebo procedurální",
    "dopad na občana závisí",
    "hlasovalo se, jestli jsou odpovědi ministrů",
)

_WITTY_MARKERS = (
    "netankuje",
    "715",
    "míň důchod",
    "zaměstnanec?",
    "to se vás netýká",
    "už je jiná kapitola",
    "spíš věc",
    "spíš nemocnice",
)


def blok_z_fact_topic(fact: dict[str, Any], topic: dict[str, Any] | None) -> BlokDne:
    t = topic or {}
    return BlokDne(
        cas_od="12:00",
        cas_do="",
        typ="law",
        svejk=bez_dlouhych_pomlc((t.get("tema_svejk") or "").strip()),
        vysvetleni=bez_dlouhych_pomlc((t.get("tema_vysvetleni") or "").strip()),
        nazev=(fact.get("nazev") or "").strip(),
        pocet_hlasovani=int(fact.get("pocet_hlasovani") or 0),
        pocet_prijato=int(t.get("pocet_prijato") or 0),
        pocet_zamitnuto=int(t.get("pocet_zamitnuto") or 0),
        proslo=bool(fact.get("proslo", True)),
    )


def glosa_generic(vysv: str) -> bool:
    if not vysv:
        return True
    low = vysv.lower()
    return any(g in low for g in GENERIC_GLOSA_MARKERS + _GENERIC_VYSV)


def vysv_je_witty(vysv: str) -> bool:
    if not (vysv or "").strip():
        return False
    low = vysv.lower()
    if any(g in low for g in _GENERIC_VYSV):
        return False
    if any(m in low for m in _WITTY_MARKERS):
        return True
    if ", " in vysv and len(vysv.split(", ", 1)[-1]) < 120:
        return True
    return False


def _strip_poslusne_prefix(text: str) -> str:
    t = (text or "").strip()
    while True:
        m = re.match(r"^poslušně\s+hlásím,?\s*že\s*", t, re.I)
        if not m:
            break
        t = t[m.end() :].strip()
    return t


def _lead_jednou_poslusne(lead: str, *, use_poslusne: bool) -> str:
    t = (lead or "").strip()
    if not t:
        return t
    inner = _strip_poslusne_prefix(t)
    if not inner:
        return t
    if use_poslusne:
        return f"Poslušně hlásím, že {inner[0].lower()}{inner[1:]}"
    return inner[0].upper() + inner[1:]


def _prvni_veta(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return ""
    t = bez_dlouhych_pomlc(t)
    part = re.split(r"\s*-\s*", t, maxsplit=1)[0].strip()
    v = re.split(r"(?<=[.!?])\s+", part, maxsplit=1)[0].strip()
    if v and not v.endswith((".", "!", "?")):
        v += "."
    return v


def _zkrat(text: str, *, max_len: int = _VYSVETLENI_MAX_LEN) -> str:
    t = (text or "").strip()
    if not t or len(t) <= max_len:
        return t
    vety = re.split(r"(?<=[.!?])\s+", t)
    out: list[str] = []
    for v in vety:
        cand = " ".join(out + [v]).strip()
        if len(cand) > max_len and out:
            break
        out.append(v)
    if out:
        return " ".join(out)
    return t[: max_len - 1].rstrip() + "…"


def _pointa_z_vysvetleni(vysv: str, glosa: str) -> str:
    if not vysv_je_witty(vysv):
        return ""

    low = vysv.lower()
    if "netankuje" in low:
        return "Vás doma to netankuje, to je spíš věc pro sestry."

    if "715" in vysv and "míň důchod" in low:
        return "Míň odvodů, míň důchod, to už je jiná kapitola."

    vysv = bez_dlouhych_pomlc(vysv)
    vety = re.split(r"(?<=[.!?])\s+", vysv.strip())
    tail = [v for v in vety[1:] if v.strip()]
    skip = ("platí od ledna", "přeplatek vrátí", "zaměstnanec?")
    for v in tail:
        if any(s in v.lower() for s in skip):
            continue
        if any(m in v.lower() for m in _WITTY_MARKERS + ("spíš", "jiná kapitola")):
            t = v if v.endswith((".", "!", "?")) else f"{v}."
            if glosa and not _prekryvaji(t, glosa, prag=0.45):
                return t
    if ", " in vysv:
        right = vysv.split(", ", 1)[1].strip()
        if right and any(m in right.lower() for m in _WITTY_MARKERS + ("spíš",)):
            if "netankuje" in right.lower():
                return "Vás doma to netankuje, to je spíš věc pro sestry."
            t = right if right.endswith((".", "!", "?")) else f"{right}."
            if glosa and not _prekryvaji(t, glosa, prag=0.45):
                return t
    return ""


def rozdel_kuriozitu(text: str) -> tuple[str, str]:
    """Vrátí (kuriozita, zbytek) když text obsahuje „Kuriozita dne:“."""
    text = text.strip()
    if not text:
        return "", ""
    m = re.search(r"Kuriozita dne:\s*", text, re.I)
    if not m:
        return "", text
    start = m.start()
    tail = text[m.end() :]
    dot = re.search(r"\.\s+", tail)
    if dot:
        kuriozita = text[start : m.end() + dot.start() + 1].strip()
        pred = text[:start].strip().rstrip(".")
        po = tail[dot.end() :].strip()
        zbytek = " ".join(chunk for chunk in (pred, po) if chunk).strip()
        return kuriozita, zbytek
    kuriozita = text[start:].strip()
    zbytek = text[:start].strip().rstrip(".")
    return kuriozita, zbytek


_KURIOZITA_PREFIX_START = re.compile(r"^(Kuriozita dne:)\s*", re.I)


def rozdel_kuriozitu_label(text: str) -> tuple[str, str]:
    """Vrátí (label, tělo) když text začíná „Kuriozita dne:“."""
    text = (text or "").strip()
    m = _KURIOZITA_PREFIX_START.match(text)
    if m:
        return m.group(1), text[m.end() :].strip()
    return "", text


def kuriozita_z_fact(fact: dict[str, Any]) -> str:
    explicit = (fact.get("kuriozita") or "").strip()
    if explicit:
        return explicit
    for key in ("pointa", "lead"):
        kuriozita, _ = rozdel_kuriozitu((fact.get(key) or "").strip())
        if kuriozita:
            return kuriozita
    return ""


def _pointa_pod_nadpis(
    fact: dict[str, Any],
    topic: dict[str, Any] | None,
    glosa: str,
    *,
    state: dict,
) -> str:
    pointa = (fact.get("pointa") or "").strip()
    if pointa:
        _, clean = rozdel_kuriozitu(pointa)
        return clean

    vysv = (topic or {}).get("tema_vysvetleni") or ""
    p = _pointa_z_vysvetleni(vysv, glosa)
    if p:
        return p

    blok = blok_z_fact_topic(fact, topic)
    return (_pointa_jednou(blok, glosa, "", state=state) or "").strip()


def _glosa_svejkova(
    fact: dict[str, Any],
    topic: dict[str, Any] | None,
    *,
    state: dict,
    use_poslusne: bool,
    fallback: Callable[[], str],
) -> str:
    if (fact.get("lead") or "").strip():
        lead = fact["lead"].strip()
        if use_poslusne and re.search(r"poslušně\s+hlásím", lead, re.I):
            if state.get("poslusne_count", 0) < 1:
                state["poslusne_count"] = state.get("poslusne_count", 0) + 1
            return _lead_jednou_poslusne(lead, use_poslusne=True)
        return lead

    blok = blok_z_fact_topic(fact, topic)
    vysv = (topic or {}).get("tema_vysvetleni") or ""
    listy_lead = _lead_veta(blok, state=state, use_poslusne=use_poslusne)
    if listy_lead:
        if use_poslusne and state.get("poslusne_count", 0) < 1:
            state["poslusne_count"] = state.get("poslusne_count", 0) + 1
            return _lead_jednou_poslusne(listy_lead, use_poslusne=True)
        return listy_lead.strip()

    if vysv_je_witty(vysv):
        first = _prvni_veta(vysv)
        if first:
            if use_poslusne and state.get("poslusne_count", 0) < 1:
                state["poslusne_count"] = state.get("poslusne_count", 0) + 1
                return _lead_jednou_poslusne(first, use_poslusne=True)
            return first

    return fallback()


def lead_svejkovsky(
    fact: dict[str, Any],
    topic: dict[str, Any] | None,
    *,
    state: dict,
    use_poslusne: bool,
    fallback: Callable[[], str],
) -> str:
    """Pod nadpisem: švejkovská glosa a případná pointa."""
    glosa = _glosa_svejkova(
        fact, topic, state=state, use_poslusne=use_poslusne, fallback=fallback
    )
    if not glosa:
        return ""

    pointa = _pointa_pod_nadpis(fact, topic, glosa, state=state)
    if not pointa or _prekryvaji(pointa, glosa, prag=0.5):
        return glosa
    return f"{glosa.rstrip()} {pointa}"


def _faktualni_z_vysvetleni(vysv: str, glosa: str) -> str:
    if not vysv or glosa_generic(vysv):
        return ""
    vysv = bez_dlouhych_pomlc(vysv)
    first = _prvni_veta(vysv)
    if not first:
        return ""
    if glosa and _prekryvaji(first, glosa, prag=0.55):
        return ""
    if vysv_je_witty(vysv) and any(m in first.lower() for m in _WITTY_MARKERS):
        return ""
    return first


def mean_vysvetleni(
    fact: dict[str, Any],
    topic: dict[str, Any] | None,
    svejk_lead: str,
    *,
    dopad_fallback: str,
    mean_from_dopad: Callable[[str, str], str],
) -> str:
    """Co to znamená pro vás: jen věcné vysvětlení, bez švejkovské pointy."""
    if (fact.get("mean") or "").strip():
        return fact["mean"].strip()

    vysv = (topic or {}).get("tema_vysvetleni") or ""
    factual = _faktualni_z_vysvetleni(vysv, svejk_lead)
    if factual:
        return _zkrat(factual)

    blok = blok_z_fact_topic(fact, topic)
    listy_mean = _co_to_znamena(blok, svejk_lead)
    if listy_mean:
        return _zkrat(listy_mean)

    return _zkrat(mean_from_dopad(dopad_fallback, svejk_lead))


def nadpis_z_clanku(fact: dict[str, Any], topic: dict[str, Any] | None) -> str:
    if (fact.get("nadpis") or "").strip():
        return fact["nadpis"].strip()
    return _nadpis_bodu(blok_z_fact_topic(fact, topic)) or fact.get("slug", "")


# zpětná kompatibilita pro review / staré importy
def lead_z_clanku(
    fact: dict[str, Any],
    topic: dict[str, Any] | None,
    *,
    state: dict,
    use_poslusne: bool,
    fallback: Callable[[], str],
) -> str:
    return lead_svejkovsky(
        fact, topic, state=state, use_poslusne=use_poslusne, fallback=fallback
    )


def mean_z_clanku(
    fact: dict[str, Any],
    topic: dict[str, Any] | None,
    lead: str,
    *,
    state: dict,
    dopad_fallback: str,
    mean_from_dopad: Callable[[str, str], str],
) -> str:
    return mean_vysvetleni(
        fact,
        topic,
        lead,
        dopad_fallback=dopad_fallback,
        mean_from_dopad=mean_from_dopad,
    )


_TEMA_Z_CLANKU: tuple[tuple[tuple[str, ...], str], ...] = (
    (("zkumav", "laborator", "odběr"), "docházející zkumavky v nemocnicích"),
    (("dávk", "přídav", "sociální podpo"), "dávky pro rodiny"),
    (("živnost", "záloh", "odvod", "pojist"), "levnější zálohy pro živnostníky"),
    (("stavebn", "stavba", "územní plán"), "změny ve stavebním zákoně"),
    (("důchod", "penzij", "penze"), "pravidla penzí a důchodů"),
    (("energ", "elektr", "plyn"), "energetiku a sítě"),
    (("doprav", "silnic", "železn"), "dopravu a infrastrukturu"),
    (("výbor", "personál", "komis"), "personálku a obsazení funkcí"),
)


def _tema_z_clanku(nadpis: str, lead: str, kick: str) -> str:
    blob = f"{nadpis} {lead} {kick}".lower()
    for keys, tema in _TEMA_Z_CLANKU:
        if any(k in blob for k in keys):
            return tema
    t = (nadpis or "bod programu").strip()
    if not t:
        return "bod programu"
    if len(t) > 50:
        return t[0].lower() + t[1:47] + "…"
    return t[0].lower() + t[1:]


def _pointa_z_leadu(lead: str) -> str:
    lead = (lead or "").strip()
    if not lead:
        return ""
    vety = re.split(r"(?<=[.!?])\s+", lead)
    for v in reversed(vety):
        v = v.strip()
        if not v or v.lower().startswith("poslušně hlásím"):
            continue
        low = v.lower()
        if any(
            m in low
            for m in _WITTY_MARKERS + ("spíš", "jiná kapitola", "netankuje", "kapitola")
        ):
            return v if v.endswith((".", "!", "?")) else f"{v}."
    if len(vety) >= 2:
        tail = vety[-1].strip()
        # fragment po rozseknutí data („1. července, ale …“) začíná malým písmenem
        if (
            tail
            and len(tail) < 110
            and not tail.lower().startswith("poslušně")
            and tail[:1].isupper()
        ):
            return tail if tail.endswith((".", "!", "?")) else f"{tail}."
    return ""


def _spojene_pointy(pointy: list[str]) -> str:
    clean = [p.strip() for p in pointy if (p or "").strip()]
    if not clean:
        return ""
    if len(clean) == 1:
        return clean[0].rstrip(".")
    a, b = clean[0].rstrip("."), clean[1].rstrip(".")
    return f"{a}; {b[0].lower()}{b[1:]}"


def _profil_dne(motivy: list[str]) -> str | None:
    ml = " ".join(motivy).lower()
    if "zkumav" in ml and ("živnost" in ml or "záloh" in ml):
        return "zkumavky_zivnostnici"
    return None


def _verdikt_den_clause(
    items: list[Any],
    *,
    proslo: int,
    zamitnuto: int,
) -> str:
    if zamitnuto > proslo and zamitnuto > 0:
        return "víc návrhů padlo než prošlo"
    if proslo and not zamitnuto and items and all(
        getattr(it, "verdikt", "") == "schvaleno" for it in items
    ):
        return "co je ve vydání, prošlo"
    if proslo or zamitnuto:
        return f"ve sněmovně prošlo {proslo} a padlo {zamitnuto}"
    return "shrnutí sedí s články výše"


def _glosa_zkumavky_zivnostnici(pointy: list[str], *, datum: str) -> str:
    sablony = (
        "že dnes ve sněmovně schválili hlídání docházejících zkumavek "
        "i levnější zálohy pro živnostníky; sestřičkám přijde včas zásoba, "
        "živnostníkům míň z peněženky, a čtenáři, co není ani jedno, "
        "může klidně zůstat u piva.",
        "že program spojil nemocniční sklad a živnostenský účet: zkumavky "
        "mají hlásit dřív, než dojdou, a OSVČ ušetří na zálohách; "
        "doma vás to netankuje, pokud nejste sestra i živnostník najednou.",
        "že ve vydání jsou zkumavky v nemocnicích a levnější zálohy pro živnostníky; "
        "jedno vás doma netankuje, u druhého platí, že míň odvodů znamená míň důchod.",
    )
    seed = f"zg-zk|{datum}|{_spojene_pointy(pointy)}"
    return sablony[_hash_seed(seed) % len(sablony)]


def _glosa_jeden(
    item: Any,
    motiv: str,
    pointy: list[str],
    *,
    datum: str,
    proslo: int,
    zamitnuto: int,
    stats: dict[str, Any],
) -> str:
    v = _verdikt_den_clause([item], proslo=proslo, zamitnuto=zamitnuto)
    p = _spojene_pointy(pointy)
    maraton = int(stats.get("minuty") or 0) >= 360

    if p:
        sablony = (
            f"že dnešní vydání stojí na {motiv}; {v}. {p}",
            f"že celý den se točil kolem {motiv}, {v}, a řekl bych: {p}",
        )
    else:
        sablony = (
            f"že dnešní vydání má jediného hrdinu, {motiv}; {v}, zbytek je v textu výše.",
            f"že celá stránka je jedna kapitola, {motiv}; {v}.",
        )
    telo = sablony[_hash_seed(f"zg-1|{datum}|{motiv}") % len(sablony)]
    if maraton:
        telo += " Schůze trvala do večera, glosa je aspoň kratší."
    return telo


def _glosa_dva(
    motivy: list[str],
    pointy: list[str],
    items: list[Any],
    *,
    datum: str,
    proslo: int,
    zamitnuto: int,
) -> str:
    m0, m1 = motivy[0], motivy[1]
    v = _verdikt_den_clause(items, proslo=proslo, zamitnuto=zamitnuto)
    p = _spojene_pointy(pointy)

    if p:
        sablony = (
            f"že dnes ve sněmovně řešili {m0} i {m1}; {v}. {p}",
            f"že program spojil {m0} a {m1}, {v}, a na závěr: {p}",
        )
    else:
        sablony = (
            f"že poslanci v jednom dni proběhli {m0} i {m1}; {v}, detaily jsou v článcích výše.",
            f"že dnešní vydání táhne dvěma směry, {m0} a {m1}; {v}.",
        )
    return sablony[_hash_seed(f"zg-2|{datum}|{m0}|{m1}|{p}") % len(sablony)]


def _glosa_vic(
    motivy: list[str],
    items: list[Any],
    *,
    datum: str,
    proslo: int,
    zamitnuto: int,
    stats: dict[str, Any],
) -> str:
    n = len(items)
    m0, m_last = motivy[0], motivy[-1]
    v = _verdikt_den_clause(items, proslo=proslo, zamitnuto=zamitnuto)
    pointy = [_pointa_z_leadu(getattr(it, "lead", "")) for it in items[:2]]
    p = _spojene_pointy([x for x in pointy if x])

    sablony = (
        f"že vydání shrnuje {n} bodů od {m0} po {m_last}; {v}.",
        f"že dnes ve sněmovně proběhlo {n} témat, od {m0} po {m_last}; {v}, zbytek je v textech výše.",
    )
    if p and n >= 2:
        sablony = (
            f"že vydání má {n} bodů, nejdřív {m0}, nakonec {m_last}; {v}. {p}",
            sablony[0].rstrip(".") + f" {p}",
        )
    telo = sablony[_hash_seed(f"zg-n|{datum}|{n}|{m0}") % len(sablony)]
    if int(stats.get("minuty") or 0) >= 360:
        telo += " Jednání se protáhlo, glosa už ne."
    return telo


def zaver_glosa_dne(
    items: list[Any],
    *,
    datum: str,
    proslo: int,
    zamitnuto: int,
    stats: dict[str, Any],
    state: dict,
) -> str:
    """Závěrečná glosa dne: shrnutí obsahu stránky ve švejkovském tónu."""
    del state  # rezervováno pro budoucí variace
    if not items:
        if proslo or zamitnuto:
            return (
                "Poslušně hlásím, že dnes ve sněmovně "
                f"{proslo} {'věc' if proslo == 1 else 'věci'} prošly a {zamitnuto} "
                f"{'návrh' if zamitnuto == 1 else 'návrhů'} padlo, v tomto vydání bez článků."
            )
        return (
            "Poslušně hlásím, že dnešní vydání je prázdné, "
            "sněmovna asi jen klokotala."
        )

    motivy = [
        _tema_z_clanku(
            getattr(it, "nadpis", ""),
            getattr(it, "lead", ""),
            getattr(it, "kick", ""),
        )
        for it in items
    ]
    pointy = [_pointa_z_leadu(getattr(it, "lead", "")) for it in items]

    profil = _profil_dne(motivy)
    if profil == "zkumavky_zivnostnici":
        telo = _glosa_zkumavky_zivnostnici(pointy, datum=datum)
    elif len(items) == 1:
        telo = _glosa_jeden(
            items[0],
            motivy[0],
            pointy,
            datum=datum,
            proslo=proslo,
            zamitnuto=zamitnuto,
            stats=stats,
        )
    elif len(items) == 2:
        telo = _glosa_dva(
            motivy,
            pointy,
            items,
            datum=datum,
            proslo=proslo,
            zamitnuto=zamitnuto,
        )
    else:
        telo = _glosa_vic(
            motivy,
            items,
            datum=datum,
            proslo=proslo,
            zamitnuto=zamitnuto,
            stats=stats,
        )

    if not telo.startswith("že "):
        telo = f"že {telo[0].lower()}{telo[1:]}" if telo else "že shrnutí je v článcích výše."
    return f"Poslušně hlásím, {telo}"
