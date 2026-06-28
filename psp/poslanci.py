"""Poslanci 10. volebního období a jejich poslanecké kluby (PSP open data)."""

from __future__ import annotations

import re
import time
import zipfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from psp.http import get_bytes

from svejk.config import PSP_DATA_DIR, ROOT

_UNL_ENCODING = "cp1250"


def _read_unl_bytes(raw: bytes):
    for line in raw.decode(_UNL_ENCODING, errors="replace").splitlines():
        yield line.split("|")

POSLANCI_ZIP_URL = "https://www.psp.cz/eknih/cdrom/opendata/poslanci.zip"
OBD_OBI_2025 = "174"  # PSP10 od 4. 10. 2025

_KLUB_LABEL = {
    "ANO2011": "ANO",
    "MS": "Motoristé",
    "STAN": "STAN",
    "SPD": "SPD",
    "Piráti": "Piráti",
    "ODS": "ODS",
    "KDU-ČSL": "KDU-ČSL",
    "TOP09": "TOP 09",
}

# Příjmení, která v textech bez křestního jména téměř vždy znamenají konkrétní osobu.
_DEFAULT_PRIJMENI = {
    "Okamura": "SPD",
    "Fiala": "ODS",
    "Vondráček": "ANO",
    "Kovářová": "Piráti",
}

# Zobrazení v textu, když klub ve Sněmovně neodpovídá volební straně poslance.
_KLUB_DISPLAY: dict[tuple[str, str], str] = {
    ("Gabriela", "Svárovská"): "Zelení, klub Pirátů",
}


@dataclass(frozen=True)
class Poslanec:
    jmeno: str
    prijmeni: str
    klub: str
    pohlavi: str


def _cache_zip_path(data_dir: Path) -> Path:
    return data_dir / "psp" / "poslanci.zip"


def _ensure_poslanci_zip(data_dir: Path) -> Path:
    path = _cache_zip_path(data_dir)
    if path.is_file():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    last_err: BaseException | None = None
    for attempt in range(3):
        try:
            path.write_bytes(get_bytes(POSLANCI_ZIP_URL, timeout=120))
            return path
        except OSError as e:
            last_err = e
            if attempt < 2:
                time.sleep(5 * (attempt + 1))
    raise OSError(
        f"Nepodařilo se stáhnout poslanci.zip z {POSLANCI_ZIP_URL}. "
        f"Umísti soubor ručně do {path}."
    ) from last_err


def _klub_label(zkr: str) -> str:
    return _KLUB_LABEL.get(zkr, zkr)


def _display_klub(p: Poslanec) -> str:
    return _KLUB_DISPLAY.get((p.jmeno, p.prijmeni), p.klub)


def load_poslanci(
    *,
    obdobi_id: str = OBD_OBI_2025,
    data_dir: Path | None = None,
) -> list[Poslanec]:
    """Načte aktivní poslance a jejich aktuální klub z poslanci.zip."""
    base = data_dir or PSP_DATA_DIR
    zip_path = _ensure_poslanci_zip(base)
    with zipfile.ZipFile(zip_path) as zf:
        organy: dict[str, dict[str, str]] = {}
        for row in _read_unl_bytes(zf.read("organy.unl")):
            if len(row) < 8:
                continue
            organy[row[0]] = {
                "id_typ": row[2],
                "zkr": row[3],
                "nazev": row[4],
                "od": row[6],
                "do": row[7],
            }

        osoby: dict[str, dict[str, str]] = {}
        for row in _read_unl_bytes(zf.read("osoby.unl")):
            if len(row) < 4:
                continue
            osoby[row[0]] = {
                "pred": row[1],
                "prijmeni": row[2],
                "jmeno": row[3],
                "pohlavi": row[6] if len(row) > 6 else "M",
            }

        klub_ids = {
            oid
            for oid, o in organy.items()
            if o["id_typ"] == "1" and not o["do"]
        }
        osoba_klub: dict[str, str] = {}
        for row in _read_unl_bytes(zf.read("zarazeni.unl")):
            if len(row) < 5:
                continue
            id_osoba, id_of, cl_funkce, do_o = row[0], row[1], row[2], row[4]
            if cl_funkce != "0" or do_o or id_of not in klub_ids:
                continue
            osoba_klub[id_osoba] = _klub_label(organy[id_of]["zkr"])

        out: list[Poslanec] = []
        for row in _read_unl_bytes(zf.read("poslanec.unl")):
            if len(row) < 5 or row[4] != obdobi_id:
                continue
            osoba = osoby.get(row[1])
            klub = osoba_klub.get(row[1])
            if not osoba or not klub:
                continue
            out.append(
                Poslanec(
                    jmeno=osoba["jmeno"].strip(),
                    prijmeni=osoba["prijmeni"].strip(),
                    klub=klub,
                    pohlavi=osoba["pohlavi"].strip() or "M",
                )
            )
    return out


