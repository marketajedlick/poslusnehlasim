"""Parsování data vydání."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from svejk.paths import SchuzePaths
from svejk.timeline import resolve_schuze_den


def resolve_edition_day(paths: SchuzePaths, den: str) -> tuple[str, str, Path]:
    """Vrátí (datum_unl DD.MM.RRRR, iso YYYY-MM-DD, day_json_path)."""
    d_unl, day_path = resolve_schuze_den(paths, den)
    iso = datetime.strptime(d_unl, "%d.%m.%Y").strftime("%Y-%m-%d")
    return d_unl, iso, day_path
