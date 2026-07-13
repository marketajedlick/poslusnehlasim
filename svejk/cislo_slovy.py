"""Čísla v textu — slovní tvar místo číslic."""

from __future__ import annotations

import re

_JEDNOTKY = (
    "nula",
    "jedna",
    "dvě",
    "tři",
    "čtyři",
    "pět",
    "šest",
    "sedm",
    "osm",
    "devět",
    "deset",
    "jedenáct",
    "dvanáct",
    "třináct",
    "čtrnáct",
    "patnáct",
    "šestnáct",
    "sedmnáct",
    "osmnáct",
    "devatenáct",
)

_DESITKY = (
    "",
    "",
    "dvacet",
    "třicet",
    "čtyřicet",
    "padesát",
    "šedesát",
    "sedmdesát",
    "osmdesát",
    "devadesát",
)

_STOVKY = (
    "",
    "sto",
    "dvě stě",
    "tři sta",
    "čtyři sta",
    "pět set",
    "šest set",
    "sedm set",
    "osm set",
    "devět set",
)


def cislo_slovy(n: int) -> str:
    """Kardinální číslovka (ženský/mužský neutrální tvar pro skládání)."""
    if n < 0:
        return str(n)
    if n < 20:
        return _JEDNOTKY[n]
    if n < 100:
        des, jed = divmod(n, 10)
        if jed == 0:
            return _DESITKY[des]
        return f"{_DESITKY[des]} {_JEDNOTKY[jed]}"
    if n < 1000:
        sto, rest = divmod(n, 100)
        if rest == 0:
            return _STOVKY[sto]
        return f"{_STOVKY[sto]} {cislo_slovy(rest)}"
    if n < 1_000_000:
        tis, rest = divmod(n, 1000)
        if rest == 0:
            return _tisice(tis)
        return f"{_tisice(tis)} {cislo_slovy(rest)}"
    return str(n)


def _tisice(n: int) -> str:
    if n == 1:
        return "tisíc"
    if 2 <= n <= 4:
        return f"{cislo_slovy(n)} tisíce"
    return f"{cislo_slovy(n)} tisíc"


def krat_slovy(n: int) -> str:
    """„jednou“, „dvakrát“, „čtyřicetčtyřikrát“."""
    n = int(n)
    if n == 1:
        return "jednou"
    if n == 2:
        return "dvakrát"
    if n == 3:
        return "třikrát"
    if n == 4:
        return "čtyřikrát"
    return f"{cislo_slovy(n).replace(' ', '')}krát"


_ORD_GEN = (
    "",
    "prvního",
    "druhého",
    "třetího",
    "čtvrtého",
    "pátého",
    "šestého",
    "sedmého",
    "osmého",
    "devátého",
    "desátého",
    "jedenáctého",
    "dvanáctého",
    "třináctého",
    "čtrnáctého",
    "patnáctého",
    "šestnáctého",
    "sedmnáctého",
    "osmnáctého",
    "devatenáctého",
    "dvacátého",
    "jednadvacátého",
    "dvaadvacátého",
    "třiadvacátého",
    "čtyřiadvacátého",
    "pětadvacátého",
    "šestadvacátého",
    "sedmadvacátého",
    "osmadvacátého",
    "devětadvacátého",
    "třicátého",
    "třicátého prvního",
)

_ORD_LOC = (
    "",
    "prvnímu",
    "druhému",
    "třetímu",
    "čtvrtému",
    "pátému",
    "šestému",
    "sedmému",
    "osmému",
    "devátému",
    "desátému",
    "jedenáctému",
    "dvanáctému",
    "třináctému",
    "čtrnáctému",
    "patnáctému",
    "šestnáctému",
    "sedmnáctému",
    "osmnáctému",
    "devatenáctému",
    "dvacátému",
    "jednadvacátému",
    "dvaadvacátému",
    "třiadvacátému",
    "čtyřiadvacátému",
    "pětadvacátému",
    "šestadvacátému",
    "sedmadvacátému",
    "osmadvacátému",
    "devětadvacátému",
    "třicátému",
    "třicátému prvnímu",
)


