"""Audit: pojmy ve facts/steno bez tooltipu v glosáři."""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from svejk.build.glossary_markup import _pattern
from svejk.build.io import iter_jsonl, read_json
from svejk.glossary import GLOSSARY
from svejk.paths import SchuzePaths, processed_root

# Sněmovní / úřednické fráze, které čtenář nemusí znát (heuristika).
JARGON_SEEDS: tuple[str, ...] = (
    r"stanovisko vlády",
    r"prvé čtení",
    r"první čtení",
    r"druhé čtení",
    r"třetí čtení",
    r"prvém čtení",
    r"druhém čtení",
    r"třetím čtení",
    r"sněmovní tisk",
    r"senátní návrh",
    r"vládní návrh",
    r"zpravodaj(?:ka|em|ovi|ky)?",
    r"podrobn(?:á|é|ou) rozprav",
    r"obecn(?:á|é|ou) rozprav",
    r"rozhodn(?:é|ého) hlasování",
    r"přeruš(?:í|ení|ujeme) bod",
    r"legislativní nouz",
    r"zkrácen(?:é|ém|ého) (?:jednání|projednávání|režimu)",
    r"zrychlen(?:é|ého) projednávání",
    r"pozměňovací návrh",
    r"vrácen(?:o|ý|á) senátem",
    r"usnesení(?:m|mi)?",
    r"tajné hlasování",
    r"tajnou volbu",
    r"volební komis",
    r"mandátový(?: a imunitní)? výbor",
    r"imunitní výbor",
    r"vyšetřovací komis",
    r"grémi(?:a|u|um)",
    r"ověřovatel(?:é|e|ů)?",
    r"místopředsed(?:kyně|kyni|kyni|ce|a|ové|ů)",
    r"ustavující schůz",
    r"interpelac",
    r"nedůvěr",
    r"střet(?:u|) zájm",
    r"nominační zákon",
    r"ústavní zákon",
    r"existenční minimum",
    r"životní minimum",
    r"superdávk",
    r"landsmanšaft",
    r"plénu(?:m)?",
    r"Senát(?:em|u)?",
    r"sněmovní tisk",
    r"QR kód",
    r"OSVČ",
    r"Dozimetr",
    r"Agrofert",
    r"NKÚ",
    r"VZP",
    r"eLegislativa",
    r"online zákonodárství",
    r"kuponov(?:á|ou) debabišizac",
    r"polistopadov(?:ý|ým) kartel",
    r"transparent(?:em|y)?",
    r"gong(?:em|u)?",
    r"poměrn(?:é|ého) zastoupení",
    r"závěrečný účet",
    r"mimořádn(?:ou|á) schůz",
    r"pořad(?:u|) schůze",
    r"návrh z grémia",
    r"dohod(?:a|y) z grémia",
    r"ústava",
    r"Ústava",
)

JARGON_RE = re.compile(
    "|".join(f"(?:{p})" for p in JARGON_SEEDS),
    re.IGNORECASE,
)

SKIP_CONTEXT = re.compile(
    r"^\s*(?:prosím|děkuji|a\s+prosím|paní|pane|vážen|kolegyn|kolegové)\b",
    re.I,
)

# Krátké vzory snadno padají do běžných slov (vzpomeňte, senátor, nedůvěryhodný).
FALSE_POSITIVE = re.compile(
    r"(?:vzpome|senátor|senátore|nedůvěry|nedůvěryhod)",
    re.I,
)


@dataclass
class Gap:
    phrase: str
    schuze: int
    slug: str
    datum: str
    source: str  # fact | steno | export
    snippet: str
    in_glossary: bool = False


def _norm(s: str) -> str:
    return unicodedata.normalize("NFKD", s.lower())


def is_covered_by_glossary(text: str, start: int, end: int) -> bool:
    """Překrývá se výskyt s nějakou frází z GLOSSARY?"""
    for gp, _ in GLOSSARY:
        for m in _pattern(gp).finditer(text):
            if not (m.end() <= start or m.start() >= end):
                return True
    return False


def _collect_export_text(paths: SchuzePaths, slug: str) -> str:
    from svejk.review import review_topic

    tr = review_topic(paths, slug)
    if not tr:
        return ""
    parts = [tr.export_lead, tr.export_mean, tr.export_parliament]
    for f in tr.fact.get("fakty") or []:
        parts.append(f.get("text") or "")
    for k in tr.fact.get("koho") or []:
        parts.append(k)
    return "\n".join(p for p in parts if p)


