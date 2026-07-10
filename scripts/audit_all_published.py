#!/usr/bin/env python3
"""Souhrnný audit všech publikovaných vydání."""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
APPROVED_PATH = ROOT / "processed/publish-approved.json"
REPORT_MD = ROOT / "grammer_check/published-review-report.md"
REPORT_JSON = ROOT / "grammer_check/published-review-report.json"

sys.path.insert(0, str(ROOT))

from svejk.build.extract import skore_z_verdiktu  # noqa: E402
from svejk.build.nav import list_site_editions, _editions_on_day, resolve_edition  # noqa: E402
from svejk.build.urls import edition_schuze_subpage, steno_export_relpath  # noqa: E402
from svejk.build.io import iter_jsonl, read_json  # noqa: E402
from svejk.build.steno_sources import (  # noqa: E402
    _find_phrase_in_text,
    build_item_steno_links,
    collect_steno_sources,
    passages_for_slug,
    steno_sources_href,
)
from svejk.build.vote_logic import topic_proslo_from_votes, vote_kategorie  # noqa: E402
from svejk.glossary_audit import audit_obdobi  # noqa: E402
from svejk.paths import SchuzePaths  # noqa: E402
from svejk.review import audit_weak_facts  # noqa: E402

# Reuse citace checks from existing scripts
from scripts.audit_published_steno import (  # noqa: E402
    citace_in_text,
    find_correct_ids,
    load_approved as steno_load_approved,
    steno_by_id as load_steno_by_id,
)
from scripts.audit_published_text import (  # noqa: E402
    audit_topic as audit_text_topic,
    load_approved as text_load_approved,
    load_steno as text_load_steno,
)


@dataclass
class Finding:
    level: str  # error | warn | info
    code: str
    key: str = ""
    slug: str = ""
    message: str = ""


@dataclass
class Report:
    findings: list[Finding] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def add(self, level: str, code: str, message: str, *, key: str = "", slug: str = "") -> None:
        self.findings.append(Finding(level, code, key, slug, message))
        self.counts[f"{level}:{code}"] += 1


def parse_key(key: str) -> tuple[int, int, str, str]:
    ob, sch, cz = key.split("/", 2)
    iso = datetime.strptime(cz.strip(), "%d.%m.%Y").strftime("%Y-%m-%d")
    return int(ob), int(sch), iso, cz.strip()


def _strip_html(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s or "")


def _has_steno_link(text: str, phrase: str) -> bool:
    if not text or not phrase:
        return False
    for m in re.finditer(r'class="steno-link"[^>]*>(.*?)</a>', text, re.I | re.S):
        inner = _strip_html(m.group(1))
        if phrase.lower() in inner.lower() or inner.lower() in phrase.lower():
            return True
    return False


