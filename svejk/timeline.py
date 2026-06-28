"""Casova osa schuze, pravidlova vrstva ve stylu Svejka z hlasovacich dat."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
import re

from psp.schuze import SchuzeAnalyzer, Vote


@dataclass
class TemaSvejka:
    svejk: str
    vysvetleni: str


@dataclass
class BlokDne:
    cas_od: str
    cas_do: str
    typ: str  # start | debate | porad | law | end
    svejk: str
    vysvetleni: str = ""
    nazev: str = ""
    pocet_hlasovani: int = 0
    pocet_prijato: int = 0
    pocet_zamitnuto: int = 0
    proslo: bool = False


@dataclass
class DenSchuze:
    datum: str
    den: str
    bloky: list[BlokDne] = field(default_factory=list)
    shrnuti: str = ""


@dataclass
class SchuzeCasovaOsa:
    cislo: int
    obdobi: int
    dny: list[DenSchuze] = field(default_factory=list)
    shrnuti: str = ""


def normalize_day(day: str | date, *, default_year: int | None = None) -> str:
    if isinstance(day, date):
        return day.strftime("%d.%m.%Y")
    text = day.strip().rstrip(".")
    if "-" in text and len(text) >= 10:
        return datetime.strptime(text[:10], "%Y-%m-%d").strftime("%d.%m.%Y")
    m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})(?:\.(\d{2,4}))?", text)
    if m:
        d, mo = int(m.group(1)), int(m.group(2))
        if mo > 12 and d <= 12:
            d, mo = mo, d
        raw_y = m.group(3)
        if raw_y:
            year = int(raw_y)
            if year < 100:
                year += 2000
        elif default_year is not None:
            year = default_year
        else:
            year = date.today().year
        return date(year, mo, d).strftime("%d.%m.%Y")
    return datetime.strptime(text, "%d.%m.%Y").strftime("%d.%m.%Y")


def _parse_partial_den(text: str) -> tuple[int, int] | None:
    m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})(?:\.(\d{2,4}))?", text.strip().rstrip("."))
    if not m or m.group(3):
        return None
    d, mo = int(m.group(1)), int(m.group(2))
    if mo > 12 and d <= 12:
        d, mo = mo, d
    if not (1 <= mo <= 12 and 1 <= d <= 31):
        return None
    return d, mo


def _years_for_den_v_schuze(paths, d: int, mo: int) -> list[int]:
    years: list[int] = []
    if paths.facts_by_day.is_dir():
        for fp in paths.facts_by_day.glob("*.json"):
            try:
                y, m, day = (int(x) for x in fp.stem.split("-"))
            except ValueError:
                continue
            if m == mo and day == d:
                years.append(y)
    if not years and paths.votes_jsonl.is_file():
        from svejk.build.io import iter_jsonl

        for v in iter_jsonl(paths.votes_jsonl):
            datum = (v.get("datum") or "").strip()
            if not datum:
                continue
            try:
                parsed = datetime.strptime(datum, "%d.%m.%Y")
            except ValueError:
                continue
            if parsed.month == mo and parsed.day == d:
                years.append(parsed.year)
    return years


def resolve_schuze_den(paths, den: str) -> tuple[str, Path]:
    """Datum bez roku doplní z dat schůze (ne z dnešního kalendáře)."""
    partial = _parse_partial_den(den)
    if partial is None:
        d_unl = normalize_day(den)
        d = datetime.strptime(d_unl, "%d.%m.%Y")
        return d_unl, paths.facts_by_day / f"{d.strftime('%Y-%m-%d')}.json"

    d, mo = partial
    years = _years_for_den_v_schuze(paths, d, mo)
    if not years:
        for year in (paths.obdobi, paths.obdobi + 1):
            path = paths.facts_by_day / f"{year}-{mo:02d}-{d:02d}.json"
            if path.is_file():
                return date(year, mo, d).strftime("%d.%m.%Y"), path
        year = paths.obdobi
    else:
        from collections import Counter

        year = Counter(years).most_common(1)[0][0]

    d_unl = date(year, mo, d).strftime("%d.%m.%Y")
    return d_unl, paths.facts_by_day / f"{year}-{mo:02d}-{d:02d}.json"


def den_v_tydnu(datum_unl: str) -> str:
    d = datetime.strptime(datum_unl, "%d.%m.%Y")
    return ["pondělí", "úterý", "středa", "čtvrtek", "pátek", "sobota", "neděle"][d.weekday()]


def tema_z_nazvu(nazev: str) -> TemaSvejka:
    from svejk.obcansky import tema_z_nazvu as _tema_z_nazvu

    svejk, vysvetleni = _tema_z_nazvu(nazev)
    return TemaSvejka(svejk=svejk, vysvetleni=vysvetleni)


def _parse_time(cas: str) -> datetime:
    return datetime.strptime(cas, "%H:%M")


def _cas_minuty(cas: str) -> int:
    h, m = int(cas[:2]), int(cas[3:5])
    return h * 60 + m


def _serad_bloky(bloky: list[BlokDne]) -> list[BlokDne]:
    """Start a konec na miste, prostredni bloky chronologicky."""
    if len(bloky) <= 2:
        return bloky
    poradi = {"debate": 0, "porad": 1, "law": 2}
    start, end = bloky[0], bloky[-1]
    stred = sorted(
        bloky[1:-1],
        key=lambda b: (_cas_minuty(b.cas_od), poradi.get(b.typ, 5)),
    )
    return [start, *stred, end]


def _minutes_between(cas1: str, cas2: str) -> int:
    return int((_parse_time(cas2) - _parse_time(cas1)).total_seconds() / 60)


def _promluvy_minuty(day_votes: list[Vote]) -> int:
    """Součet mezer mezi hlasováními >= 30 min, odhad času promluv."""
    if len(day_votes) < 2:
        return 0
    return sum(
        gap
        for v1, v2 in zip(day_votes, day_votes[1:])
        if (gap := _minutes_between(v1.cas, v2.cas)) >= 30
    )


def _format_promluvy(minutes: int) -> str:
    if minutes < 30:
        return ""
    hod = minutes // 60
    if hod == 0:
        return f"{minutes} minut promluv, "
    if hod == 1:
        return "hodinu promluv, "
    if 2 <= hod <= 4:
        return f"{hod} hodiny promluv, "
    return f"{hod} hodin promluv, "


def _debate_temata(day_votes: list[Vote]) -> str:
    checks = [
        ("babiš", "Babiše"),
        ("babis", "Babiše"),
        ("dozimetr", "Dozimetr"),
        ("dotac", "dotace"),
        ("interpelac", "interpelace"),
        ("stavebn", "stavební zákon"),
        ("penzijn", "penze"),
    ]
    seen: set[str] = set()
    found: list[str] = []
    for v in day_votes:
        lower = v.nazev.lower()
        for kw, label in checks:
            if kw in lower and label not in seen:
                seen.add(label)
                found.append(label)
    if found:
        return f"Opozice chtěla {', '.join(found)}. Koalice jinak. "
    return ""


def _porad_svejk(prijato: int, zamitnuto: int, celkem: int) -> tuple[str, str]:
    if celkem == 0:
        return "", ""
    if celkem <= 8:
        return (
            f"Pořad schůze? {zamitnuto}× ne, {prijato}× jo.",
            "Krátká ranní hádka o tom, co se bude projednávat.",
        )
    if zamitnuto > prijato * 3:
        return (
            f"Skoro hodinu mlátili do stolu o pořadu. {celkem} hlasování, {zamitnuto}× ne.",
            "Opozice opakovaně blokovala program. U nás v kasárnách se o tom, kdo smete dvůr, "
            "rozhodlo rychleji.",
        )
    if prijato > zamitnuto:
        return (
            f"Pořad schůze prošel ({prijato}× jo, {zamitnuto}× ne).",
            "Poslanci se shodli, co se bude projednávat.",
        )
    return (
        f"Pořad schůze, {celkem} hlasování, {zamitnuto}× zamítnuto.",
        "Hádali se, co patří na program dne.",
    )


def _shrnuti_dne(
    pocet_proslo: int,
    pocet_zakonu: int,
    pocet_porad: int,
    pocet_hlasovani: int,
    promluvy_min: int = 0,
) -> str:
    promluvy = _format_promluvy(promluvy_min)
    if pocet_porad > pocet_hlasovani // 2:
        if pocet_proslo:
            return (
                f"Ve zkratce: {promluvy}"
                f"hodinu o pořadu, pak {pocet_proslo} věcí schváleno a domů. "
                f"Tomu se skoro nechce věřit."
            )
        return (
            f"Ve zkratce: {promluvy}celý den se hádali o pořad a moc toho neprojednali. "
            f"Opozice blokovala. Samozřejmě."
        )
    if pocet_proslo:
        return f"Ve zkratce: {promluvy}{pocet_proslo} věcí prošlo, poslanci šli domů."
    if pocet_zakonu:
        return f"Ve zkratce: {promluvy}{pocet_zakonu} věc projednána, nic neprošlo."
    return f"Ve zkratce: {promluvy}mluvili, hlasovali o proceduře, víc toho nebylo."


def build_den(votes: list[Vote], datum_unl: str) -> DenSchuze:
    day_votes = [v for v in votes if v.datum == datum_unl]
    if not day_votes:
        return DenSchuze(datum=datum_unl, den=den_v_tydnu(datum_unl))

    bloky: list[BlokDne] = []
    porad = [v for v in day_votes if v.je_porad_schuze]
    non_porad = [v for v in day_votes if not v.je_porad_schuze]
    hint = _debate_temata(day_votes)

    start = day_votes[0]
    bloky.append(
        BlokDne(
            cas_od=start.cas[:5],
            cas_do="",
            typ="start",
            svejk="Poslušně hlásím, schůze začala. Krátce se hlasovalo, program definitivně schválen.",
            vysvetleni="Schůze zahájena, organizační hlasování.",
        )
    )

    gap_found = False
    for i in range(len(day_votes) - 1):
        v1, v2 = day_votes[i], day_votes[i + 1]
        gap_min = _minutes_between(v1.cas, v2.cas)
        if gap_min >= 90:
            hod = max(1, gap_min // 60)
            vysv = "Poslanci debatovali, k hlasování se dlouho nedostali."
            if v2.nazev.strip():
                short = v2.nazev.strip()
                if len(short) > 80:
                    short = short[:77] + "…"
                vysv = f"Debatovali, než přišlo hlasování o: {short}."
            bloky.append(
                BlokDne(
                    cas_od=v1.cas[:5],
                    cas_do=v2.cas[:5],
                    typ="debate",
                    svejk=(
                        f"{hod} hodin seděli a nula hlasování. "
                        f"{hint}"
                        "Čistá konsternace, celý den dohadů a pořád nic."
                    ),
                    vysvetleni=vysv,
                )
            )
            gap_found = True
            break

    if not gap_found and len(non_porad) <= 2 and len(porad) > 10:
        bloky.append(
            BlokDne(
                cas_od=start.cas[:5],
                cas_do=porad[0].cas[:5],
                typ="debate",
                svejk=(
                    "Odpoledne mluvili, večer teprve hlasovali. "
                    "Typická sněmovní úspora času."
                ),
                vysvetleni="Většinu dne proběhla debata, hlasování až večer.",
            )
        )

    if porad:
        stats = {
            "celkem": len(porad),
            "prijato": sum(1 for v in porad if v.vysledek == "A"),
            "zamitnuto": sum(1 for v in porad if v.vysledek == "R"),
        }
        svejk, vysv = _porad_svejk(**stats)
        if svejk:
            cas_do = ""
            if len(porad) > 1 and porad[0].cas[:5] != porad[-1].cas[:5]:
                cas_do = porad[-1].cas[:5]
            bloky.append(
                BlokDne(
                    cas_od=porad[0].cas[:5],
                    cas_do=cas_do,
                    typ="porad",
                    svejk=svejk,
                    vysvetleni=vysv,
                    pocet_hlasovani=len(porad),
                    pocet_prijato=stats["prijato"],
                    pocet_zamitnuto=stats["zamitnuto"],
                    proslo=stats["prijato"] > stats["zamitnuto"],
                )
            )

    seen: dict[tuple[str, str], Vote] = {}
    posledni: dict[tuple[str, str], Vote] = {}
    pocty: dict[tuple[str, str], list[Vote]] = {}
    for v in day_votes:
        if v.je_porad_schuze:
            continue
        key = (v.bod, v.nazev or "(organizační)")
        if key not in seen:
            seen[key] = v
        posledni[key] = v
        pocty.setdefault(key, []).append(v)

    for v in sorted(seen.values(), key=lambda x: (x.cas, x.cislo)):
        if not v.nazev.strip():
            continue
        key = (v.bod, v.nazev or "(organizační)")
        last_v = posledni[key]
        group = pocty[key]
        prijato = sum(1 for x in group if x.vysledek == "A")
        zamitnuto = sum(1 for x in group if x.vysledek == "R")
        cas_do = ""
        if last_v.cas[:5] != v.cas[:5]:
            cas_do = last_v.cas[:5]
        tema = tema_z_nazvu(v.nazev)
        proslo = last_v.vysledek == "A"
        svejk = tema.svejk
        if not proslo:
            svejk = f"{tema.svejk} Tentokrát ne, poslanci to smetli ze stolu."
        elif len(group) > 1 and zamitnuto:
            svejk = f"{tema.svejk} Po {len(group)}× hlasování nakonec prošlo."
        bloky.append(
            BlokDne(
                cas_od=v.cas[:5],
                cas_do=cas_do,
                typ="law",
                svejk=svejk,
                vysvetleni=tema.vysvetleni,
                nazev=v.nazev,
                pocet_hlasovani=len(group),
                pocet_prijato=prijato,
                pocet_zamitnuto=zamitnuto,
                proslo=proslo,
            )
        )

    last = day_votes[-1]
    max_p = max(v.pritomno for v in day_votes)
    min_p = min(v.pritomno for v in day_votes if v.pritomno > 0)
    odchod = ""
    if max_p - min_p >= 30:
        odchod = " Polovina poslanců už dávno chyběla jak kadeti po večerce."
    bloky.append(
        BlokDne(
            cas_od=last.cas[:5],
            cas_do="",
            typ="end",
            svejk=f"Poslušně hlásím, šli domů.{odchod}",
            vysvetleni="",
        )
    )

    bloky = _serad_bloky(bloky)

    pocet_zakonu = sum(1 for b in bloky if b.typ == "law")
    pocet_proslo = sum(1 for b in bloky if b.typ == "law" and b.proslo)
    promluvy_min = _promluvy_minuty(day_votes)
    shrnuti = _shrnuti_dne(pocet_proslo, pocet_zakonu, len(porad), len(day_votes), promluvy_min)

    return DenSchuze(
        datum=datum_unl,
        den=den_v_tydnu(datum_unl),
        bloky=bloky,
        shrnuti=shrnuti,
    )


def render_den(day: DenSchuze) -> str:
    lines = [f"## {day.den.capitalize()} ({day.datum})", ""]
    for b in day.bloky:
        cas = f"{b.cas_od}-{b.cas_do}" if b.cas_do else b.cas_od + ("+" if b.typ == "end" else "")
        lines.append(f"{cas}, {b.svejk}")
        if b.vysvetleni:
            lines.append(f"({b.vysvetleni})")
        lines.append("")
    if day.shrnuti:
        lines.append(f"---\n\n{day.shrnuti}")
    return "\n".join(lines)


def render_cela_schuze(osa: SchuzeCasovaOsa) -> str:
    parts = [f"# Schůze {osa.cislo}/{osa.obdobi}, Švejk glosuje", ""]
    for day in osa.dny:
        parts.append(render_den(day))
        parts.append("")
    if osa.shrnuti:
        parts.append(osa.shrnuti)
    return "\n".join(parts)


def render_fakticke_dny(
    dny: list[DenSchuze],
    analyzer: SchuzeAnalyzer,
    obdobi: int,
    cislo: int,
) -> str:
    votes = analyzer.load_votes(obdobi, cislo)
    lines: list[str] = []
    for day in dny:
        day_votes = [v for v in votes if v.datum == day.datum]
        lines.append(f"{day.den.capitalize()} {day.datum}:")
        for v in day_votes:
            if v.je_porad_schuze or not v.nazev.strip():
                continue
            lines.append(
                f"  {v.cas[:5]}, {v.nazev[:120]}, {v.vysledek_label} ({v.pro}:{v.proti})"
            )
        porad = [v for v in day_votes if v.je_porad_schuze]
        if porad:
            p = sum(1 for x in porad if x.vysledek == "A")
            r = sum(1 for x in porad if x.vysledek == "R")
            lines.append(f"  Pořad schůze: {len(porad)} hlasování ({p}× přijato, {r}× zamítnuto).")
        lines.append("")
    return "\n".join(lines)


def den_to_dict(day: DenSchuze) -> dict:
    return {
        "datum": day.datum,
        "den": day.den,
        "bloky": [
            {
                "cas_od": b.cas_od,
                "cas_do": b.cas_do,
                "typ": b.typ,
                "svejk": b.svejk,
                "vysvetleni": b.vysvetleni,
                "nazev": b.nazev,
                "pocet_hlasovani": b.pocet_hlasovani,
                "pocet_prijato": b.pocet_prijato,
                "pocet_zamitnuto": b.pocet_zamitnuto,
                "proslo": b.proslo,
            }
            for b in day.bloky
        ],
        "shrnuti": day.shrnuti,
    }


class SvejkTimelineGenerator:
    def __init__(self, data_dir=None, organ_id: str = "174"):
        self.analyzer = SchuzeAnalyzer(data_dir, organ_id)

    def for_schuze(self, obdobi: int, cislo_schuze: int) -> SchuzeCasovaOsa:
        votes = self.analyzer.load_votes(obdobi, cislo_schuze)
        dny = [build_den(votes, d) for d in sorted({v.datum for v in votes})]
        shrnuti = " ".join(d.shrnuti for d in dny if d.shrnuti)
        return SchuzeCasovaOsa(cislo=cislo_schuze, obdobi=obdobi, dny=dny, shrnuti=shrnuti)
