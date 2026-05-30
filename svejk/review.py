"""Porovnání raw dat, aligned témat a exportních textů — pro ruční doladění facts/."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from svejk.build.day_content import (
    build_den_content,
    dopad_z_fact,
    parliament_lead_z_fact,
    zaver_z_obsahu,
    _lead_kratky,
    _mean_z_dopadu,
)
from svejk.build.steno_text import nejlepsi_vety
from svejk.build.io import iter_jsonl, read_json
from svejk.listy import _glosa_je_nedostatecna
from svejk.obcansky import GENERIC_GLOSA_MARKERS, glosa_pro_obcana
from svejk.paths import SchuzePaths


@dataclass
class ReviewIssue:
    level: str  # warn | info
    code: str
    message: str


@dataclass
class TopicReview:
    slug: str
    nazev: str
    datum: str
    proslo: bool
    publikovat: bool
    raw_votes: list[dict[str, Any]] = field(default_factory=list)
    tema_vysvetleni: str = ""
    tema_svejk: str = ""
    fact: dict[str, Any] = field(default_factory=dict)
    export_lead: str = ""
    export_mean: str = ""
    export_parliament: str = ""
    issues: list[ReviewIssue] = field(default_factory=list)


def _votes_by_cislo(paths: SchuzePaths) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    if not paths.votes_jsonl.is_file():
        return out
    for v in iter_jsonl(paths.votes_jsonl):
        c = v.get("cislo")
        if c is not None:
            out[int(c)] = v
    return out


def _topic_map(paths: SchuzePaths) -> dict[str, dict[str, Any]]:
    if not paths.topics_json.is_file():
        return {}
    data = read_json(paths.topics_json)
    return {t["slug"]: t for t in data.get("topics") or [] if t.get("slug")}


def _issues_for_topic(
    fact: dict[str, Any],
    topic: dict[str, Any] | None,
    *,
    export_lead: str,
    export_mean: str,
    export_parliament: str,
) -> list[ReviewIssue]:
    issues: list[ReviewIssue] = []
    vysv = (topic or {}).get("tema_vysvetleni") or ""
    fakty = fact.get("fakty") or []
    koho = fact.get("koho") or []
    nadpis = (fact.get("nadpis") or "").strip()

    if not fact.get("publikovat"):
        issues.append(ReviewIssue("info", "skip", "Nepublikuje se (publikovat: false)."))
        return issues

    if not fakty:
        issues.append(ReviewIssue("warn", "no_fakty", "Chybí konkrétní věty ve fakty[] — doplnit z tema_vysvetleni nebo stena."))
    if vysv and _glosa_je_nedostatecna(vysv):
        issues.append(ReviewIssue("warn", "generic_tema", "tema_vysvetleni je obecné — přepsat v aligned nebo doplnit facts."))
    elif vysv and not fakty:
        issues.append(ReviewIssue("info", "tema_ready", "V aligned je použitelné tema_vysvetleni — zkopíruj do fakty[]."))

    gloss = glosa_pro_obcana(fact.get("nazev", ""), vysv, proslo=fact.get("proslo", True))
    if gloss and _glosa_je_nedostatecna(gloss):
        issues.append(ReviewIssue("warn", "generic_glosa", "Automatická glosa je slabá (fallback)."))

    low_parl = export_parliament.lower()
    if (
        ("schválili změny v " in low_parl or "zamítli změny v " in low_parl)
        and "hlasován" not in low_parl
    ):
        issues.append(
            ReviewIssue(
                "warn",
                "generic_parliament",
                "Úvodní věta je generická („schválili změny v …“) — upravit fakty nebo nadpis.",
            )
        )

    if export_mean and export_lead and export_mean.strip() == export_lead.strip():
        issues.append(ReviewIssue("warn", "duplicate", "Lead a „Co to znamená“ jsou stejné."))

    if koho and not fakty and len(export_mean) < 120:
        issues.append(ReviewIssue("warn", "thin_body", "Jen řádek Koho — chybí konkrétní dopad (částky, termíny)."))

    if nadpis and nadpis.lower().startswith("změna "):
        issues.append(ReviewIssue("info", "fallback_title", "Nadpis vypadá jako automatický fallback — zvaž ruční nadpis."))

    return issues


def review_topic(paths: SchuzePaths, slug: str) -> TopicReview | None:
    fp = paths.facts_by_topic / f"{slug}.json"
    if not fp.is_file():
        return None
    fact = read_json(fp)
    topics = _topic_map(paths)
    topic = topics.get(slug)
    votes_idx = _votes_by_cislo(paths)

    raw_votes: list[dict[str, Any]] = []
    if topic:
        for c in topic.get("vote_cisla") or []:
            v = votes_idx.get(int(c))
            if v:
                raw_votes.append(v)

    export_lead = _lead_kratky(fact, topic)
    dopad = dopad_z_fact(fact)
    export_mean = _mean_z_dopadu(dopad, export_lead)
    export_parliament = parliament_lead_z_fact(fact, topic)

    tr = TopicReview(
        slug=slug,
        nazev=fact.get("nazev", slug),
        datum=fact.get("datum", topic.get("datum", "") if topic else ""),
        proslo=bool(fact.get("proslo")),
        publikovat=bool(fact.get("publikovat")),
        raw_votes=raw_votes[:8],
        tema_vysvetleni=(topic or {}).get("tema_vysvetleni") or "",
        tema_svejk=(topic or {}).get("tema_svejk") or "",
        fact=fact,
        export_lead=export_lead,
        export_mean=export_mean,
        export_parliament=export_parliament,
    )
    tr.issues = _issues_for_topic(
        fact,
        topic,
        export_lead=export_lead,
        export_mean=export_mean,
        export_parliament=export_parliament,
    )
    return tr


def review_day(paths: SchuzePaths, den: str) -> list[TopicReview]:
    from svejk.timeline import normalize_day

    d_unl = normalize_day(den)
    d = datetime.strptime(d_unl, "%d.%m.%Y")
    day_path = paths.facts_by_day / f"{d.strftime('%Y-%m-%d')}.json"
    if not day_path.is_file():
        raise FileNotFoundError(f"Chybí index dne: {day_path}")
    day = read_json(day_path)
    out: list[TopicReview] = []
    for slug in day.get("topic_slugs") or []:
        tr = review_topic(paths, slug)
        if tr:
            out.append(tr)
    return out


def audit_weak_facts(paths: SchuzePaths) -> list[TopicReview]:
    weak: list[TopicReview] = []
    if not paths.facts_by_topic.is_dir():
        return weak
    for fp in sorted(paths.facts_by_topic.glob("*.json")):
        fact = read_json(fp)
        if not fact.get("publikovat"):
            continue
        tr = review_topic(paths, fact["slug"])
        if not tr:
            continue
        if any(i.level == "warn" for i in tr.issues):
            weak.append(tr)
    return weak


def _wrap(label: str, text: str, width: int = 72) -> list[str]:
    import textwrap

    lines = [f"── {label} " + "─" * max(0, width - len(label) - 4)]
    t = (text or "").strip()
    if not t:
        lines.append("  (prázdné)")
    else:
        for para in t.split("\n"):
            lines.extend(textwrap.wrap(para, width=width, initial_indent="  ", subsequent_indent="  ") or ["  "])
    return lines


def format_topic_review(
    tr: TopicReview,
    paths: SchuzePaths,
    *,
    show_votes: int = 5,
) -> str:
    lines: list[str] = []
    flag = " ".join(f"[{i.code}]" for i in tr.issues if i.level == "warn") or "[ok]"
    lines.append(f"\n{'=' * 72}")
    lines.append(f"  {tr.slug}  {flag}")
    lines.append(f"  {tr.nazev}  ·  {tr.datum}  ·  {'prošlo' if tr.proslo else 'neprošlo'}")
    lines.append(f"{'=' * 72}")

    for i in tr.issues:
        mark = "!" if i.level == "warn" else "·"
        lines.append(f"  {mark} {i.message}")

    if tr.raw_votes:
        lines.append("")
        lines.append("── RAW (hlasování UNL) " + "─" * 48)
        for v in tr.raw_votes[:show_votes]:
            nazev = (v.get("nazev") or "(pořad schůze)").strip()[:60]
            lines.append(
                f"  #{v.get('cislo')} {v.get('cas', '')}  {v.get('vysledek', '?')}  "
                f"pro={v.get('pro')} proti={v.get('proti')}  {nazev}"
            )
        extra = len(tr.raw_votes) - show_votes
        if extra > 0:
            lines.append(f"  … +{extra} dalších hlasování")

    lines.extend(_wrap("ALIGNED tema_vysvetleni", tr.tema_vysvetleni))
    if tr.tema_svejk:
        lines.extend(_wrap("ALIGNED tema_svejk", tr.tema_svejk))

    fact = tr.fact
    lines.append("")
    lines.append("── FACTS (edituj processed/.../facts/by_topic/…json) " + "─" * 22)
    lines.append(f"  nadpis: {fact.get('nadpis', '')}")
    lines.append(f"  predmet_lidsky: {fact.get('predmet_lidsky', '')}")
    for k in fact.get("koho") or []:
        lines.extend(_wrap("koho", k))
    for j, f in enumerate(fact.get("fakty") or [], 1):
        lines.extend(_wrap(f"fakty[{j}]", f.get("text", "")))

    topic = _topic_map(paths).get(tr.slug) if tr.slug else None
    steno_ids = (topic or {}).get("steno_ids") or []
    if paths.steno_jsonl.is_file() and steno_ids:
        steno_by_id = {s["id"]: s for s in iter_jsonl(paths.steno_jsonl)}
        lines.append("")
        lines.append("── STENO (návrhy vět do fakty[]) " + "─" * 32)
        shown = 0
        for sid in steno_ids[:6]:
            rec = steno_by_id.get(sid)
            if not rec:
                continue
            jmeno = (rec.get("cele_jmeno") or "").strip()
            for v in nejlepsi_vety(rec.get("text") or "", limit=2):
                lines.extend(_wrap(f"{sid} {jmeno}", v))
                shown += 1
                if shown >= 4:
                    break
            if shown >= 4:
                break
    elif steno_ids:
        lines.append("")
        lines.append(f"  (steno_ids={len(steno_ids)}, ale chybí raw/steno.jsonl — spusť fetch)")

    lines.extend(_wrap("EXPORT lead (na stránce)", tr.export_lead))
    lines.extend(_wrap("EXPORT mean (Co to znamená)", tr.export_mean))
    lines.extend(_wrap("EXPORT parliament (md úvod)", tr.export_parliament))

    return "\n".join(lines)


def format_day_review(
    paths: SchuzePaths,
    den: str,
    *,
    show_votes: int = 5,
) -> str:
    from svejk.timeline import normalize_day

    d_unl = normalize_day(den)
    d = datetime.strptime(d_unl, "%d.%m.%Y")
    day_path = paths.facts_by_day / f"{d.strftime('%Y-%m-%d')}.json"
    day = read_json(day_path) if day_path.is_file() else {}
    topics = review_day(paths, den)

    zaver_line = ""
    if day_path.is_file():
        content = build_den_content(day_path, paths)
        zaver_line = content.zaver

    header = [
        "",
        f"REVIEW  schůze {paths.obdobi}-s{paths.schuze}  den {d_unl}",
        f"Soubor dne: facts/by_day/{d.strftime('%Y-%m-%d')}.json",
        "",
    ]
    if zaver_line:
        header.extend(_wrap("EXPORT závěr (shrnutí stránky)", zaver_line))
        header.append("")
    header.extend(
        [
            "Workflow: uprav facts → ./run-svejk.sh build --schuze N --only compose [--den D]",
            "         → export-pages / lokální http.server",
            "Volitelně v by_day JSON: \"zaver\": \"vlastní věta bez Poslušně hlásím\"",
            "",
        ]
    )
    if not topics:
        header.append("  (žádná publikovaná témata v indexu dne)")
        return "\n".join(header)

    parts = header + [format_topic_review(t, paths, show_votes=show_votes) for t in topics]
    warns = sum(1 for t in topics for i in t.issues if i.level == "warn")
    parts.append(f"\nSouhrn: {len(topics)} témat, {warns} varování.\n")
    return "\n".join(parts)


def format_audit_report(weak: list[TopicReview], paths: SchuzePaths) -> str:
    lines = [
        "",
        f"AUDIT textů  {paths.obdobi}-s{paths.schuze}  ({len(weak)} slabých témat)",
        "",
    ]
    for tr in weak:
        warns = [i for i in tr.issues if i.level == "warn"]
        codes = ", ".join(i.code for i in warns)
        lines.append(f"  {tr.datum}  {tr.slug}")
        lines.append(f"    {codes}  —  {tr.nazev[:55]}")
    lines.append("")
    lines.append("Detail jednoho tématu:  ./run-svejk.sh review --schuze N --slug <slug>")
    lines.append("")
    return "\n".join(lines)
