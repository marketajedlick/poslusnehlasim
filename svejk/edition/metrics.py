"""Metriky kvality vydání pro edition review."""

from __future__ import annotations

from typing import Any

from svejk.build.io import read_json
from svejk.build.steno_sources import collect_steno_sources
from svejk.edition.dates import resolve_edition_day
from svejk.edition.link_phrases import article_text
from svejk.edition.state import effective_state, fingerprint_stale, load_edition
from svejk.paths import SchuzePaths
from svejk.review import audit_weak_facts, format_day_review
from svejk.validate.names import audit_edition_day, summarize_party_issues


def _verdikt_rozpory(paths: SchuzePaths, slugs: list[str]) -> list[tuple[str, str, str]]:
    """Verdikt článku proti výsledku hlasování (typ hlasování ze stena).

    Chytá „vrácení do výboru ≠ zamítnutí“ a „první čtení ≠ zamítnutí“ z WORKFLOW §5.
    """
    from svejk.build.io import iter_jsonl
    from svejk.build.vote_logic import topic_vysledek, verdikt_odporuje, vote_motions_from_steno

    if not paths.topics_json.is_file():
        return []
    topics = {t["slug"]: t for t in read_json(paths.topics_json).get("topics") or []}
    votes = {int(v["cislo"]): v for v in iter_jsonl(paths.votes_jsonl) if v.get("cislo") is not None}
    motions: dict[int, str] | None = None
    out: list[tuple[str, str, str]] = []
    for slug in slugs:
        fp = paths.facts_by_topic / f"{slug}.json"
        topic = topics.get(slug)
        if not fp.is_file() or not topic:
            continue
        fact = read_json(fp)
        if not fact.get("publikovat", True):
            continue
        vysledek = topic.get("vysledek")
        if "vysledek" not in topic and paths.steno_jsonl.is_file():
            if motions is None:
                motions = vote_motions_from_steno(list(iter_jsonl(paths.steno_jsonl)))
            group = [votes[c] for c in topic.get("vote_cisla") or [] if c in votes]
            vysledek = topic_vysledek(group, motions)
        verdikt = (fact.get("verdikt") or "").strip()
        if verdikt_odporuje(verdikt, vysledek):
            out.append((slug, verdikt, vysledek))
    return out


def _shared_topic_days(paths: SchuzePaths, iso: str, slugs: list[str]) -> dict[str, list[str]]:
    """Témata dne, která má v topic_slugs i jiný den téže schůze."""
    out: dict[str, list[str]] = {}
    wanted = set(slugs)
    for other in sorted(paths.facts_by_day.glob("*.json")):
        if other.stem == iso:
            continue
        for slug in read_json(other).get("topic_slugs") or []:
            if slug in wanted:
                out.setdefault(slug, []).append(other.stem)
    return out


def _norm_link_text(text: str) -> str:
    """Web doplňuje k jménům stranu („Richterová (Piráti)“) a číslovky slovy;
    pro porovnání fráze s odkazem závorky vynech."""
    import re

    t = re.sub(r"\s*\([^)]*\)", "", text or "")
    return " ".join(t.split()).lower().strip(" .,;:")


def _rendered_link_texts(paths: SchuzePaths, datum_unl: str) -> dict[str, list[str]]:
    """Text uvnitř steno-link odkazů ve vykresleném článku, podle slugu."""
    import re
    from datetime import datetime

    from svejk.build.article_fields import ARTICLE_PROSE_FIELDS
    from svejk.build.day_content import build_den_content

    iso = datetime.strptime(datum_unl, "%d.%m.%Y").strftime("%Y-%m-%d")
    day_path = paths.facts_by_day / f"{iso}.json"
    if not day_path.is_file():
        return {}
    content = build_den_content(day_path, paths, link_mode="pages")
    out: dict[str, list[str]] = {}
    for item in content.items:
        texts: list[str] = []
        for field in ARTICLE_PROSE_FIELDS:
            for m in re.finditer(
                r'<a\b[^>]*class="steno-link"[^>]*>(.*?)</a>', getattr(item, field, "") or "", re.S
            ):
                texts.append(_norm_link_text(re.sub(r"<[^>]+>", "", m.group(1))))
        out[item.slug] = texts
    return out


