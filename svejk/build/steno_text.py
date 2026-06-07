"""Úryvky a věty ze stenoprotokolu, celé věty, ne useknuté regex okno."""

from __future__ import annotations

import re
from typing import Any

PREDSED_MAX_SLOV = 80
ZAHÁJENÍ_MAX_SLOV = 550

FORMALNI_POZDRAV_RE = re.compile(
    r"^(vážen[ée]\s+(paní|páni)\s+posl|dobrý\s+(den|večer),?\s+vážen)",
    re.I,
)
PROCEDURA_RE = re.compile(
    r"§\s*\d|jednacího\s+řádu|identifikačními\s+kartami|ověřovatel|"
    r"přihlásili\s+identifikační|odhlásím\s+a\s+prosím|konstatuji,\s+že\s+jsme",
    re.I,
)
SCENIC_RE = re.compile(r"\(([^)]{4,})\)")
STRUCNY_RE = re.compile(r"budu\s+stručn", re.I)
NEAUTORIZOVANO_RE = re.compile(r"neautorizováno", re.I)
SCENIC_SKIP = frozenset({"nesrozumitelné", "nejasné", "smích"})


def text_je_neautorizovany(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return True
    if NEAUTORIZOVANO_RE.search(t) and len(t.split()) < 30:
        return True
    return False


def scenic_poznamky(text: str) -> list[str]:
    out: list[str] = []
    for raw in SCENIC_RE.findall(text or ""):
        s = raw.strip()
        if len(s) < 4 or s.lower() in SCENIC_SKIP:
            continue
        out.append(s)
    return out


def rozdelit_vety_steno(text: str) -> list[str]:
    if not text or text.strip().lower() == "neautorizováno!":
        return []
    t = re.sub(r"\s+", " ", text.strip())
    parts = re.split(r"(?<=[.!?])\s+", t)
    return [p.strip() for p in parts if len(p.strip()) >= 25]


def veta_je_hluk(veta: str) -> bool:
    if FORMALNI_POZDRAV_RE.search(veta):
        return True
    if PROCEDURA_RE.search(veta) and not re.search(r"\d{1,3}\s*%|\d+\s*mili", veta, re.I):
        return True
    low = veta.lower()
    if low.startswith("nyní přistoupíme") or low.startswith("já tedy zahajuji hlasování"):
        return True
    return False


def _podil_procedury(text: str) -> float:
    vety = rozdelit_vety_steno(text)
    if not vety:
        return 1.0
    proc = sum(1 for v in vety if veta_je_hluk(v))
    return proc / len(vety)


def detekuj_predsedajici(steno_records: list[dict[str, Any]]) -> set[str]:
    short: dict[str, int] = {}
    total: dict[str, int] = {}
    for rec in steno_records:
        jmeno = (rec.get("cele_jmeno") or "").strip()
        if not jmeno:
            continue
        total[jmeno] = total.get(jmeno, 0) + 1
        if int(rec.get("pocet_slov") or 0) <= PREDSED_MAX_SLOV:
            short[jmeno] = short.get(jmeno, 0) + 1
    out: set[str] = set()
    for jmeno, cnt in short.items():
        if cnt >= 2 and cnt / total[jmeno] >= 0.25:
            out.add(jmeno)
    return out


def je_organizacni_vstup(
    rec: dict[str, Any],
    *,
    predsed_jmena: set[str] | None = None,
) -> bool:
    text = rec.get("text") or ""
    if text_je_neautorizovany(text):
        return True

    pocet = int(rec.get("pocet_slov") or 0)
    jmeno = (rec.get("cele_jmeno") or "").strip()
    tema = (rec.get("tema") or "").lower()
    scenic = scenic_poznamky(text)

    if predsed_jmena and jmeno in predsed_jmena and pocet <= PREDSED_MAX_SLOV and not scenic:
        return True

    if "zahájení" in tema and pocet < ZAHÁJENÍ_MAX_SLOV:
        if not scenic or _podil_procedury(text) >= 0.3:
            return True

    if pocet <= PREDSED_MAX_SLOV and not scenic:
        vety = [v for v in rozdelit_vety_steno(text) if not veta_je_hluk(v)]
        if not vety:
            return True

    return False


def _skore_vety(veta: str, *, dlouhy_projev: bool = False) -> int:
    low = veta.lower()
    sk = 0
    if re.search(r"\d", veta):
        sk += 4
    if re.search(r"\d{1,2}\s*\d{3}\s*(?:korun|Kč)|\d+\s*%", veta, re.I):
        sk += 3
    if any(
        w in low
        for w in (
            "klesne",
            "sníží",
            "zvýší",
            "zůstane",
            "platí",
            "od ledna",
            "živnost",
            "staví",
            "úřad",
            "občan",
            "poslanec",
            "návrh",
            "zamítn",
            "schvál",
        )
    ):
        sk += 2
    n = len(veta.split())
    if 12 <= n <= 35:
        sk += 2
    elif n < 8:
        sk -= 2
    if veta.endswith((".", "!", "?")):
        sk += 1
    if re.search(r"\b(z\.?\s*o\.?|novela|paragraf|článek)\b", low):
        sk -= 1
    if SCENIC_RE.search(veta):
        sk += 5
    if STRUCNY_RE.search(veta) and dlouhy_projev:
        sk += 4
    if veta_je_hluk(veta):
        sk -= 6
    return sk


def nejlepsi_vety(
    text: str,
    *,
    limit: int = 3,
    min_skore: int = 2,
    dlouhy_projev: bool = False,
) -> list[str]:
    scored: list[tuple[int, str]] = []
    for v in rozdelit_vety_steno(text):
        if veta_je_hluk(v):
            continue
        sk = _skore_vety(v, dlouhy_projev=dlouhy_projev)
        if sk >= min_skore:
            scored.append((sk, v))
    scored.sort(key=lambda x: (-x[0], -len(x[1])))
    out: list[str] = []
    seen: set[str] = set()
    for _, v in scored:
        key = v[:50].lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(v if v.endswith((".", "!", "?")) else f"{v}.")
        if len(out) >= limit:
            break
    return out


def _fakty_ze_scenic(text: str, steno_id: str, *, limit: int = 2) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for note in scenic_poznamky(text):
        key = note[:40].lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "text": note[:320],
                "source": "steno",
                "kind": "scene",
                "steno_id": steno_id,
                "citace": f"({note[:200]})",
            }
        )
        if len(out) >= limit:
            break
    return out


def fakty_z_steno_record(
    rec: dict[str, Any],
    *,
    predsed_jmena: set[str] | None = None,
    limit: int = 3,
) -> list[dict[str, Any]]:
    if je_organizacni_vstup(rec, predsed_jmena=predsed_jmena):
        return []

    text = rec.get("text") or ""
    steno_id = rec.get("id") or ""
    pocet = int(rec.get("pocet_slov") or 0)
    dlouhy = pocet >= 300

    out: list[dict[str, Any]] = []
    out.extend(_fakty_ze_scenic(text, steno_id, limit=1 if limit >= 2 else 0))

    veta_limit = max(1, limit - len(out))
    for veta in nejlepsi_vety(text, limit=veta_limit, dlouhy_projev=dlouhy):
        citace = veta[:200]
        out.append(
            {
                "text": veta[:320],
                "source": "steno",
                "steno_id": steno_id,
                "citace": citace,
            }
        )
    return out[:limit]


def fakty_z_steno_text(steno_text: str, steno_id: str, *, limit: int = 3) -> list[dict[str, Any]]:
    rec = {"id": steno_id, "text": steno_text, "pocet_slov": len((steno_text or "").split())}
    return fakty_z_steno_record(rec, limit=limit)