def audit_link_roundtrip(report: Report) -> None:
    """link_phrase → compose vloží steno-link do článku."""
    approved = json.loads(APPROVED_PATH.read_text(encoding="utf-8")).get("approved") or []
    for key in approved:
        ob, sch, iso, cz = parse_key(key)
        paths = SchuzePaths.create(ob, sch)
        day_path = paths.facts_by_day / f"{iso}.json"
        if not day_path.is_file():
            continue
        day = read_json(day_path)
        if not day.get("steno_zdroje"):
            continue
        blocks = collect_steno_sources(paths, cz)
        page_href = steno_sources_href(ob, sch, cz, link_mode="pages")
        for slug in day.get("topic_slugs") or []:
            fp = paths.facts_by_topic / f"{slug}.json"
            if not fp.is_file():
                continue
            fact = read_json(fp)
            if not fact.get("publikovat"):
                continue
            passages = passages_for_slug(blocks, slug)
            item = SimpleNamespace(
                slug=slug,
                lead=(fact.get("lead") or "").strip(),
                pointa=(fact.get("pointa") or "").strip(),
                mean=(fact.get("mean") or "").strip(),
                kuriozita=(fact.get("kuriozita") or "").strip(),
                citace_text=(fact.get("citace_text") or "").strip(),
                citace_href="",
            )
            before = json.dumps(
                {f: getattr(item, f) for f in ("lead", "pointa", "mean", "kuriozita")},
                ensure_ascii=False,
            )
            build_item_steno_links(passages, item, page_href)
            after = json.dumps(
                {f: getattr(item, f) for f in ("lead", "pointa", "mean", "kuriozita")},
                ensure_ascii=False,
            )
            linked = before != after
            for p in passages:
                lp = (p.link_phrase or "").strip()
                if not lp:
                    continue
                article = " ".join(
                    (fact.get(k) or "")
                    for k in ("lead", "pointa", "mean", "kuriozita", "citace_text")
                )
                if not _find_phrase_in_text(article, lp):
                    report.add(
                        "warn",
                        "orphan_link_phrase",
                        f"link_phrase «{lp[:50]}» není v textu článku",
                        key=key,
                        slug=slug,
                    )
                    continue
                fields = {f: getattr(item, f) or "" for f in ("lead", "pointa", "mean", "kuriozita")}
                if not any(_has_steno_link(v, lp) for v in fields.values()):
                    report.add(
                        "error",
                        "missing_steno_link",
                        f"link_phrase «{lp[:50]}» se nepromítla do odkazu (kotva {p.anchor})",
                        key=key,
                        slug=slug,
                    )
            if not linked and any((p.link_phrase or "").strip() for p in passages):
                report.add(
                    "warn",
                    "no_links_injected",
                    "Článek má link_phrase, ale compose nevložil žádný steno-link",
                    key=key,
                    slug=slug,
                )


def audit_duplicate_steno_id(report: Report) -> None:
    approved = json.loads(APPROVED_PATH.read_text(encoding="utf-8")).get("approved") or []
    for key in approved:
        ob, sch, iso, cz = parse_key(key)
        paths = SchuzePaths.create(ob, sch)
        day_path = paths.facts_by_day / f"{iso}.json"
        if not day_path.is_file():
            continue
        day = read_json(day_path)
        day_ids: dict[str, list[str]] = defaultdict(list)
        for slug in day.get("topic_slugs") or []:
            fp = paths.facts_by_topic / f"{slug}.json"
            if not fp.is_file():
                continue
            fact = read_json(fp)
            if not fact.get("publikovat"):
                continue
            for i, f in enumerate(fact.get("fakty") or []):
                sid = (f.get("steno_id") or "").strip()
                if sid:
                    day_ids[sid].append(f"{slug}[{i}]")
        for sid, refs in day_ids.items():
            if len(refs) > 1:
                report.add(
                    "warn",
                    "duplicate_steno_id",
                    f"{sid} použito {len(refs)}×: {', '.join(refs[:4])}{'…' if len(refs) > 4 else ''}",
                    key=key,
                )


def _topic_map(paths: SchuzePaths) -> dict[str, dict]:
    if not paths.topics_json.is_file():
        return {}
    return {t["slug"]: t for t in read_json(paths.topics_json).get("topics") or [] if t.get("slug")}


def _votes_index(paths: SchuzePaths) -> dict[int, dict]:
    out: dict[int, dict] = {}
    if paths.votes_jsonl.is_file():
        for v in iter_jsonl(paths.votes_jsonl):
            c = v.get("cislo")
            if c is not None:
                out[int(c)] = v
    return out