def _poradove_gen(n: int) -> str:
    if 1 <= n < len(_ORD_GEN):
        return _ORD_GEN[n]
    return cislo_slovy(n)


def _poradove_loc(n: int) -> str:
    if 1 <= n < len(_ORD_LOC):
        return _ORD_LOC[n]
    return cislo_slovy(n)


def _predlozka_v(slovo: str) -> str:
    return "ve" if slovo[:1].lower() in "0123456789dfhlmnrstv" else "v"


def cas_slovy(hod: int, minuta: int) -> str:
    """„ve čtrnáct hodin dvacet čtyři minut“, „ve dvacet dva hodin“."""
    hod = int(hod)
    minuta = int(minuta)
    if minuta == 0:
        hodiny = cislo_slovy(hod)
        return f"{_predlozka_v(hodiny)} {hodiny} hodin"
    hodiny = cislo_slovy(hod)
    minuty = cislo_slovy(minuta)
    return f"{_predlozka_v(hodiny)} {hodiny} hodin {minuty} minut"


_LOC_JEDNOTKY = (
    "",
    "jednom",
    "dvou",
    "třech",
    "čtyřech",
    "pěti",
    "šesti",
    "sedmi",
    "osmi",
    "devíti",
    "deseti",
    "jedenácti",
    "dvanácti",
    "třinácti",
    "čtrnácti",
    "patnácti",
    "šestnácti",
    "sedmnácti",
    "osmnácti",
    "devatenácti",
)

_LOC_DESITKY = (
    "",
    "",
    "dvaceti",
    "třiceti",
    "čtyřiceti",
    "padesáti",
    "šedesáti",
    "sedmdesáti",
    "osmdesáti",
    "devadesáti",
)


def _po_tvarem(n: int) -> str:
    if n < 20:
        return _LOC_JEDNOTKY[n]
    if n < 100:
        des, jed = divmod(n, 10)
        if jed == 0:
            return _LOC_DESITKY[des]
        return f"{_LOC_DESITKY[des]} {_LOC_JEDNOTKY[jed]}"
    if n < 1000:
        sto, rest = divmod(n, 100)
        if rest == 0:
            return "stu" if sto == 1 else f"{_LOC_JEDNOTKY[sto]} stech"
        return f"{_LOC_JEDNOTKY[sto] if sto < 20 else cislo_slovy(sto)} {_po_tvarem(rest)}"
    return cislo_slovy(n)


def po_hlasovanich(n: int) -> str:
    """„po pěti hlasováních“, „po jednom hlasování“."""
    n = int(n)
    if n <= 0:
        return ""
    if n == 1:
        return "po jednom hlasování"
    return f"po {_po_tvarem(n)} hlasováních"


def po_hlasovanich_cap(n: int) -> str:
    t = po_hlasovanich(n)
    if t.startswith("po "):
        return "Po " + t[3:]
    return t.capitalize() if t else t


def krat_se_hlasovalo(n: int) -> str:
    """„pětkrát se hlasovalo“, „jednou se hlasovalo“."""
    n = int(n)
    if n <= 0:
        return ""
    if n == 1:
        return "jednou se hlasovalo"
    if n == 2:
        return "dvakrát se hlasovalo"
    if n == 3:
        return "třikrát se hlasovalo"
    if n == 4:
        return "čtyřikrát se hlasovalo"
    return f"{cislo_slovy(n).replace(' ', '')}krát se hlasovalo"


def krat_hlasovali(n: int) -> str:
    n = int(n)
    if n <= 0:
        return ""
    if n == 1:
        return "jednou hlasovali"
    if n == 2:
        return "dvakrát hlasovali"
    if n == 3:
        return "třikrát hlasovali"
    if n == 4:
        return "čtyřikrát hlasovali"
    return f"{cislo_slovy(n).replace(' ', '')}krát hlasovali"