def _prijmeni_tvary(prijmeni: str, pohlavi: str) -> set[str]:
    """Běžné tvary příjmení ve zpravodajském stylu (nominativ + pád)."""
    tvary = {prijmeni}
    if pohlavi == "F":
        if prijmeni.endswith("ová"):
            kmen = prijmeni[:-1]
            tvary.update(kmen + s for s in ("á", "é", "ou", "ým"))
        elif prijmeni.endswith("á"):
            kmen = prijmeni[:-1]
            tvary.add(kmen + "é")
        return tvary

    ek_ec = prijmeni.endswith(("ek", "ec")) and len(prijmeni) > 3
    ka = prijmeni.endswith("ka") and len(prijmeni) > 3
    if ek_ec:
        kmen = prijmeni[:-2]
        tvary.update(
            kmen + s
            for s in ("ka", "kovi", "kem", "kova", "kovo", "kův", "kovy", "kově")
        )
    elif ka:
        kmen = prijmeni[:-1]
        tvary.update(
            kmen + s
            for s in ("y", "ou", "ovi", "em", "ova", "ovo", "ův", "ovy", "ově", "ových")
        )
    else:
        if prijmeni.endswith(("š", "ř", "č", "ž", "c", "j")):
            tvary.add(prijmeni + "e")
        if prijmeni.endswith("k"):
            tvary.add(prijmeni + "a")
        elif prijmeni.endswith(("h", "r", "n")):
            tvary.add(prijmeni + "a")
        if prijmeni.endswith("a"):
            kmen = prijmeni[:-1]
            tvary.add(kmen + "y")
            tvary.add(kmen + "ovi")
            tvary.update(kmen + s for s in ("ova", "ovy", "ovu"))
        else:
            tvary.add(prijmeni + "ovi")
            tvary.update(prijmeni + s for s in ("ova", "ovy", "ově", "ův"))
    return tvary


@dataclass
class _MatchRule:
    pattern: re.Pattern[str]
    klub: str


class PoslanecRegistry:
    """Mapování jmen poslanců na strany pro post-processing textů."""

    def __init__(self, poslanci: list[Poslanec]):
        self._rules = self._build_rules(poslanci)

    @classmethod
    def from_psp(cls, *, data_dir: Path | None = None) -> PoslanecRegistry:
        return cls(load_poslanci(data_dir=data_dir))

    def _build_rules(self, poslanci: list[Poslanec]) -> list[_MatchRule]:
        by_prijmeni: dict[str, list[Poslanec]] = {}
        for p in poslanci:
            by_prijmeni.setdefault(p.prijmeni, []).append(p)

        rules: list[tuple[int, _MatchRule]] = []

        for prijmeni, group in by_prijmeni.items():
            if len(group) == 1:
                p = group[0]
                for tvar in _prijmeni_tvary(p.prijmeni, p.pohlavi):
                    rules.append(
                        (
                            len(tvar),
                            _MatchRule(
                                self._surname_pattern(tvar, block_jmeno=p.jmeno),
                                _display_klub(p),
                            ),
                        )
                    )
                rules.append(
                    (
                        len(p.jmeno) + len(p.prijmeni) + 1,
                        _MatchRule(
                            self._full_name_pattern(p.jmeno, p.prijmeni, p.pohlavi),
                            _display_klub(p),
                        ),
                    )
                )
                continue

            for p in group:
                rules.append(
                    (
                        len(p.jmeno) + len(p.prijmeni) + 1,
                        _MatchRule(
                            self._full_name_pattern(p.jmeno, p.prijmeni, p.pohlavi),
                            _display_klub(p),
                        ),
                    )
                )
            default = _DEFAULT_PRIJMENI.get(prijmeni)
            if default:
                p0 = next((x for x in group if x.klub == default), group[0])
                for tvar in _prijmeni_tvary(p0.prijmeni, p0.pohlavi):
                    rules.append(
                        (
                            len(tvar),
                            _MatchRule(
                                self._surname_pattern(tvar, block_jmeno=p0.jmeno),
                                _display_klub(p0),
                            ),
                        )
                    )

        rules.sort(key=lambda x: (-x[0], x[1].pattern.pattern))
        return [r for _, r in rules]

    @staticmethod
    def _word(part: str) -> str:
        return re.escape(part)

    def _surname_pattern(self, tvar: str, *, block_jmeno: str = "") -> re.Pattern[str]:
        body = self._word(tvar)
        skip_first = ""
        if block_jmeno:
            skip_first = rf"(?!\s+{self._word(block_jmeno)})"
        return re.compile(
            rf"(?<![\w/]){body}{skip_first}(?!\s*\()(?![\w/])",
            re.UNICODE,
        )

    def _full_name_pattern(
        self, jmeno: str, prijmeni: str, pohlavi: str
    ) -> re.Pattern[str]:
        jmeno_pat = self._word(jmeno)
        prijmeni_pat = "|".join(
            self._word(t) for t in sorted(_prijmeni_tvary(prijmeni, pohlavi), key=len, reverse=True)
        )
        return re.compile(
            rf"(?<![\w/]){jmeno_pat}\s+({prijmeni_pat})(?!\s*\()(?![\w/])",
            re.UNICODE,
        )

    def annotate(self, text: str) -> str:
        if not text or not self._rules:
            return text

        matches: list[tuple[int, int, str, str]] = []
        for rule in self._rules:
            for m in rule.pattern.finditer(text):
                matches.append((m.start(), m.end(), m.group(0), rule.klub))

        if not matches:
            return text

        matches.sort(key=lambda x: (-(x[1] - x[0]), x[0]))
        used: list[tuple[int, int]] = []
        selected: list[tuple[int, int, str, str]] = []
        for start, end, label, klub in matches:
            if any(not (end <= s or start >= e) for s, e in used):
                continue
            used.append((start, end))
            selected.append((start, end, label, klub))

        out = text
        for start, end, label, klub in sorted(selected, key=lambda x: x[0], reverse=True):
            out = out[:start] + f"{label} ({klub})" + out[end:]
        return out


@lru_cache(maxsize=1)
def poslanec_registry() -> PoslanecRegistry:
    return PoslanecRegistry.from_psp(data_dir=ROOT / "data")
