"""Sdílená logika pro vyhodnocení témat a hlasování."""

from __future__ import annotations

import re
from typing import Literal

from svejk.noviny import _law_kategorie
from svejk.jednaci_den import vote_chrono_key
from svejk.timeline import BlokDne


def vote_kategorie(nazev: str) -> str:
    blok = BlokDne(
        cas_od="",
        cas_do="",
        typ="law",
        svejk="",
        nazev=nazev,
    )
    return _law_kategorie(blok)


def topic_proslo_druhe_cteni_ukonceno(steno_texts: list[str]) -> bool:
    """Druhé čtení skončilo bez zamítnutí celého návrhu (posun k třetímu čtení)."""
    joined = "\n".join(steno_texts).lower()
    if "končím tedy druhé čtení" not in joined:
        return False
    if "návrh na vrácení zákona garančnímu výboru" in joined:
        return True
    if "nepadly žádné návrhy, o kterých by se mělo hlasovat" in joined:
        return True
    return False


# Typ hlasování ze stena. UNL typ návrhu nemá; předsedající ho ale ohlašuje
# („vyslovuje souhlas s návrhem zákona“, „přikázán k projednání výboru“, …).
_HLASOVANI_CISLO_RE = re.compile(r"hlasování(?:\s+pořadové)?\s+číslo\s+(\d+)", re.I)
_RE_FINAL = re.compile(
    r"(?:vyslovuje|vyslovila|vyslovit)\s+souhlas\s+s\s+(?:\w+\s+){0,3}návrhem\s+(?:ústavního\s+)?zákona"
    r"|schvaluje\s+(?:\w+\s+){0,2}návrh\s+zákona"
    r"|návrh\w*\s+zákona\s+jako\s+celku"
    r"|jsme\s+(?:tento\s+)?návrh\s+zákona\s+(?:přijali|schválili)",
    re.I,
)
_RE_REJECT = re.compile(
    r"návrh\w*\s+na\s+zamítnutí|zamítnout\s+(?:tento\s+)?návrh\s+zákona|návrh\s+zákona\s+zamít", re.I
)
_RE_RETURN = re.compile(
    r"(?:vrácení|vrátit|vrací)\s+(?:\w+\s+){0,6}(?:výbor|k\s+novému\s+projednání|do\s+druhého)", re.I
)
_RE_REFER = re.compile(r"přikáz\w*|přikazuje", re.I)
_RE_PAUSE = re.compile(r"přeruš\w*", re.I)
_RE_AMEND = re.compile(
    r"pozměňovací|legislativně\s+technick|návrh\s+(?:pana|paní)\s+poslan|zkrácení\s+lhůty|lhůt", re.I
)

VoteMotion = Literal[
    "zaverecne", "zamitnuti", "vraceni", "prikazani", "preruseni", "pozmenovak", "jine"
]
TopicVysledek = Literal["schvaleno", "zamitnuto", "vraceno_vyboru", "postup", "preruseno"]


def classify_vote_motion(pre: str, post: str) -> VoteMotion:
    """Typ hlasování z textu před ohlášením (návrh) a po něm (konstatování)."""
    if _RE_FINAL.search(post) or _RE_FINAL.search(pre):
        return "zaverecne"
    if _RE_REFER.search(post):
        return "prikazani"
    if _RE_REJECT.search(pre):
        return "zamitnuti"
    if _RE_RETURN.search(pre):
        return "vraceni"
    if _RE_AMEND.search(pre):
        return "pozmenovak"
    if _RE_REFER.search(pre):
        return "prikazani"
    if _RE_PAUSE.search(pre):
        return "preruseni"
    return "jine"


def vote_motions_from_steno(steno: list[dict]) -> dict[int, VoteMotion]:
    """{číslo hlasování ve schůzi: typ} podle ohlášení „Hlasování číslo N“ ve stenu."""
    out: dict[int, VoteMotion] = {}
    recs = sorted(steno, key=lambda r: int(r.get("poradi") or 0))
    texts = [r.get("text") or "" for r in recs]
    for i, text in enumerate(texts):
        matches = list(_HLASOVANI_CISLO_RE.finditer(text))
        for j, m in enumerate(matches):
            start = matches[j - 1].end() if j else 0
            pre = text[start : m.start()]
            if not j and len(pre) < 300 and i:
                pre = texts[i - 1][-(450 - len(pre)) :] + " " + pre
            pre = pre[-450:]
            end = matches[j + 1].start() if j + 1 < len(matches) else len(text)
            post = text[m.end() : end][:300]
            cut = re.search(r"Zahajuji hlasování|Přednesu|návrh usnesení", post)
            if cut:
                post = post[: cut.start()]
            out.setdefault(int(m.group(1)), classify_vote_motion(pre, post))
    return out