def _steno_for_topic(paths: SchuzePaths, slug: str) -> list[dict[str, Any]]:
    from svejk.review import _topic_map

    topic = _topic_map(paths).get(slug)
    if not topic or not paths.steno_jsonl.is_file():
        return []
    ids = set(topic.get("steno_ids") or [])
    if not ids:
        return []
    return [r for r in iter_jsonl(paths.steno_jsonl) if r.get("id") in ids]


def audit_schuze(paths: SchuzePaths, *, export_only: bool = False) -> list[Gap]:
    gaps: list[Gap] = []
    if not paths.facts_by_topic.is_dir():
        return gaps

    for fp in sorted(paths.facts_by_topic.glob("*.json")):
        fact = read_json(fp)
        if not fact.get("publikovat"):
            continue
        slug = fact["slug"]
        datum = fact.get("datum", "")
        export = _collect_export_text(paths, slug)
        steno_recs = _steno_for_topic(paths, slug)

        checked: set[str] = set()

        def check_text(text: str, source: str) -> None:
            if not text or len(text.strip()) < 8:
                return
            for m in JARGON_RE.finditer(text):
                phrase = m.group(0).strip()
                if FALSE_POSITIVE.search(text[max(0, m.start() - 6) : m.end() + 6]):
                    continue
                key = (_norm(phrase), source, slug)
                if key in checked:
                    continue
                checked.add(key)
                covered = is_covered_by_glossary(text, m.start(), m.end())
                if covered:
                    continue
                start = max(0, m.start() - 30)
                end = min(len(text), m.end() + 40)
                snippet = text[start:end].replace("\n", " ")
                gaps.append(
                    Gap(
                        phrase=phrase,
                        schuze=paths.schuze,
                        slug=slug,
                        datum=datum,
                        source=source,
                        snippet=snippet,
                        in_glossary=False,
                    )
                )

        check_text(export, "export")
        if not export_only:
            for rec in steno_recs:
                txt = rec.get("text") or ""
                if SKIP_CONTEXT.match(txt[:80]):
                    continue
                check_text(txt, "steno")

    return gaps


def audit_obdobi(
    obdobi: int = 2025,
    od: int = 1,
    do: int = 99,
    *,
    export_only: bool = False,
) -> list[Gap]:
    all_gaps: list[Gap] = []
    for p in sorted(processed_root().glob(f"{obdobi}-s*")):
        if not p.is_dir():
            continue
        try:
            cislo = int(p.name.split("-s", 1)[1])
        except ValueError:
            continue
        if not (od <= cislo <= do):
            continue
        paths = SchuzePaths.create(obdobi, cislo)
        all_gaps.extend(audit_schuze(paths, export_only=export_only))
    return all_gaps


def summarize_gaps(gaps: list[Gap]) -> dict[str, list[Gap]]:
    by_phrase: dict[str, list[Gap]] = defaultdict(list)
    for g in gaps:
        by_phrase[_norm(g.phrase)].append(g)
    return dict(sorted(by_phrase.items(), key=lambda x: -len(x[1])))


def format_report(gaps: list[Gap], *, limit: int = 40) -> str:
    if not gaps:
        return "Všechny sledované pojmy jsou pokryté glosářem (tooltipem).\n"

    grouped = summarize_gaps(gaps)
    lines = [
        "",
        f"GLOSSARY AUDIT — {len(gaps)} výskytů bez tooltipu ({len(grouped)} unikátních pojmů)",
        "",
    ]
    for i, (phrase_key, items) in enumerate(grouped.items()):
        if i >= limit:
            lines.append(f"… +{len(grouped) - limit} dalších pojmů")
            break
        sample = items[0]
        lines.append(f"  [{len(items)}×]  {sample.phrase}")
        schuze = sorted({g.schuze for g in items})
        lines.append(f"         schůze: {', '.join(f's{s}' for s in schuze)}")
        ex = items[0]
        lines.append(f"         zdroj: {ex.source} · {ex.slug}")
        lines.append(f"         …{ex.snippet}…")
        lines.append("")
    lines.append("Doplň do svejk/glossary.py nebo uprav facts, aby se pojem vysvětlil v textu.")
    lines.append("")
    return "\n".join(lines)
