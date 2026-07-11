"""Export sociálních assetů (carousel, IG caption)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from svejk.build.io import read_json
from svejk.build.og_image import (
    render_edition_og_image,
    render_edition_share_hero_image,
    render_share_hero_image,
)
from svejk.paths import SchuzePaths


def build_ig_caption(
    *,
    datum_unl: str,
    dnesni_ucet: str,
    zaver: str,
    site_url: str = "https://poslusnehlasim.cz",
) -> str:
    from datetime import datetime

    iso = datetime.strptime(datum_unl, "%d.%m.%Y").strftime("%Y-%m-%d")
    url = f"{site_url.rstrip('/')}/vydani/{iso}/"
    ucet = (dnesni_ucet or "").replace("\n", " ").strip()
    tail = (zaver or "").strip()
    if tail.lower().startswith("že "):
        tail = tail[3:].strip()
    lines = ["Poslušně hlásím"]
    if ucet:
        lines.append(ucet)
    if tail:
        lines.append(tail)
    lines.extend(["", url, "", "#snemovna #poslusnehlasim"])
    return "\n".join(lines)


def run_social_assets(
    paths: SchuzePaths,
    datum_unl: str,
    iso: str,
    assets_dir: Path,
    *,
    day_doc: dict[str, Any] | None = None,
) -> dict[str, Any]:
    assets_dir.mkdir(parents=True, exist_ok=True)
    day_path = paths.facts_by_day / f"{iso}.json"
    day = day_doc or (read_json(day_path) if day_path.is_file() else {})
    slugs = day.get("topic_slugs") or []
    first_nadpis = ""
    quotes: list[str] = []
    for slug in slugs:
        fp = paths.facts_by_topic / f"{slug}.json"
        if not fp.is_file():
            continue
        fact = read_json(fp)
        if not fact.get("publikovat", True):
            continue
        if not first_nadpis:
            first_nadpis = (fact.get("nadpis") or "").strip()
        cit = (fact.get("citace_text") or "").strip()
        if not cit:
            for f in fact.get("fakty") or []:
                if isinstance(f, dict) and (f.get("citace") or "").strip():
                    cit = (f.get("citace") or "").strip()
                    break
        if cit and len(cit) > 20:
            quotes.append(cit[:200])
        if len(quotes) >= 3:
            break

    og_path = render_edition_og_image(
        assets_dir,
        datum_unl=datum_unl,
        den=day.get("den") or "",
        dnesni_ucet=day.get("dnesni_ucet") or "",
        first_item_nadpis=first_nadpis,
        zaver=day.get("zaver") or "",
    )
    share_path = render_edition_share_hero_image(
        assets_dir,
        datum_unl=datum_unl,
        zaver=day.get("zaver") or "",
        zaver_body=day.get("dnesni_ucet") or "",
    )
    carousel_dir = assets_dir / "carousel"
    carousel_dir.mkdir(parents=True, exist_ok=True)
    carousel_files: list[str] = []
    ucet = (day.get("dnesni_ucet") or "").replace("\n", " ").strip()
    if ucet:
        p = render_share_hero_image(
            carousel_dir / "01-ucet.png",
            zaver_key="Dnešní účet",
            quote_body=ucet[:280],
        )
        carousel_files.append(str(p.name))
    for i, q in enumerate(quotes[:3], start=2):
        p = render_share_hero_image(
            carousel_dir / f"{i:02d}-citace.png",
            quote_body=q,
        )
        carousel_files.append(f"carousel/{p.name}")
    stats = day.get("stats") or {}
    skore = f"{stats.get('proslo', 0)}:{stats.get('zamitnuto', 0)}"
    if stats.get("pocet_hlas"):
        p = render_share_hero_image(
            carousel_dir / "05-skore.png",
            zaver_key="Skóre dne",
            quote_body=f"Zákony: {skore} · hlasování: {stats.get('pocet_hlas')}",
        )
        carousel_files.append(f"carousel/{p.name}")

    caption = build_ig_caption(
        datum_unl=datum_unl,
        dnesni_ucet=day.get("dnesni_ucet") or "",
        zaver=day.get("zaver") or "",
    )
    caption_path = assets_dir / "caption.txt"
    caption_path.write_text(caption + "\n", encoding="utf-8")

    return {
        "og": str(og_path),
        "share": str(share_path) if share_path else None,
        "carousel": carousel_files,
        "caption": str(caption_path),
    }