def audit_verdikt_vs_votes(report: Report) -> None:
    approved = json.loads(APPROVED_PATH.read_text(encoding="utf-8")).get("approved") or []
    for key in approved:
        ob, sch, iso, cz = parse_key(key)
        paths = SchuzePaths.create(ob, sch)
        topics = _topic_map(paths)
        votes = _votes_index(paths)
        day_path = paths.facts_by_day / f"{iso}.json"
        if not day_path.is_file():
            continue
        day = read_json(day_path)
        for slug in day.get("topic_slugs") or []:
            fp = paths.facts_by_topic / f"{slug}.json"
            if not fp.is_file():
                continue
            fact = read_json(fp)
            if not fact.get("publikovat"):
                continue
            verdikt = (fact.get("verdikt") or "").strip()
            if verdikt in ("debata", ""):
                continue
            topic = topics.get(slug) or {}
            group = [votes[int(c)] for c in (topic.get("vote_cisla") or []) if int(c) in votes]
            if not group:
                continue
            group = sorted(group, key=lambda v: (v.get("datum", ""), v.get("cas", "")))
            proslo = topic_proslo_from_votes(group)
            expected = "schvaleno" if proslo else "zamiteno"
            if verdikt in ("zvoleno",):
                expected = "zvoleno" if proslo else "zamiteno"
            if verdikt in ("odlozeno",) and not proslo:
                continue
            if verdikt == expected:
                continue
            if verdikt == "odlozeno":
                continue
            # Zákon mohl projít prvním kolem, ale padnout v závěrečném hlasování (např. zvířata #165 A, #167 R).
            last = group[-1]
            if (
                verdikt == "zamiteno"
                and proslo
                and last.get("vysledek") == "R"
                and (last.get("proti") or 0) > (last.get("pro") or 0)
            ):
                continue
            report.add(
                "error",
                "verdikt_mismatch",
                f"verdikt={verdikt}, hlasování naznačuje «{expected}» "
                f"(poslední #{last.get('cislo')} {last.get('vysledek')} {last.get('pro')}:{last.get('proti')})",
                key=key,
                slug=slug,
            )


def audit_skore_dne(report: Report) -> None:
    approved = json.loads(APPROVED_PATH.read_text(encoding="utf-8")).get("approved") or []
    for key in approved:
        ob, sch, iso, cz = parse_key(key)
        paths = SchuzePaths.create(ob, sch)
        day_path = paths.facts_by_day / f"{iso}.json"
        if not day_path.is_file():
            continue
        day = read_json(day_path)
        slugs = day.get("topic_slugs") or []
        skore_p, skore_z = skore_z_verdiktu(slugs, paths)
        stats = day.get("stats") or {}
        day_p = int(stats.get("proslo") or day.get("proslo") or 0)
        day_z = int(stats.get("zamitnuto") or day.get("zamitnuto") or 0)
        if day.get("skore_manual"):
            continue
        if skore_p != day_p or skore_z != day_z:
            report.add(
                "warn",
                "skore_mismatch",
                f"ze článků {skore_p}:{skore_z}, ve stats dne {day_p}:{day_z}",
                key=key,
            )
        # pocet_hlas jen zákony
        if paths.votes_jsonl.is_file() and stats.get("pocet_hlas"):
            law_votes = 0
            for v in iter_jsonl(paths.votes_jsonl):
                if v.get("je_porad_schuze"):
                    continue
                d = (v.get("datum") or "")
                if not d.startswith(iso):
                    continue
                if vote_kategorie(v.get("nazev") or "") == "substantivni":
                    law_votes += 1
            declared = int(stats.get("pocet_hlas") or 0)
            if declared and law_votes and abs(declared - law_votes) > 2:
                report.add(
                    "info",
                    "pocet_hlas_drift",
                    f"stats.pocet_hlas={declared}, substantivních hlasování dne ≈{law_votes}",
                    key=key,
                )


def audit_steno_citace(report: Report) -> None:
    for ob, sch, iso, key in steno_load_approved():
        base = ROOT / f"processed/{ob}-s{sch}"
        day_path = base / "facts/by_day" / f"{iso}.json"
        steno_path = base / "raw/steno.jsonl"
        if not day_path.is_file() or not steno_path.is_file():
            continue
        day = read_json(day_path)
        steno = load_steno_by_id(steno_path)
        for slug in day.get("topic_slugs") or []:
            tpath = base / "facts/by_topic" / f"{slug}.json"
            if not tpath.is_file():
                continue
            topic = read_json(tpath)
            if topic.get("publikovat") is False:
                continue
            for i, f in enumerate(topic.get("fakty") or []):
                if not isinstance(f, dict):
                    continue
                cit = (f.get("citace") or "").strip()
                if not cit:
                    continue
                sid = (f.get("steno_id") or "").strip()
                if f.get("source") == "steno" and not sid:
                    report.add("error", "missing_steno_id", f"fakty[{i}] bez steno_id", key=key, slug=slug)
                    continue
                if sid:
                    rec = steno.get(sid)
                    if not rec:
                        report.add("error", "unknown_steno_id", f"fakty[{i}] {sid}", key=key, slug=slug)
                    elif not citace_in_text(cit, rec.get("text", "")):
                        hits = find_correct_ids(steno, cit)
                        report.add(
                            "error",
                            "bad_citace",
                            f"fakty[{i}] {sid} → správně {hits[0] if hits else '?'}",
                            key=key,
                            slug=slug,
                        )