def topic_vysledek(group: list[dict], motions: dict[int, str] | None) -> TopicVysledek | None:
    """Výsledek bodu podle typu hlasování; None = ze stena nejde určit.

    Závěrečné hlasování rozhoduje vždy (poslední, kvůli přehlasování veta).
    Jinak poslední přijatý procedurální krok; přerušení jen když je úplně poslední.
    """
    if not motions:
        return None
    group = sorted(group, key=vote_chrono_key)
    final = [v for v in group if motions.get(int(v.get("cislo") or 0)) == "zaverecne"]
    if final:
        return "schvaleno" if final[-1].get("vysledek") == "A" else "zamitnuto"
    events = {"zamitnuti": "zamitnuto", "vraceni": "vraceno_vyboru", "prikazani": "postup"}
    last: TopicVysledek | None = None
    for v in group:
        kind = motions.get(int(v.get("cislo") or 0))
        if kind in events and v.get("vysledek") == "A":
            last = events[kind]  # type: ignore[assignment]
    if last:
        return last
    if group and motions.get(int(group[-1].get("cislo") or 0)) == "preruseni" and group[-1].get("vysledek") == "A":
        return "preruseno"
    return None


def topic_proslo_from_votes(group: list[dict], motions: dict[int, str] | None = None) -> bool:
    """Prošlo bod? Se stenem podle typu hlasování, jinak heuristika z výsledků.

    Heuristika: stačí rozhodující A (pro > proti), u maratonů přerušení ne.
    Bez typu hlasování ale „prošlo“ i téma, kde prošel jen pozměňovák.
    """
    vysledek = topic_vysledek(group, motions)
    if vysledek is not None:
        return vysledek in ("schvaleno", "postup")
    group = sorted(group, key=vote_chrono_key)
    if not group:
        return False
    prijato = sum(1 for v in group if v.get("vysledek") == "A")
    zamitnuto = sum(1 for v in group if v.get("vysledek") == "R")
    decisive = [
        v
        for v in group
        if v.get("vysledek") == "A" and (v.get("pro") or 0) > (v.get("proti") or 0)
    ]
    if not decisive:
        return False
    if prijato <= 2 and zamitnuto >= max(10, prijato * 5):
        return False
    return True


def spor_o_porad_schuze(day_votes: list[dict]) -> bool:
    """True, pokud hlasování o pořadu vypadá jako výrazný spor (ne jen rutina)."""
    porad = [v for v in day_votes if v.get("je_porad_schuze")]
    if not porad:
        return False
    if max(v.get("proti", 0) for v in porad) >= 40:
        return True
    if len(porad) >= 3:
        return True
    times = sorted({v.get("cas", "")[:5] for v in porad if v.get("cas")})
    if len(times) >= 2:
        sh, sm = int(times[0][:2]), int(times[0][3:5])
        eh, em = int(times[-1][:2]), int(times[-1][3:5])
        if (eh * 60 + em) - (sh * 60 + sm) >= 20:
            return True
    return False


def debata_vysledek_radek(stats: dict) -> str:
    """Třetí odrážka ve Výsledku dne podle délky debaty a sporu o pořadu."""
    if stats.get("spor_o_porad"):
        return "* nejdřív se dlouho hádali o pořadu dne"
    if stats.get("dlouha_debata"):
        minuty = int(stats.get("minuty") or 0)
        if minuty >= 240:
            return "* celé odpoledne se mluvilo o jednom bodu"
        return "* dlouhá debata u jednoho bodu"
    return "* nikdo se nepohádal tak, aby to stálo za zmínku"


# Verdikt článku, který přímo odporuje výsledku hlasování.
_VERDIKT_ROZPOR: dict[str, frozenset[str]] = {
    "schvaleno": frozenset({"zamitnuto", "vraceno_vyboru"}),
    "zvoleno": frozenset({"zamitnuto"}),
    "zamiteno": frozenset({"schvaleno", "postup"}),
}


def verdikt_odporuje(verdikt: str, vysledek: str | None) -> bool:
    return bool(vysledek) and vysledek in _VERDIKT_ROZPOR.get(verdikt or "", frozenset())


def verdikt_z_vysledku(vysledek: str | None) -> str | None:
    return {
        "schvaleno": "schvaleno",
        "zamitnuto": "zamiteno",
        "vraceno_vyboru": "odlozeno",
        "preruseno": "odlozeno",
        "postup": "prvni_cteni",
    }.get(vysledek or "")
