"""Generování JSON tabulek hlasování (kluby pro/proti) z open dat PSP."""

from __future__ import annotations

import io
import json
import urllib.request
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from psp.poslanci import OBD_OBI_2025

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

_KLUB_ORDER = (
    "ANO",
    "ODS",
    "STAN",
    "Piráti",
    "KDU-ČSL",
    "TOP 09",
    "SPD",
    "Motoristé",
)


def fetch_psp_hl_zip(obdobi: int) -> zipfile.ZipFile:
    url = f"https://www.psp.cz/eknih/cdrom/opendata/hl-{obdobi}ps.zip"
    raw = urllib.request.urlopen(url, timeout=120).read()
    return zipfile.ZipFile(io.BytesIO(raw))


def _poslanec_kluby(poslanci_zip: Path, obdobi_id: str = OBD_OBI_2025) -> dict[str, str]:
    with zipfile.ZipFile(poslanci_zip) as pz:
        organy = {
            r[0]: {"id_typ": r[2], "zkr": r[3], "do": r[7]}
            for r in (
                line.split("|")
                for line in pz.read("organy.unl").decode("cp1250", errors="replace").splitlines()
            )
            if len(r) >= 8
        }
        klub_ids = {oid for oid, o in organy.items() if o["id_typ"] == "1" and not o["do"]}
        osoba_klub: dict[str, str] = {}
        for r in (
            line.split("|")
            for line in pz.read("zarazeni.unl").decode("cp1250", errors="replace").splitlines()
        ):
            if len(r) >= 5 and r[2] == "0" and not r[4] and r[1] in klub_ids:
                osoba_klub[r[0]] = r[1]
        id_klub: dict[str, str] = {}
        for r in (
            line.split("|")
            for line in pz.read("poslanec.unl").decode("cp1250", errors="replace").splitlines()
        ):
            if len(r) >= 5 and r[4] == obdobi_id:
                kid = osoba_klub.get(r[1])
                if kid:
                    zkr = organy[kid]["zkr"]
                    id_klub[r[0]] = _KLUB_LABEL.get(zkr, zkr)
        return id_klub


def _sort_kluby_list(
    kluby: list[dict[str, Any]], count_key: str
) -> list[dict[str, Any]]:
    return sorted(
        kluby,
        key=lambda k: (
            _KLUB_ORDER.index(k["klub"])
            if k.get("klub") in _KLUB_ORDER
            else len(_KLUB_ORDER),
            -int(k.get(count_key) or 0),
        ),
    )


def _breakdown(
    cislo: int,
    *,
    votes_by_cislo: dict[int, dict[str, Any]],
    mp_votes: dict[str, list[tuple[str, str]]],
    id_klub: dict[str, str],
) -> tuple[list[dict[str, int]], list[dict[str, int]]]:
    vote_id = votes_by_cislo[cislo]["id"]
    by_klub: dict[str, Counter[str]] = defaultdict(Counter)
    for id_pos, res in mp_votes[vote_id]:
        by_klub[id_klub.get(id_pos, "?")][res] += 1
    kluby_pro = [
        {"klub": k, "pro": c.get("A", 0)}
        for k, c in by_klub.items()
        if c.get("A", 0)
    ]
    kluby_proti = [
        {"klub": k, "proti": c.get("N", 0) + c.get("B", 0)}
        for k, c in by_klub.items()
        if c.get("N", 0) + c.get("B", 0)
    ]
    return (
        _sort_kluby_list(kluby_pro, "pro"),
        _sort_kluby_list(kluby_proti, "proti"),
    )


def build_radky(
    *,
    psp_obdobi: int,
    obdobi_id: str,
    schuze: int,
    kandidati: list[tuple[str, int]],
    poslanci_zip: Path,
    hl_zip: zipfile.ZipFile | None = None,
) -> list[dict[str, Any]]:
    """kandidati: (jméno, číslo hlasování ve schůzi)."""
    if hl_zip is None:
        hl_zip = fetch_psp_hl_zip(psp_obdobi)

    votes_by_cislo: dict[int, dict[str, Any]] = {}
    for line in hl_zip.read(f"hl{psp_obdobi}s.unl").decode("cp1250", errors="replace").splitlines():
        row = line.split("|")
        if len(row) < 15 or row[1] != obdobi_id or row[2] != str(schuze):
            continue
        votes_by_cislo[int(row[3])] = {
            "id": row[0],
            "pro": int(row[7]),
            "proti": int(row[8]),
            "vysledek": row[14],
        }

    mp_votes: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for line in hl_zip.read(f"hl{psp_obdobi}h1.unl").decode("cp1250", errors="replace").splitlines():
        row = line.split("|")
        if len(row) >= 3:
            mp_votes[row[1]].append((row[0], row[2]))

    id_klub = _poslanec_kluby(poslanci_zip, obdobi_id)

    radky: list[dict[str, Any]] = []
    for jmeno, cislo in kandidati:
        v = votes_by_cislo.get(cislo)
        if not v:
            raise ValueError(f"Chybí hlasování č. {cislo} pro {jmeno}")
        kluby_pro, kluby_proti = _breakdown(
            cislo,
            votes_by_cislo=votes_by_cislo,
            mp_votes=mp_votes,
            id_klub=id_klub,
        )
        radky.append(
            {
                "jmeno": jmeno,
                "cislo_hlasovani": cislo,
                "pro": v["pro"],
                "proti": v["proti"],
                "kluby_pro": kluby_pro,
                "kluby_proti": kluby_proti,
            }
        )
    return radky


def write_volba_zvoleni_json(
    paths_facts: Path,
    *,
    datum_unl: str,
    psp_obdobi: int,
    obdobi: int,
    obdobi_id: str,
    schuze: int,
    kandidati: list[tuple[str, int]],
    poslanci_zip: Path,
) -> Path:
    from datetime import datetime

    d = datetime.strptime(datum_unl, "%d.%m.%Y")
    radky = build_radky(
        psp_obdobi=psp_obdobi,
        obdobi_id=obdobi_id,
        schuze=schuze,
        kandidati=kandidati,
        poslanci_zip=poslanci_zip,
    )
    payload = {
        "datum": datum_unl,
        "obdobi": obdobi,
        "schuze": schuze,
        "pocet": len(radky),
        "radky": radky,
    }
    out = paths_facts / f"hlasovani-zvoleni-{d.strftime('%Y-%m-%d')}.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out