def _link_phrase_coverage(paths: SchuzePaths, datum_unl: str, slugs: list[str]) -> dict[str, Any]:
    """Kolik citací se steno_id má ve *vykresleném* článku odkaz (dřív se měřilo
    proti surovým facts, takže fráze s číslicemi hlásily 100 % a na webu chyběly)."""
    from svejk.build.steno_sources import _phrase_variants

    rendered = _rendered_link_texts(paths, datum_unl)
    total = linked = 0
    missing: list[str] = []
    for slug in slugs:
        fp = paths.facts_by_topic / f"{slug}.json"
        if not fp.is_file():
            continue
        data = read_json(fp)
        if not data.get("publikovat", True):
            continue
        links = rendered.get(slug, [])
        cards = [
            _norm_citace(data.get(f"{prefix}_text") or "")
            for prefix in ("citace", "citace2", "citace3", "citace4")
        ]
        for i, f in enumerate(data.get("fakty") or []):
            if not isinstance(f, dict):
                continue
            if not (f.get("steno_id") or "").strip():
                continue
            total += 1
            phrase = (f.get("link_phrase") or "").strip()
            variants = [_norm_link_text(v) for v in _phrase_variants(phrase)] if phrase else []
            quote = _norm_citace(f.get("citace") or "")
            if any(v in t or t in v for v in variants for t in links if t):
                linked += 1
            elif quote and any(_same_quote(quote, c) or (len(quote) >= 15 and quote in c) for c in cards if c):
                linked += 1  # citace v kartě článku má vlastní odkaz na steno
            else:
                missing.append(f"{slug}[{i}]")
    pct = round(100 * linked / total, 1) if total else 100.0
    return {"total": total, "linked": linked, "percent": pct, "missing": missing}


def _norm_citace(text: str) -> str:
    import re

    t = (text or "").lower().replace("\n", " ")
    for ch in "„“\"'":
        t = t.replace(ch, "")
    # citace ve facts mívá pomlčku, karta na webu čárku
    t = re.sub(r"\s*[\u2013\u2014-]\s+", ", ", t)
    t = re.sub(r"\s+", " ", t).strip(" .,;:!?")
    return t


def _same_quote(a: str, b: str) -> bool:
    """Stejná věta, nebo jedna je v druhé a kratší má aspoň 40 znaků."""
    if not a or not b:
        return False
    if a == b:
        return True
    short, long = (a, b) if len(a) <= len(b) else (b, a)
    return len(short) >= 40 and short in long


def jazykolam_duplicates(jazykolam: str, quotes: list[str]) -> list[str]:
    """Citát dne, který už je citátem v článku."""
    needle = _norm_citace(jazykolam)
    if not needle:
        return []
    hit: list[str] = []
    for quote in quotes:
        if _same_quote(needle, _norm_citace(quote)):
            hit.append(quote)
    return hit


def _jazykolam_duplicate_quotes(
    paths: SchuzePaths,
    day: dict[str, Any],
    slugs: list[str],
) -> list[str]:
    j = day.get("jazykolam") or {}
    text = (j.get("text") or "").strip() if isinstance(j, dict) else ""
    if not text:
        return []
    quotes: list[str] = []
    for slug in slugs:
        fp = paths.facts_by_topic / f"{slug}.json"
        if not fp.is_file():
            continue
        data = read_json(fp)
        if not data.get("publikovat", True):
            continue
        citace_text = (data.get("citace_text") or "").strip()
        if citace_text:
            quotes.append(citace_text)
        for f in data.get("fakty") or []:
            if isinstance(f, dict) and (f.get("citace") or "").strip():
                quotes.append(f["citace"].strip())
    return jazykolam_duplicates(text, quotes)


