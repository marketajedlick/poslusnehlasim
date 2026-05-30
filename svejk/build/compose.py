"""Sestavení novin-dlouhe z uložených facts/."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from svejk.build.day_content import DenContent, build_den_content, vysledek_radky
from svejk.build.html import render_den_html
from svejk.build.io import read_json
from svejk.noviny import HLAVICKA_LISTU, _datum_cesky, _new_state
from svejk.paths import SchuzePaths


def render_den_markdown(
    content: DenContent,
    paths: SchuzePaths,
    day_path: Path,
    *,
    state: dict,
) -> str:
    lines = [
        f"# {HLAVICKA_LISTU}",
        "",
        f"**{content.den.capitalize()} {_datum_cesky(content.datum)}**",
        "",
        f"**Dnešní účet:** {content.dnesni_ucet}",
        "",
    ]

    prvni = True
    for item in content.items:
        lead = item.parliament_lead
        if prvni:
            lead = f"Poslušně hlásím, že {lead[0].lower()}{lead[1:]}"
            state["poslusne_count"] = 1
            prvni = False

        lines.extend(
            [
                f"## {item.nadpis}",
                "",
                lead,
                "",
                "### Co to znamená?",
                "",
                item.dopad,
                "",
            ]
        )

    lines.append("## Výsledek dne")
    lines.append("")
    for radek in vysledek_radky(content, paths, day_path):
        lines.append(radek)
    lines.append("")
    lines.append(f"**{content.zaver}**")

    return "\n".join(lines).strip()


def render_den_z_facts(day_path: Path, paths: SchuzePaths, *, state: dict | None = None) -> str:
    if state is None:
        state = _new_state()
    content = build_den_content(day_path, paths, state=state)
    return render_den_markdown(content, paths, day_path, state=state)


def run_compose(
    paths: SchuzePaths,
    *,
    den: str | None = None,
) -> dict[str, Any]:
    paths.ensure_dirs()
    written_md: list[str] = []
    written_html: list[str] = []

    def _compose_one(day_path: Path, datum: str) -> None:
        state = _new_state()
        content = build_den_content(day_path, paths, state=state)
        md_out = paths.noviny_dlouhe_md(datum)
        md_out.write_text(
            render_den_markdown(content, paths, day_path, state=state) + "\n",
            encoding="utf-8",
        )
        written_md.append(str(md_out))

        html_out = paths.noviny_dlouhe_html(datum)
        html_out.write_text(
            render_den_html(content, paths, day_path),
            encoding="utf-8",
        )
        written_html.append(str(html_out))

    if den:
        from svejk.timeline import normalize_day

        d_unl = normalize_day(den)
        d = datetime.strptime(d_unl, "%d.%m.%Y")
        day_path = paths.facts_by_day / f"{d.strftime('%Y-%m-%d')}.json"
        if not day_path.is_file():
            raise FileNotFoundError(f"Chybí index dne: {day_path}")
        _compose_one(day_path, d_unl)
        return {"days": 1, "files": written_md, "html_files": written_html}

    if not paths.facts_by_day.is_dir():
        raise FileNotFoundError(f"Chybí {paths.facts_by_day} — spusť extract")

    for day_path in sorted(paths.facts_by_day.glob("*.json")):
        day = read_json(day_path)
        _compose_one(day_path, day["datum"])

    return {"days": len(written_md), "files": written_md, "html_files": written_html}
