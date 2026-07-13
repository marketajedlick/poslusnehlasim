"""Export tabulky poslanců a klubů z PSP open data."""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from psp.poslanci import _display_klub, load_poslanci


@dataclass(frozen=True)
class PoslanecRow:
    jmeno: str
    prijmeni: str
    klub: str
    zavorce: str

    @property
    def cele_jmeno(self) -> str:
        return f"{self.jmeno} {self.prijmeni}"


def build_poslanci_table(*, data_dir: Path | None = None) -> list[PoslanecRow]:
    rows = [
        PoslanecRow(
            jmeno=p.jmeno,
            prijmeni=p.prijmeni,
            klub=p.klub,
            zavorce=_display_klub(p),
        )
        for p in load_poslanci(data_dir=data_dir)
    ]
    rows.sort(key=lambda r: (r.klub, r.prijmeni, r.jmeno))
    return rows


def club_summary(rows: list[PoslanecRow]) -> list[tuple[str, int]]:
    counts = Counter(r.klub for r in rows)
    return sorted(counts.items(), key=lambda x: (-x[1], x[0]))


def format_csv(rows: list[PoslanecRow]) -> str:
    from io import StringIO

    buf = StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["jmeno", "prijmeni", "klub", "zavorce"])
    for row in rows:
        writer.writerow([row.jmeno, row.prijmeni, row.klub, row.zavorce])
    return buf.getvalue()


def format_markdown(rows: list[PoslanecRow]) -> str:
    lines = [
        "# Poslanci a kluby (PSP open data)",
        "",
        "## Počty podle klubu",
        "",
        "| Klub | Počet |",
        "| --- | ---: |",
    ]
    for klub, count in club_summary(rows):
        lines.append(f"| {klub} | {count} |")
    lines.extend(
        [
            "",
            f"Celkem: **{len(rows)}** poslanců.",
            "",
            "## Tabulka",
            "",
            "| Jméno | Klub | Do závorky v článku |",
            "| --- | --- | --- |",
        ]
    )
    for row in rows:
        lines.append(f"| {row.cele_jmeno} | {row.klub} | ({row.zavorce}) |")
    lines.append("")
    return "\n".join(lines)


def export_csv(path: Path, *, data_dir: Path | None = None) -> Path:
    rows = build_poslanci_table(data_dir=data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(format_csv(rows), encoding="utf-8")
    return path


def export_markdown(path: Path, *, data_dir: Path | None = None) -> Path:
    rows = build_poslanci_table(data_dir=data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(format_markdown(rows), encoding="utf-8")
    return path