def n_hlasovani(n: int) -> str:
    """„pět hlasování“, „jedno hlasování“ (nominál)."""
    n = int(n)
    if n <= 0:
        return ""
    if n == 1:
        return "jedno hlasování"
    if n == 2:
        return "dvě hlasování"
    if n <= 4:
        return f"{cislo_slovy(n)} hlasování"
    return f"{cislo_slovy(n)} hlasování"


_RE_PO_HLAS = re.compile(
    r"\b[Pp]o\s+(\d+)\s*(?:×\s*)?hlasován[ií]",
    re.IGNORECASE,
)
_RE_KRAT_HLASOVALI = re.compile(r"\b(\d+)\s*[x×]\s*hlasovali\b", re.IGNORECASE)
_RE_KRAT_SE_HLASOVALO = re.compile(r"\b(\d+)\s*[x×]\s*se\s+hlasovalo\b", re.IGNORECASE)
_RE_N_HLASOVANI = re.compile(r"\b(\d+)\s+hlasování\b", re.IGNORECASE)
_RE_CAS = re.compile(r"\b(?:v|ve)\s+(\d{1,2}):(\d{2})\b")
_RE_KRAT = re.compile(r"\b(\d+)\s*[x×](?!\s*hlasoval)", re.IGNORECASE)
_RE_TISICE = re.compile(r"\b(\d{1,3}(?:\s\d{3})+)\b")
_RE_DATUM_GEN = re.compile(
    r"\b(\d{1,2})\.\s+"
    r"(ledna|února|března|dubna|května|června|července|srpna|září|října|listopadu|prosince)\b",
    re.IGNORECASE,
)
_RE_DATUM_LOC = re.compile(
    r"\bk\s+(\d{1,2})\.\s+"
    r"(lednu|únoru|březnu|dubnu|květnu|červnu|červenci|srpnu|září|říjnu|listopadu|prosinci)\b",
    re.IGNORECASE,
)
_RE_CISLO = re.compile(r"\b(\d+)\b")
_RE_MESIC_ROK = re.compile(
    r"\b(ledna|února|března|dubna|května|června|července|srpna|září|října|listopadu|prosince|"
    r"lednu|únoru|březnu|dubnu|květnu|červnu|červenci|srpnu|říjnu|listopadu|prosinci)\s+"
    r"((?:19|20)\d{2})\b",
    re.IGNORECASE,
)
_RE_EET_VERZE = re.compile(r"\bEET\s+\d+\.\d+\b", re.IGNORECASE)


def _je_kalendarni_rok(n: int) -> bool:
    return 1900 <= n <= 2099


def _rok_nebo_cislo(m: re.Match[str], text: str) -> str:
    n = int(m.group(1))
    start = m.start()
    end = m.end()
    if start > 0 and text[start - 1] == "/":
        return str(n)
    if end < len(text) and text[end] == "/":
        return str(n)

    if not _je_kalendarni_rok(n):
        return cislo_slovy(n)

    prefix = text[max(0, start - 20) : start].lower()
    if re.search(r"(?:\brok[u]?\s|\broce\s|\bna\s+)$", prefix):
        return str(n)
    if re.search(
        r"(ledna|února|března|dubna|května|června|července|srpna|září|října|listopadu|prosince|"
        r"lednu|únoru|březnu|dubnu|květnu|červnu|červenci|srpnu|říjnu|prosinci)\s+$",
        prefix,
    ):
        return str(n)

    return f"rok {n}"