def _citace_norm(text: str) -> str:
    import re

    t = (text or "").replace("\u00a0", " ")
    t = re.sub(r"[„“”\"'‚‘’]", "", t)
    # Dlouhé pomlčky ze stena se v citacích nahrazují čárkou (build je zakazuje).
    t = re.sub(r"\s*(?:[\u2013\u2014]|\s-\s|,)\s*", " , ", t)
    t = re.sub(r"\*\*\* Neprošlo jazykovou korekturou, neautorizováno!", " ", t)
    return " ".join(t.split()).lower().strip(" .,;:")


def _citace_in_steno(paths: SchuzePaths, slugs: list[str]) -> dict[str, Any]:
    """Citace ve facts je doslovně ve stenozáznamu (i z jiné schůze téhož dne).

    Porovnává se bez rozdílu v mezerách, uvozovkách a pomlčkách; dřív hlásila
    nedoslovné citace jen kvůli „–“ vs „-“ nebo kvůli steno_id z jiné schůze.
    """
    from svejk.build.steno_sources import _load_steno_index, _paths_for_steno

    indexes: dict[tuple[int, int], dict[str, dict]] = {}
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
            sp = _paths_for_steno(paths, sid)
            key = (sp.obdobi, sp.schuze)
            if key not in indexes:
                indexes[key] = _load_steno_index(sp)
            rec = indexes[key].get(sid)
            if rec is None:
                continue  # záznam lokálně není (CI bez stena): nehodnotit
            checked += 1
            if _citace_norm(cit) in _citace_norm(rec.get("text") or ""):
                ok += 1
            else:
                bad.append(f"{slug}[{i}]")
    pct = round(100 * ok / checked, 1) if checked else 100.0
    return {"checked": checked, "ok": ok, "percent": pct, "bad": bad}


def run_edition_metrics(
    paths: SchuzePaths,
    den: str,
    *,
    save: bool = True,
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
    quote_dupes = _jazykolam_duplicate_quotes(paths, day, slugs)
    if quote_dupes:
        errors.append("citát dne je stejný jako citát v článku")
    for slug, verdikt, vysledek in _verdikt_rozpory(paths, slugs):
        errors.append(f"{slug}: verdikt {verdikt} odporuje hlasování ({vysledek})")
    shared = _shared_topic_days(paths, iso, slugs)
    for slug, days in sorted(shared.items()):
        errors.append(f"téma {slug} je i ve vydání {', '.join(days)} (úprava změní oba dny)")
    metrics = {
        "state": effective_state(doc, paths),
        "stale": fingerprint_stale(doc, paths),
        "link_phrase_coverage": link_cov,
        "citace_in_steno": citace,
        "party_labels": party_labels,
        "generic_topic_count": len(weak_slugs),
        "steno_passages": steno_blocks,
        "steno_missing_article_phrase": steno_missing,
        "jazykolam_duplicates": quote_dupes,
        "shared_topics": shared,
        "ok": not errors,
        "errors": errors,
    }
    if save:
        doc["metrics"] = metrics
        from svejk.edition.state import save_edition

        save_edition(paths, iso, doc)
    return metrics


def format_edition_review(
    paths: SchuzePaths,
    den: str,
    *,
    as_json: bool = False,
    save: bool = True,
    with_metrics: bool = False,
):
    import json

    datum_unl, iso, _ = resolve_edition_day(paths, den)
    metrics = run_edition_metrics(paths, den, save=save)
    day_report = format_day_review(paths, den)
    if as_json:
        out = json.dumps(
            {"metrics": metrics, "review": day_report},
            ensure_ascii=False,
            indent=2,
        )
        return (out, metrics) if with_metrics else out
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
    out = "\n".join(lines)
    return (out, metrics) if with_metrics else out
