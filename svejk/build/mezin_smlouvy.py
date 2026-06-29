"""Doplňková stránka mezinárodních smluv u vydání (odkazy do stenoprotokolu)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from svejk.build.io import read_json
from svejk.build.nav import smlouvy_pages_href
from svejk.build.steno_sources import inject_steno_links
from svejk.paths import SchuzePaths


def _day_path(paths: SchuzePaths, datum_unl: str) -> Path:
    d = datetime.strptime(datum_unl, "%d.%m.%Y")
    return paths.facts_by_day / f"{d.strftime('%Y-%m-%d')}.json"


def load_smlouvy_topic(paths: SchuzePaths, datum_unl: str) -> dict[str, Any] | None:
    day_path = _day_path(paths, datum_unl)
    if not day_path.is_file():
        return None
    slug = (read_json(day_path).get("smlouvy_slug") or "").strip()
    if not slug:
        return None
    fp = paths.facts_by_topic / f"{slug}.json"
    if not fp.is_file():
        return None
    return read_json(fp)


def has_smlouvy(paths: SchuzePaths, datum_unl: str) -> bool:
    topic = load_smlouvy_topic(paths, datum_unl)
    return bool(topic and topic.get("smlouvy"))


def smlouvy_link_phrases(topic: dict[str, Any]) -> list[str]:
    raw = topic.get("link_phrases") or ["šest mezinárodních smluv"]
    return [p.strip() for p in raw if (p or "").strip()]


def append_smlouvy_steno_block(
    blocks: list[Any],
    *,
    paths: SchuzePaths,
    day: dict[str, Any],
    steno_by_id: dict[str, dict[str, Any]],
    psp_resolver: Any,
    num: int,
    global_passage_idx: int,
) -> tuple[int, int]:
    """Přidá blok smluv do collect_steno_sources; vrátí (num, global_passage_idx)."""
    from svejk.build.steno_sources import StenoTopicBlock, _passage_from_fact

    slug = (day.get("smlouvy_slug") or "").strip()
    if not slug:
        return num, global_passage_idx
    fp = paths.facts_by_topic / f"{slug}.json"
    if not fp.is_file():
        return num, global_passage_idx
    topic = read_json(fp)
    entries = topic.get("smlouvy") or []
    if not entries:
        return num, global_passage_idx

    num += 1
    title = (topic.get("nadpis") or "Mezinárodní smlouvy").strip()
    block = StenoTopicBlock(slug=slug, title=title, num=num)
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        steno_id = (entry.get("steno_id") or "").strip()
        if not steno_id:
            continue
        fact = {
            "source": "steno",
            "steno_id": steno_id,
            "citace": (entry.get("citace") or "").strip(),
            "text": (entry.get("text") or "").strip(),
            "link_phrase": (entry.get("link_phrase") or "").strip(),
        }
        passage = _passage_from_fact(
            fact,
            paths=paths,
            steno_by_id=steno_by_id,
            topic_slug=slug,
            topic_title=title,
            article_num=num,
            passage_idx=global_passage_idx,
            psp_resolver=psp_resolver,
        )
        global_passage_idx += 1
        if passage:
            block.passages.append(passage)
    if block.passages:
        blocks.append(block)
    return num, global_passage_idx


def psp_href_for_entry(
    paths: SchuzePaths,
    entry: dict[str, Any],
) -> str:
    from svejk.build.steno_sources import resolve_psp_url_for_steno

    steno_id = (entry.get("steno_id") or "").strip()
    if not steno_id:
        return ""
    citace = (entry.get("citace") or "").strip()
    return resolve_psp_url_for_steno(paths, steno_id, citace)


def smlouvy_page_items(
    paths: SchuzePaths,
    datum_unl: str,
    *,
    obdobi: int,
    link_mode: str,
    base_path: str = "",
) -> list[dict[str, str]]:
    topic = load_smlouvy_topic(paths, datum_unl)
    if not topic:
        return []
    out: list[dict[str, str]] = []
    for entry in topic.get("smlouvy") or []:
        if not isinstance(entry, dict):
            continue
        steno_id = (entry.get("steno_id") or "").strip()
        psp_href = psp_href_for_entry(paths, entry) if steno_id else ""
        out.append(
            {
                "stat": (entry.get("stat") or "").strip(),
                "tema": (entry.get("tema") or "").strip(),
                "text": (entry.get("text") or "").strip(),
                "recnik": (entry.get("recnik") or entry.get("rečník") or "").strip(),
                "psp_href": psp_href,
            }
        )
    return out


def resolve_smlouvy_page_links(
    paths: SchuzePaths,
    datum_unl: str,
    links: list[tuple[str, str]],
    *,
    obdobi: int,
    schuze: int,
    link_mode: str,
    base_path: str = "",
) -> list[tuple[str, str]]:
    if not has_smlouvy(paths, datum_unl):
        return []
    out: list[tuple[str, str]] = []
    for label, page in links:
        if page != "smlouvy":
            continue
        href = smlouvy_pages_href(obdobi, schuze, datum_unl, base_path)
        out.append((label, href))
    return out


def apply_smlouvy_page_links(
    content: Any,
    paths: SchuzePaths,
    *,
    obdobi: int | None = None,
    link_mode: str = "file",
    base_path: str = "",
) -> None:
    topic = load_smlouvy_topic(paths, content.datum)
    if not topic:
        return
    ob = obdobi if obdobi is not None else paths.obdobi
    href = smlouvy_pages_href(ob, paths.schuze, content.datum, base_path)
    links = [(p, href) for p in smlouvy_link_phrases(topic)]
    if not links:
        return
    for field in ("dnesni_ucet", "result_note", "zaver", "zaver_body"):
        val = getattr(content, field, None)
        if val:
            setattr(content, field, inject_steno_links(val, links))
    for item in content.items:
        item.lead = inject_steno_links(item.lead, links)
        item.mean = inject_steno_links(item.mean, links)
        item.kuriozita = inject_steno_links(item.kuriozita, links)
