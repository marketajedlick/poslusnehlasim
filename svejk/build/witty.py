"""Vtipné leady, krátké „Co to znamená“ a napojení na listy."""

from __future__ import annotations

import re
from typing import Any, Callable

from svejk.listy import (
    _co_to_znamena,
    _lead_veta,
    _nadpis_bodu,
    _pointa_jednou,
)
from svejk.obcansky import GENERIC_GLOSA_MARKERS
from svejk.timeline import BlokDne

_MEAN_MAX_LEN = 160

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
        svejk=(t.get("tema_svejk") or "").strip(),
        vysvetleni=(t.get("tema_vysvetleni") or "").strip(),
        nazev=(fact.get("nazev") or "").strip(),
        pocet_hlasovani=int(fact.get("pocet_hlasovani") or 0),
        pocet_prijato=int(t.get("pocet_prijato") or 0),
        pocet_zamitnuto=int(t.get("pocet_zamitnuto") or 0),
        proslo=bool(fact.get("proslo", True)),
    )


def vysv_je_witty(vysv: str) -> bool:
    if not (vysv or "").strip():
        return False
    low = vysv.lower()
    if any(g in low for g in _GENERIC_VYSV):
        return False
    if any(m in low for m in _WITTY_MARKERS):
        return True
    for sep in (" — ", " – "):
        if sep in vysv:
            right = vysv.split(sep, 1)[1].strip()
            if right and len(right) < 120:
                return True
    return False


def _prvni_veta(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return ""
    part = re.split(r"\s*[—–]\s*", t, maxsplit=1)[0].strip()
    v = re.split(r"(?<=[.!?])\s+", part, maxsplit=1)[0].strip()
    if v and not v.endswith((".", "!", "?")):
        v += "."
    return v


def _zkrat_mean(text: str, *, max_len: int = _MEAN_MAX_LEN) -> str:
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


def mean_z_vysvetleni(vysv: str, lead: str) -> str:
    if not vysv_je_witty(vysv):
        return ""

    low = vysv.lower()
    if "netankuje" in low:
        return "Vás doma to netankuje, to je spíš věc pro sestry."

    if "715" in vysv and "míň důchod" in low:
        return "úspora cca 715 Kč měsíčně. Míň odvodů, míň důchod — to už je jiná kapitola."

    for sep in (" — ", " – "):
        if sep in vysv:
            right = vysv.split(sep, 1)[1].strip()
            if right and any(m in right.lower() for m in _WITTY_MARKERS + ("spíš",)):
                if "netankuje" in right.lower():
                    return "Vás doma to netankuje, to je spíš věc pro sestry."
                if not right.endswith((".", "!", "?")):
                    right += "."
                return _zkrat_mean(right)

    vety = re.split(r"(?<=[.!?])\s+", vysv.strip())
    tail = [v for v in vety[1:] if v.strip()]
    skip = ("platí od ledna", "přeplatek vrátí")
    picked = [v for v in tail if not any(s in v.lower() for s in skip)]
    if not picked and len(vety) >= 2:
        picked = [vety[-1]]
    if picked:
        text = " ".join(picked)
        if lead and lead.rstrip(".") in text:
            text = text.replace(lead.rstrip("."), "", 1).strip(" .")
        return _zkrat_mean(text)
    return ""


def nadpis_z_clanku(fact: dict[str, Any], topic: dict[str, Any] | None) -> str:
    if (fact.get("nadpis") or "").strip():
        return fact["nadpis"].strip()
    return _nadpis_bodu(blok_z_fact_topic(fact, topic)) or fact.get("slug", "")


def lead_z_clanku(
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
        low = listy_lead.lower()
        if vysv_je_witty(vysv) and (
            "schválili změny v " in low or "zamítli změny v " in low
        ):
            first = _prvni_veta(vysv)
            if first:
                if use_poslusne and state.get("poslusne_count", 0) < 1:
                    state["poslusne_count"] = state.get("poslusne_count", 0) + 1
                    body = first[0].lower() + first[1:]
                    return f"Poslušně hlásím, že {body}"
                return first
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


def mean_z_clanku(
    fact: dict[str, Any],
    topic: dict[str, Any] | None,
    lead: str,
    *,
    state: dict,
    dopad_fallback: str,
    mean_from_dopad: Callable[[str, str], str],
) -> str:
    if (fact.get("mean") or "").strip():
        return _zkrat_mean(fact["mean"].strip())

    vysv = (topic or {}).get("tema_vysvetleni") or ""
    witty = mean_z_vysvetleni(vysv, lead)
    if witty:
        return witty

    blok = blok_z_fact_topic(fact, topic)
    listy_mean = _co_to_znamena(blok, lead)
    if listy_mean:
        pt = _pointa_jednou(blok, lead, listy_mean, state=state)
        text = f"{listy_mean} {pt}".strip() if pt else listy_mean
        return _zkrat_mean(text)

    return _zkrat_mean(mean_from_dopad(dopad_fallback, lead))


def glosa_generic(vysv: str) -> bool:
    if not vysv:
        return True
    low = vysv.lower()
    return any(g in low for g in GENERIC_GLOSA_MARKERS + _GENERIC_VYSV)
