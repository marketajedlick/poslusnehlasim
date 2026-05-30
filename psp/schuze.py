"""Analýza schůze Poslanecké sněmovny z lokálních UNL dat."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Iterator

from psp.unl import read_unl


@dataclass
class Vote:
    id_hlasovani: str
    id_organ: str
    schuze: int
    cislo: int
    bod: str
    datum: str
    cas: str
    pro: int
    proti: int
    zdrzel: int
    nehlasoval: int
    pritomno: int
    kvorum: int
    vysledek: str  # A / R
    nazev: str

    @property
    def je_porad_schuze(self) -> bool:
        return "pořad schůze" in self.nazev.lower()

    @property
    def vysledek_label(self) -> str:
        return "PŘIJATO" if self.vysledek == "A" else "ZAMÍTNUTO" if self.vysledek == "R" else self.vysledek

    @property
    def datetime_str(self) -> str:
        return f"{self.datum} {self.cas}"


@dataclass
class SchuzeMeta:
    id_schuze: str
    id_organ: str
    cislo: int
    zahajeni: str
    ukonceni: str


@dataclass
class TopicSummary:
    bod: str
    nazev: str
    posledni_hlasovani: Vote
    pocet_hlasovani: int
    prijato: int
    zamitnuto: int


@dataclass
class SchuzeReport:
    meta: SchuzeMeta | None
    obdobi: int
    cislo_schuze: int
    hlasovani: list[Vote] = field(default_factory=list)
    temata: list[TopicSummary] = field(default_factory=list)
    porad_stats: dict[str, int] = field(default_factory=dict)
    dny: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "obdobi": self.obdobi,
            "schuze": self.cislo_schuze,
            "meta": {
                "id_schuze": self.meta.id_schuze if self.meta else None,
                "zahajeni": self.meta.zahajeni if self.meta else None,
                "ukonceni": self.meta.ukonceni if self.meta else None,
            },
            "statistiky": {
                "celkem_hlasovani": len(self.hlasovani),
                "porad_schuze": self.porad_stats,
                "dny": self.dny,
            },
            "temata": [
                {
                    "bod": t.bod,
                    "nazev": t.nazev,
                    "pocet_hlasovani": t.pocet_hlasovani,
                    "prijato": t.prijato,
                    "zamitnuto": t.zamitnuto,
                    "vysledek": t.posledni_hlasovani.vysledek_label,
                    "posledni_hlasovani": {
                        "datum": t.posledni_hlasovani.datum,
                        "cas": t.posledni_hlasovani.cas,
                        "pro": t.posledni_hlasovani.pro,
                        "proti": t.posledni_hlasovani.proti,
                        "pritomno": t.posledni_hlasovani.pritomno,
                    },
                }
                for t in self.temata
            ],
            "hlasovani": [
                {
                    "cislo": v.cislo,
                    "bod": v.bod,
                    "datum": v.datum,
                    "cas": v.cas,
                    "nazev": v.nazev,
                    "pro": v.pro,
                    "proti": v.proti,
                    "zdrzel": v.zdrzel,
                    "nehlasoval": v.nehlasoval,
                    "pritomno": v.pritomno,
                    "vysledek": v.vysledek,
                }
                for v in self.hlasovani
            ],
        }


class SchuzeAnalyzer:
    """
    Analyzuje schůzi z UNL exportů PSP.

    Hlasování: hl-{obdobi}ps/hl{obdobi}s.unl
    Schůze:    schuze/schuze.unl
    Poslanci:  poslanci/poslanec.unl + poslanci/osoby.unl
    Steno:     steno/rec.unl (počty projevů)
    """

    def __init__(self, data_dir: Path, id_organ: str = "174"):
        self.data_dir = Path(data_dir)
        self.id_organ = id_organ

    def _hl_soubor(self, obdobi: int) -> Path:
        return self.data_dir / f"hl-{obdobi}ps" / f"hl{obdobi}s.unl"

    def load_schuze_meta(self, cislo_schuze: int) -> SchuzeMeta | None:
        path = self.data_dir / "schuze" / "schuze.unl"
        if not path.exists():
            return None
        candidates: list[SchuzeMeta] = []
        for row in read_unl(path):
            if len(row) < 6:
                continue
            if row[1] != self.id_organ or row[2] != str(cislo_schuze):
                continue
            if "1" in row[6:]:
                continue
            zahajeni = row[3]
            ukonceni = row[4] if row[4] else (row[5] if len(row) > 5 else "")
            if not ukonceni:
                continue
            candidates.append(
                SchuzeMeta(
                    id_schuze=row[0],
                    id_organ=row[1],
                    cislo=int(row[2]),
                    zahajeni=zahajeni,
                    ukonceni=ukonceni,
                )
            )
        if not candidates:
            return None
        return max(candidates, key=lambda m: m.ukonceni)

    def load_votes(self, obdobi: int, cislo_schuze: int) -> list[Vote]:
        path = self._hl_soubor(obdobi)
        if not path.exists():
            raise FileNotFoundError(f"Chybí soubor hlasování: {path}")

        votes: list[Vote] = []
        for row in read_unl(path):
            if len(row) < 15:
                continue
            if row[1] != self.id_organ or row[2] != str(cislo_schuze):
                continue
            nazev = row[15].replace("**", " ").strip() if len(row) > 15 else ""
            votes.append(
                Vote(
                    id_hlasovani=row[0],
                    id_organ=row[1],
                    schuze=int(row[2]),
                    cislo=int(row[3]),
                    bod=row[4],
                    datum=row[5],
                    cas=row[6],
                    pro=int(row[7]),
                    proti=int(row[8]),
                    zdrzel=int(row[9]),
                    nehlasoval=int(row[10]),
                    pritomno=int(row[11]),
                    kvorum=int(row[12]),
                    vysledek=row[14],
                    nazev=nazev,
                )
            )
        votes.sort(key=lambda v: (v.datum, v.cas, v.cislo))
        return votes

    def list_schuze_cisla(self, obdobi: int) -> list[int]:
        """Čísla schůzí, která mají hlasování v UNL souboru období."""
        path = self._hl_soubor(obdobi)
        if not path.exists():
            return []
        found: set[int] = set()
        for row in read_unl(path):
            if len(row) < 3 or row[1] != self.id_organ:
                continue
            try:
                found.add(int(row[2]))
            except ValueError:
                continue
        return sorted(found)

    def find_schuze_by_date(self, obdobi: int, day: date) -> list[int]:
        """Najde čísla schůzí, které probíhaly v daný den."""
        path = self.data_dir / "schuze" / "schuze.unl"
        day_str = day.strftime("%Y-%m-%d")
        found: set[int] = set()
        for row in read_unl(path):
            if len(row) < 6 or row[1] != self.id_organ:
                continue
            zahaj = row[3][:10]
            konec = row[4][:10] if row[4] else zahaj
            if zahaj <= day_str <= konec:
                found.add(int(row[2]))
        return sorted(found)

    def find_recent_schuze(self, obdobi: int, since: date) -> list[int]:
        """Schůze, jejichž konec (nebo začátek) je >= since."""
        path = self.data_dir / "schuze" / "schuze.unl"
        since_str = since.strftime("%Y-%m-%d")
        found: set[int] = set()
        for row in read_unl(path):
            if len(row) < 6 or row[1] != self.id_organ:
                continue
            konec = (row[4] or row[3])[:10]
            if konec >= since_str:
                found.add(int(row[2]))
        return sorted(found)

    @staticmethod
    def _summarize_topics(votes: list[Vote], skip_porad: bool = True) -> list[TopicSummary]:
        groups: dict[tuple[str, str], list[Vote]] = defaultdict(list)
        for v in votes:
            if skip_porad and v.je_porad_schuze:
                continue
            key = (v.bod, v.nazev or "(organizační)")
            groups[key].append(v)

        summaries: list[TopicSummary] = []
        for (bod, nazev), group in groups.items():
            group.sort(key=lambda x: (x.datum, x.cas, x.cislo))
            summaries.append(
                TopicSummary(
                    bod=bod,
                    nazev=nazev,
                    posledni_hlasovani=group[-1],
                    pocet_hlasovani=len(group),
                    prijato=sum(1 for g in group if g.vysledek == "A"),
                    zamitnuto=sum(1 for g in group if g.vysledek == "R"),
                )
            )
        summaries.sort(
            key=lambda t: (
                t.posledni_hlasovani.datum,
                t.posledni_hlasovani.cas,
            )
        )
        return summaries

    @staticmethod
    def _porad_stats(votes: list[Vote]) -> dict[str, int]:
        porad = [v for v in votes if v.je_porad_schuze]
        return {
            "celkem": len(porad),
            "prijato": sum(1 for v in porad if v.vysledek == "A"),
            "zamitnuto": sum(1 for v in porad if v.vysledek == "R"),
        }

    def analyze(self, obdobi: int, cislo_schuze: int) -> SchuzeReport:
        votes = self.load_votes(obdobi, cislo_schuze)
        meta = self.load_schuze_meta(cislo_schuze)
        dny = Counter(v.datum for v in votes)
        return SchuzeReport(
            meta=meta,
            obdobi=obdobi,
            cislo_schuze=cislo_schuze,
            hlasovani=votes,
            temata=self._summarize_topics(votes),
            porad_stats=self._porad_stats(votes),
            dny=dict(sorted(dny.items())),
        )

    def load_poslanec_jmena(self) -> dict[str, str]:
        """id_poslanec -> celé jméno."""
        osoby: dict[str, tuple[str, str, str]] = {}
        for row in read_unl(self.data_dir / "poslanci" / "osoby.unl"):
            if len(row) >= 4:
                osoby[row[0]] = (row[1], row[2], row[3])

        jmena: dict[str, str] = {}
        for row in read_unl(self.data_dir / "poslanci" / "poslanec.unl"):
            if len(row) < 2:
                continue
            pid, oid = row[0], row[1]
            if oid in osoby:
                titul, prijmeni, jmeno = osoby[oid]
                jmena[pid] = f"{titul} {jmeno} {prijmeni}".strip()
        return jmena

    def speaker_counts(self, obdobi: int, cislo_schuze: int) -> Counter[str]:
        """Počty projevů podle id_poslanec z rec.unl."""
        counts: Counter[str] = Counter()
        path = self.data_dir / "steno" / "rec.unl"
        if not path.exists():
            return counts
        for row in read_unl(path):
            if len(row) >= 4 and row[1] == self.id_organ and row[2] == str(cislo_schuze):
                counts[row[3]] += 1
        return counts

    def votes_for_topic(self, votes: list[Vote], keyword: str) -> list[Vote]:
        kw = keyword.lower()
        return [v for v in votes if kw in v.nazev.lower()]

    @staticmethod
    def parse_unl_date(s: str) -> date | None:
        """Parsuje '26.05.2026' nebo '2026-05-26 14'."""
        s = s.strip()
        for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(s[:10], fmt).date()
            except ValueError:
                continue
        return None
