"""Švejkovský lead + pointa pod nadpisem; věcné vysvětlení v „Co to znamená“."""

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


def _pointa_pod_nadpis(
    fact: dict[str, Any],
    topic: dict[str, Any] | None,
    glosa: str,
    *,
    state: dict,
) -> str:
    if (fact.get("pointa") or "").strip():
        return fact["pointa"].strip()

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
        return fact["lead"].strip()

    blok = blok_z_fact_topic(fact, topic)
    vysv = (topic or {}).get("tema_vysvetleni") or ""
    listy_lead = _lead_veta(blok, state=state, use_poslusne=use_poslusne)
    if listy_lead:
        return listy_lead

    if vysv_je_witty(vysv):
        first = _prvni_veta(vysv)
        if first:
            if use_poslusne and state.get("poslusne_count", 0) < 1:
                state["poslusne_count"] = state.get("poslusne_count", 0) + 1
                body = first[0].lower() + first[1:]
                return f"Poslušně hlásím, že {body}"
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
    """Co to znamená: jen věcné vysvětlení, bez švejkovské pointy."""
    if (fact.get("mean") or "").strip():
        return _zkrat(fact["mean"].strip())

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
