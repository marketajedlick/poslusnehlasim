"""Sestavení novin-dlouhe z uložených facts/."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from svejk.build.day_content import DenContent, build_den_content, vysledek_radky
from svejk.cislo_slovy import nahrad_cisla_v_textu
from svejk.text_norm import bez_dlouhych_pomlc
from svejk.build.html import render_den_html
from svejk.build.io import read_json
from svejk.noviny import HLAVICKA_LISTU, _datum_cesky, _new_state
from svejk.paths import SchuzePaths
from svejk.text_norm import ma_dlouhou_pomlcku


def _dnesni_ucet_radky(ucet: str) -> list[str]:
    text = (ucet or "").strip()
    if not text:
        return ["**Dnešní účet:**"]
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return ["**Dnešní účet:**"]
    out = [f"**Dnešní účet:** {lines[0]}"]
    out.extend(lines[1:])
    return out


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
        f"**{content.den.capitalize()} {nahrad_cisla_v_textu(_datum_cesky(content.datum))}**",
        "",
        *_dnesni_ucet_radky(content.dnesni_ucet),
        "",
    ]

    prvni = True
    for item in content.items:
        intro = (item.lead or item.parliament_lead).strip()
        if (
            prvni
            and not item.has_custom_lead
            and item.parliament_lead
            and "hlasován" in item.parliament_lead.lower()
        ):
            intro = item.parliament_lead.strip()
        lead = intro
        if prvni:
            if not re.match(r"^poslušně\s+hlásím", intro, re.I):
                lead = f"Poslušně hlásím, že {intro[0].lower()}{intro[1:]}"
            state["poslusne_count"] = 1
            prvni = False

        co_znamena = item.mean.strip() if item.mean else item.dopad
        lines.extend(
            [
                f"## {item.nadpis}",
                "",
                lead,
                "",
                "### Co to znamená?",
                "",
                co_znamena,
                "",
            ]
        )

    lines.append("## Výsledek dne")
    lines.append("")
    for radek in vysledek_radky(content, paths, day_path):
        lines.append(nahrad_cisla_v_textu(bez_dlouhych_pomlc(radek)))
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
        md_body = render_den_markdown(content, paths, day_path, state=state) + "\n"
        md_out.write_text(md_body, encoding="utf-8")
        written_md.append(str(md_out))

        html_out = paths.noviny_dlouhe_html(datum)
        html_body = render_den_html(content, paths, day_path)
        html_out.write_text(html_body, encoding="utf-8")
        written_html.append(str(html_out))

        for out_path, body in ((md_out, md_body), (html_out, html_body)):
            if ma_dlouhou_pomlcku(body):
                raise ValueError(
                    f"Zakázaná dlouhá pomlčka (—/–) ve výstupu {out_path.name}, oprav zdrojové texty."
                )

    if den:
        from svejk.timeline import resolve_schuze_den

        d_unl, day_path = resolve_schuze_den(paths, den)
        if not day_path.is_file():
            raise FileNotFoundError(f"Chybí index dne: {day_path}")
        _compose_one(day_path, d_unl)
        return {"days": 1, "files": written_md, "html_files": written_html}

    if not paths.facts_by_day.is_dir():
        raise FileNotFoundError(f"Chybí {paths.facts_by_day}, spusť extract")

    for day_path in sorted(paths.facts_by_day.glob("*.json")):
        day = read_json(day_path)
        _compose_one(day_path, day["datum"])

    return {"days": len(written_md), "files": written_md, "html_files": written_html}