def audit_text_quotes(report: Report) -> None:
    for ob, sch, iso, key in text_load_approved():
        base = ROOT / f"processed/{ob}-s{sch}"
        day_path = base / "facts/by_day" / f"{iso}.json"
        if not day_path.is_file():
            continue
        steno_by_id = text_load_steno(sch, base)
        if not steno_by_id:
            continue
        day = read_json(day_path)
        for slug in day.get("topic_slugs") or []:
            tpath = base / "facts/by_topic" / f"{slug}.json"
            if not tpath.is_file():
                continue
            topic = read_json(tpath)
            if topic.get("publikovat") is False:
                continue
            for issue in audit_text_topic(topic, key=key, steno_by_id=steno_by_id):
                report.add(issue.level, issue.code, issue.message, key=key, slug=slug)


def audit_steno_nalezitosti(report: Report) -> None:
    approved = json.loads(APPROVED_PATH.read_text(encoding="utf-8")).get("approved") or []
    for key in approved:
        ob, sch, iso, cz = parse_key(key)
        paths = SchuzePaths.create(ob, sch)
        day_path = paths.facts_by_day / f"{iso}.json"
        if not day_path.is_file():
            continue
        day = read_json(day_path)
        if not day.get("steno_zdroje"):
            continue
        for block in collect_steno_sources(paths, cz):
            for p in block.passages:
                if p.anchor.startswith("vote-"):
                    if not (p.article_phrase or "").strip():
                        report.add(
                            "info",
                            "vote_no_article_phrase",
                            (p.summary or "")[:80],
                            key=key,
                            slug=block.slug,
                        )
                    continue
                miss = []
                if not (p.article_phrase or "").strip():
                    miss.append("article_phrase")
                if not (p.summary or "").strip():
                    miss.append("summary")
                if not (p.citace or "").strip():
                    miss.append("citace")
                if not (p.excerpt or "").strip() or (
                    p.excerpt.strip() == (p.citace or "").strip()
                    and len((p.citace or "").strip()) > 100
                ):
                    miss.append("excerpt")
                if miss:
                    report.add(
                        "warn",
                        "steno_incomplete",
                        f"{p.anchor} ({p.speaker}): {', '.join(miss)}",
                        key=key,
                        slug=block.slug,
                    )


def audit_editorial(report: Report) -> None:
    schuze_done: set[int] = set()
    approved = json.loads(APPROVED_PATH.read_text(encoding="utf-8")).get("approved") or []
    for key in approved:
        _, sch, _, _ = parse_key(key)
        if sch in schuze_done:
            continue
        schuze_done.add(sch)
        paths = SchuzePaths.create(2025, sch)
        for tr in audit_weak_facts(paths):
            for i in tr.issues:
                if i.level != "warn":
                    continue
                report.add("warn", f"review_{i.code}", i.message, slug=tr.slug)


def audit_glossary(report: Report) -> None:
    gaps = audit_obdobi(2025, 1, 24, export_only=True)
    for g in gaps[:200]:
        report.add(
            "info",
            "glossary_gap",
            f"«{g.phrase[:50]}» v {g.slug or g.source} (s{g.schuze})",
        )
    if len(gaps) > 200:
        report.add("info", "glossary_gap", f"… a dalších {len(gaps) - 200} pojmů")