def nahrad_hlasovani_v_textu(text: str) -> str:
    """Doplní slovní tvar u zbývajících číselných zmínek o hlasování."""
    if not text or not re.search(r"\d", text):
        return text

    def _po(m: re.Match[str]) -> str:
        return po_hlasovanich_cap(int(m.group(1)))

    def _krat_ali(m: re.Match[str]) -> str:
        return krat_hlasovali(int(m.group(1)))

    def _krat_se(m: re.Match[str]) -> str:
        return krat_se_hlasovalo(int(m.group(1)))

    def _nom(m: re.Match[str]) -> str:
        return n_hlasovani(int(m.group(1)))

    t = _RE_PO_HLAS.sub(_po, text)
    t = _RE_KRAT_HLASOVALI.sub(_krat_ali, t)
    t = _RE_KRAT_SE_HLASOVALO.sub(_krat_se, t)
    t = _RE_N_HLASOVANI.sub(_nom, t)
    return t


def _nahrad_zbyla_cisla(text: str) -> str:
    if not text or not re.search(r"\d", text):
        return text

    def _cas(m: re.Match[str]) -> str:
        return m.group(0)

    def _krat(m: re.Match[str]) -> str:
        return krat_slovy(int(m.group(1)))

    def _tis(m: re.Match[str]) -> str:
        return cislo_slovy(int(m.group(1).replace(" ", "")))

    def _datum_gen(m: re.Match[str]) -> str:
        den = int(m.group(1))
        return f"{_poradove_gen(den)} {m.group(2).lower()}"

    def _datum_loc(m: re.Match[str]) -> str:
        den = int(m.group(1))
        return f"k {_poradove_loc(den)} {m.group(2).lower()}"

    def _cislo(m: re.Match[str]) -> str:
        start, end = m.start(), m.end()
        # Skóre hlasování (105:64) necháváme číslicemi, ne jako čas.
        if end < len(t) and t[end] == ":" and end + 1 < len(t) and t[end + 1].isdigit():
            return m.group(1)
        if start > 0 and t[start - 1] == ":":
            return m.group(1)
        # TOP 09 – strana, ne slovní číslo
        if start >= 4 and t[start - 4 : start].upper() == "TOP ":
            return m.group(1)
        # ponytail: očíslovaný seznam (01 - NATO) necháváme; upgrade = širší whitelist v compose
        if (
            len(m.group(1)) == 2
            and m.group(1).isdigit()
            and end + 2 <= len(t)
            and t[end : end + 2] == " -"
        ):
            return m.group(1)
        return _rok_nebo_cislo(m, t)

    t = _RE_CAS.sub(_cas, text)
    t = _RE_KRAT.sub(_krat, t)
    t = _RE_TISICE.sub(_tis, t)
    t = _RE_DATUM_LOC.sub(_datum_loc, t)
    t = _RE_DATUM_GEN.sub(_datum_gen, t)
    t = _RE_MESIC_ROK.sub(lambda m: f"{m.group(1).lower()} {m.group(2)}", t)
    t = _RE_CISLO.sub(_cislo, t)
    return t


def _chran_eet_verze(text: str) -> tuple[str, list[str]]:
    """EET 2.0 zůstává jako značka verze, ne „dvě.nula“."""
    ulozeno: list[str] = []

    def _chr(m: re.Match[str]) -> str:
        ulozeno.append(m.group(0))
        return f"__EETVERZE{len(ulozeno) - 1}__"

    return _RE_EET_VERZE.sub(_chr, text), ulozeno


def _obnov_eet_verze(text: str, ulozeno: list[str]) -> str:
    for i, orig in enumerate(ulozeno):
        text = text.replace(f"__EETVERZE{i}__", orig)
    return text


def nahrad_cisla_v_textu(text: str) -> str:
    """Všechna čísla v textu přepíše do slovní podoby."""
    if not text or not re.search(r"\d", text):
        return text
    text, eet = _chran_eet_verze(text)
    text = _nahrad_zbyla_cisla(nahrad_hlasovani_v_textu(text))
    return _obnov_eet_verze(text, eet)
