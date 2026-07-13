"""Metriky kvality vydání pro edition review."""

from __future__ import annotations

from typing import Any

from svejk.build.io import read_json
from svejk.build.steno_sources import _find_phrase_in_text, collect_steno_sources
from svejk.edition.dates import resolve_edition_day
from svejk.edition.link_phrases import article_text
from svejk.edition.state import effective_state, fingerprint_stale, load_edition
from svejk.paths import SchuzePaths
from svejk.review import audit_weak_facts, format_day_review
from svejk.validate.names import audit_edition_day, summarize_party_issues


def _link_phrase_coverage(paths: SchuzePaths, datum_unl: str, slugs: list[str]) -> dict[str, Any]:
    total = linked = 0
    missing: list[str] = []
    for slug in slugs:
        fp = paths.facts_by_topic / f"{slug}.json"
        if not fp.is_file():
            continue
        data = read_json(fp)
        if not data.get("publikovat", True):
            continue
        article = article_text(data)
        for i, f in enumerate(data.get("fakty") or []):
            if not isinstance(f, dict):
                continue
            if not (f.get("steno_id") or "").strip():
                continue
            total += 1
            phrase = (f.get("link_phrase") or "").strip()
            if phrase and _find_phrase_in_text(article, phrase):
                linked += 1
            else:
                missing.append(f"{slug}[{i}]")
    pct = round(100 * linked / total, 1) if total else 100.0
    return {"total": total, "linked": linked, "percent": pct, "missing": missing}


def _citace_in_steno(paths: SchuzePaths, slugs: list[str]) -> dict[str, Any]:
    steno_by_id: dict[str, dict] = {}
    if paths.steno_jsonl.is_file():
        import json

        for line in paths.steno_jsonl.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                if r.get("id"):
                    steno_by_id[r["id"]] = r
    checked = ok = 0
    bad: list[str] = []
    for slug in slugs:
        fp = paths.facts_by_topic / f"{slug}.json"
        if not fp.is_file():
            continue
        data = read_json(fp)
        for i, f in enumerate(data.get("fakty") or []):
            cit = (f.get("citace") or "").strip()
            sid = (f.get("steno_id") or "").strip()
            if not cit or not sid:
                continue
            checked += 1
            text = (steno_by_id.get(sid) or {}).get("text") or ""
            if cit in text or cit.replace("\n", " ") in text.replace("\n", " "):
                ok += 1
            else:
                bad.append(f"{slug}[{i}]")
    pct = round(100 * ok / checked, 1) if checked else 100.0
    return {"checked": checked, "ok": ok, "percent": pct, "bad": bad}


def run_edition_metrics(
    paths: SchuzePaths,
    den: str,
) -> dict[str, Any]:
    datum_unl, iso, day_path = resolve_edition_day(paths, den)
    doc = load_edition(paths, iso)
    day = read_json(day_path) if day_path.is_file() else {}
    slugs = day.get("topic_slugs") or doc.get("topic_slugs") or []
    weak = audit_weak_facts(paths)
    weak_slugs = {w.slug for w in weak if w.datum == datum_unl}
    link_cov = _link_phrase_coverage(paths, datum_unl, slugs)
    citace = _citace_in_steno(paths, slugs)
    steno_blocks = 0
    steno_missing = 0
    if day.get("steno_zdroje"):
        for block in collect_steno_sources(paths, datum_unl):
            for p in block.passages:
                if p.anchor.startswith("vote-"):
                    continue
                steno_blocks += 1
                if not (p.article_phrase or "").strip():
                    steno_missing += 1
    errors = []
    if link_cov["percent"] < 80 and link_cov["total"] > 0:
        errors.append("link_phrase_coverage pod 80 %")
    if citace["percent"] < 90 and citace["checked"] > 0:
        errors.append("citace nejsou doslovně ve stenozáznamu")
    if weak_slugs:
        errors.append(f"slabá témata: {', '.join(sorted(weak_slugs)[:5])}")
    party_labels = summarize_party_issues(audit_edition_day(paths, iso))
    if party_labels["errors"]:
        errors.append(f"strany u jmen: {party_labels['errors']} chyb")
    metrics = {
        "state": effective_state(doc, paths),
        "stale": fingerprint_stale(doc, paths),
        "link_phrase_coverage": link_cov,
        "citace_in_steno": citace,
        "party_labels": party_labels,
        "generic_topic_count": len(weak_slugs),
        "steno_passages": steno_blocks,
        "steno_missing_article_phrase": steno_missing,
        "ok": not errors,
        "errors": errors,
    }
    doc["metrics"] = metrics
    from svejk.edition.state import save_edition

    save_edition(paths, iso, doc)
    return metrics


def format_edition_review(paths: SchuzePaths, den: str, *, as_json: bool = False) -> str:
    import json

    datum_unl, iso, _ = resolve_edition_day(paths, den)
    metrics = run_edition_metrics(paths, den)
    day_report = format_day_review(paths, den)
    if as_json:
        return json.dumps(
            {"metrics": metrics, "review": day_report},
            ensure_ascii=False,
            indent=2,
        )
    lines = [
        f"\nEDITION REVIEW  {paths.obdobi}-s{paths.schuze}  {datum_unl}",
        f"Stav: {metrics['state']}" + (" (stale data)" if metrics.get("stale") else ""),
        f"Link coverage: {metrics['link_phrase_coverage']['percent']}% "
        f"({metrics['link_phrase_coverage']['linked']}/{metrics['link_phrase_coverage']['total']})",
        f"Citace ve stenu: {metrics['citace_in_steno']['percent']}%",
        f"Strany u jmen: {metrics['party_labels']['errors']} chyb, "
        f"{metrics['party_labels']['warns']} varování",
        f"Slabá témata: {metrics['generic_topic_count']}",
        "",
        day_report,
    ]
    if metrics["errors"]:
        lines.insert(4, "CHYBY: " + "; ".join(metrics["errors"]))
    party_items = [
        i for i in metrics["party_labels"]["items"] if i["level"] == "error"
    ]
    if party_items:
        lines.append("")
        lines.append("Strany u jmen:")
        for item in party_items[:12]:
            ctx = f" [{item['context']}]" if item.get("context") else ""
            lines.append(f"  {item['slug']}{ctx}: {item['message']}")
        if len(party_items) > 12:
            lines.append(f"  … +{len(party_items) - 12} dalších")
    return "\n".join(lines)
