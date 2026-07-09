"""Sestavení novin-dlouhe z uložených facts/."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from svejk.build.day_content import (
    DenContent,
    _sanitize_vysledek_export,
    build_den_content,
    vysledek_radky,
)
from svejk.cislo_slovy import nahrad_cisla_v_textu
from svejk.strings import load_strings
from svejk.text_norm import bez_dlouhych_pomlc, lcfirst_preserve_proper, ma_dlouhou_pomlcku
from svejk.build.html import (
    render_den_html,
    render_steno_sources_html,
    render_smlouvy_html,
    render_vyznamenani_table_html,
    render_recnici_table_html,
)
from svejk.build.vyznamenani_neprosli import (
    VyznamenaniKind,
    inject_mean_links_md,
    load_vyznamenani,
    resolve_vyznamenani_page_links,
    vyznamenani_href,
)
from svejk.build.witty import rozdel_kuriozitu_label
from svejk.build.io import read_json
from svejk.noviny import HLAVICKA_LISTU, _datum_cesky, _new_state
from svejk.paths import SchuzePaths
from svejk.build.steno_sources import has_steno_sources, write_steno_refs
from svejk.build.recnici import has_recnici
from svejk.build.mezin_smlouvy import has_smlouvy


def _listy_markdown(listy: dict) -> list[str]:
    lines = ["## SNĚMOVNÍ LISTY", ""]
    meta = (listy.get("meta") or "").strip()
    deck = (listy.get("deck") or "").strip()
    if meta:
        lines.extend([meta, ""])
    if deck:
        lines.extend([f"**{deck}**", ""])
    for section in listy.get("sections") or []:
        heading = (section.get("heading") or "").strip()
        if heading:
            lines.extend([f"### {heading}", ""])
        for para in section.get("paragraphs") or []:
            text = (para or "").strip()
            if text:
                lines.extend([text, ""])
        bullets = section.get("bullets") or []
        if bullets:
            for bullet in bullets:
                text = (bullet or "").strip()
                if text:
                    lines.append(f"* {text}")
            lines.append("")
    footer = (listy.get("footer") or "").strip()
    if footer:
        lines.extend(["", f"*{footer}*"])
    return lines


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
        f"**{content.den.capitalize()} {nahrad_cisla_v_textu(_datum_cesky(content.datum))}** · s{paths.schuze}",
        "",
        *_dnesni_ucet_radky(content.dnesni_ucet),
        "",
    ]
    if content.snemovni_listy:
        lines.extend(_listy_markdown(content.snemovni_listy))
        lines.append("")

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
                lead = f"Poslušně hlásím, že {lcfirst_preserve_proper(intro)}"
            state["poslusne_count"] = 1
            prvni = False

        co_znamena = item.mean.strip() if item.mean else item.dopad
        if item.mean_links:
            link_pairs: list[tuple[str, str]] = []
            for phrase, page in item.mean_links:
                if page not in ("neprosli", "prosli", "zvoleni"):
                    continue
                kind: VyznamenaniKind = page  # type: ignore[assignment]
                if not load_vyznamenani(paths, content.datum, kind):
                    continue
                href = vyznamenani_href(
                    paths.obdobi,
                    paths.schuze,
                    content.datum,
                    kind,
                    link_mode="file",
                )
                link_pairs.append((phrase, href))
            if link_pairs:
                lead = inject_mean_links_md(lead, link_pairs)
                co_znamena = inject_mean_links_md(co_znamena, link_pairs)
        heading = (
            "\n".join(item.nadpis_radky)
            if len(item.nadpis_radky) > 1
            else item.nadpis
        )
        lines.extend(
            [
                f"## {heading}",
                "",
            ]
        )
        lines.extend([lead, ""])
        if item.citace_text:
            lines.extend([f"> „{item.citace_text}“", ""])
            if item.citace_autor:
                lines.append(f"> {item.citace_autor}")
            lines.append("")
        if item.lead_tail and item.kuriozita:
            lines.extend([f'<div class="kuriozita-box">{item.kuriozita}</div>', ""])
            lines.extend([item.lead_tail, ""])
        elif item.lead_tail:
            lines.extend([item.lead_tail, ""])
        if item.pointa:
            lines.extend([item.pointa, ""])
        mean_label = load_strings()["edition"]["mean_label"]
        lines.extend([f"**{mean_label}** <strong>{co_znamena}</strong>", ""])
        if item.kuriozita and not item.lead_tail:
            label, body = rozdel_kuriozitu_label(item.kuriozita)
            if label:
                lines.extend(["", f"**{label}** {body}"])
            else:
                lines.extend(["", item.kuriozita])
        if item.kuriozita_links:
            from svejk.build.mezin_smlouvy import resolve_smlouvy_page_links
            from svejk.build.recnici import resolve_recnici_page_links

            nav = resolve_vyznamenani_page_links(
                paths,
                content.datum,
                item.kuriozita_links,
                obdobi=paths.obdobi,
                schuze=paths.schuze,
                link_mode="file",
            ) + resolve_recnici_page_links(
                paths,
                content.datum,
                item.kuriozita_links,
                obdobi=paths.obdobi,
                schuze=paths.schuze,
                link_mode="file",
            ) + resolve_smlouvy_page_links(
                paths,
                content.datum,
                item.kuriozita_links,
                obdobi=paths.obdobi,
                schuze=paths.schuze,
                link_mode="file",
            )
            if nav:
                md_links = " · ".join(f"[{label}]({href})" for label, href in nav)
                lines.extend(["", md_links])
        lines.append("")

    lines.append("## Výsledek dne")
    lines.append("")
    for radek in vysledek_radky(content, paths, day_path):
        lines.append(_sanitize_vysledek_export(radek))
    lines.append("")
    lines.append(f"**{content.zaver}**")

    return "\n".join(lines).strip()


def render_den_z_facts(day_path: Path, paths: SchuzePaths, *, state: dict | None = None) -> str:
    if state is None:
        state = _new_state()
    content = build_den_content(day_path, paths, state=state, link_mode="file")
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
        content = build_den_content(day_path, paths, state=state, link_mode="file")
        md_out = paths.noviny_dlouhe_md(datum)
        md_body = render_den_markdown(content, paths, day_path, state=state) + "\n"
        md_out.write_text(md_body, encoding="utf-8")
        written_md.append(str(md_out))

        html_out = paths.noviny_dlouhe_html(datum)
        html_body = render_den_html(content, paths, day_path)
        html_out.write_text(html_body, encoding="utf-8")
        written_html.append(str(html_out))

        for kind in ("neprosli", "prosli", "zvoleni"):
            table_html = render_vyznamenani_table_html(
                paths, datum, kind, link_mode="file"
            )
            if not table_html:
                continue
            table_out = paths.vyznamenani_html(datum, kind)
            table_out.write_text(table_html, encoding="utf-8")
            written_html.append(str(table_out))

        if has_steno_sources(paths, datum):
            write_steno_refs(paths)
            steno_html = render_steno_sources_html(paths, datum, link_mode="file")
            if steno_html:
                steno_out = paths.steno_zdroje_html(datum)
                steno_out.write_text(steno_html, encoding="utf-8")
                written_html.append(str(steno_out))

        if has_recnici(paths, datum):
            recnici_html = render_recnici_table_html(paths, datum, link_mode="file")
            if recnici_html:
                recnici_out = paths.recnici_html(datum)
                recnici_out.write_text(recnici_html, encoding="utf-8")
                written_html.append(str(recnici_out))

        if has_smlouvy(paths, datum):
            smlouvy_html = render_smlouvy_html(paths, datum, link_mode="file")
            if smlouvy_html:
                smlouvy_out = paths.smlouvy_html(datum)
                smlouvy_out.write_text(smlouvy_html, encoding="utf-8")
                written_html.append(str(smlouvy_out))

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