def audit_site_links(report: Report) -> None:
    site = ROOT / "site/vydani"
    if not site.is_dir():
        report.add("info", "site_missing", "site/ neexistuje, přeskočena kontrola HTML")
        return
    approved = json.loads(APPROVED_PATH.read_text(encoding="utf-8")).get("approved") or []
    editions = list_site_editions(2025)
    for key in approved:
        ob, sch, iso, cz = parse_key(key)
        dup_day = len(_editions_on_day(editions, cz)) > 1
        canonical = resolve_edition(ob, cz)
        if dup_day and canonical and sch != canonical.schuze:
            edition = site / iso / edition_schuze_subpage(sch) / "index.html"
        else:
            edition = site / iso / "index.html"
        steno = ROOT / "site" / steno_export_relpath(cz, sch, dup_day=dup_day)
        if not edition.is_file():
            report.add("warn", "missing_edition_html", f"chybí {iso}/index.html", key=key)
        if not steno.is_file():
            day_path = ROOT / f"processed/{ob}-s{sch}/facts/by_day/{iso}.json"
            if day_path.is_file():
                day = read_json(day_path)
                if day.get("steno_zdroje"):
                    report.add(
                        "warn",
                        "missing_steno_html",
                        f"chybí {steno.relative_to(ROOT / 'site')}",
                        key=key,
                    )


def format_md(report: Report) -> str:
    lines = [
        "# Audit publikovaných vydání",
        "",
        f"Vygenerováno: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## Souhrn",
        "",
    ]
    by_code: dict[str, list[Finding]] = defaultdict(list)
    for f in report.findings:
        by_code[f.code].append(f)

    severity_order = {"error": 0, "warn": 1, "info": 2}
    codes = sorted(
        by_code.keys(),
        key=lambda c: (
            severity_order.get(by_code[c][0].level, 9),
            -len(by_code[c]),
            c,
        ),
    )
    lines.append("| Úroveň | Kód | Počet |")
    lines.append("|---|---|---:|")
    for code in codes:
        f = by_code[code][0]
        lines.append(f"| {f.level} | `{code}` | {len(by_code[code])} |")
    lines.append("")

    for code in codes:
        items = by_code[code]
        f0 = items[0]
        lines.append(f"## `{code}` ({f0.level}, {len(items)})")
        lines.append("")
        for f in items[:25]:
            loc = f"{f.key} {f.slug}".strip()
            lines.append(f"- {loc}: {f.message}")
        if len(items) > 25:
            lines.append(f"- … a dalších {len(items) - 25}")
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    report = Report()
    print("1/9 link round-trip…", file=sys.stderr)
    audit_link_roundtrip(report)
    print("2/9 duplicate steno_id…", file=sys.stderr)
    audit_duplicate_steno_id(report)
    print("3/9 verdikt vs votes…", file=sys.stderr)
    audit_verdikt_vs_votes(report)
    print("4/9 skóre dne…", file=sys.stderr)
    audit_skore_dne(report)
    print("5/9 steno citace…", file=sys.stderr)
    audit_steno_citace(report)
    print("6/9 text quotes…", file=sys.stderr)
    audit_text_quotes(report)
    print("7/9 steno náležitosti…", file=sys.stderr)
    audit_steno_nalezitosti(report)
    print("8/9 editorial review…", file=sys.stderr)
    audit_editorial(report)
    print("9/9 glossary + site…", file=sys.stderr)
    audit_glossary(report)
    audit_site_links(report)

    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    md = format_md(report)
    REPORT_MD.write_text(md, encoding="utf-8")
    REPORT_JSON.write_text(
        json.dumps(
            {
                "counts": dict(report.counts),
                "findings": [f.__dict__ for f in report.findings],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(md[:3000])
    if len(md) > 3000:
        print(f"\n… celý report: {REPORT_MD}", file=sys.stderr)
    errors = sum(1 for f in report.findings if f.level == "error")
    warns = sum(1 for f in report.findings if f.level == "warn")
    print(f"\nCelkem: {errors} error, {warns} warn, {len(report.findings)} celkem", file=sys.stderr)
    print(f"Uloženo: {REPORT_MD}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
