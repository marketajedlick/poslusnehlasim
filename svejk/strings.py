"""Texty UI webu a drobné české formátovací helpery."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_STRINGS_PATH = Path(__file__).resolve().parent / "strings.json"

_MESICE = (
    "leden",
    "únor",
    "březen",
    "duben",
    "květen",
    "červen",
    "červenec",
    "srpen",
    "září",
    "říjen",
    "listopad",
    "prosinec",
)


def month_label(month: int, year: int) -> str:
    return f"{_MESICE[month - 1]} {year}"


@lru_cache(maxsize=1)
def load_strings() -> dict[str, Any]:
    return json.loads(_STRINGS_PATH.read_text(encoding="utf-8"))


def footer_closings() -> tuple[str, ...]:
    t = load_strings()
    closings = t.get("footer", {}).get("closings")
    if isinstance(closings, list) and closings:
        return tuple(str(x) for x in closings)
    return (
        "Poslušně hlásím, že dnešní vydání končí. Poslanci šli domů a my taky.",
    )


def footer_stats_line(n_editions: int, schuze_part: str) -> str:
    t = load_strings()
    template = t.get("footer", {}).get("stats", "{editions} vydání • {schuze} • 100 % veřejná data")
    return template.format(editions=n_editions, schuze=schuze_part)


def schuze_count_label(n_schuze: int) -> str:
    if n_schuze == 1:
        return "1 schůze"
    if 2 <= n_schuze <= 4:
        return f"{n_schuze} schůze"
    return f"{n_schuze} schůzí"
