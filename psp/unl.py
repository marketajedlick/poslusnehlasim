"""Čtení UNL souborů PSP (Windows-1250, oddělovač |)."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

ENCODING = "cp1250"


def read_unl(path: Path) -> Iterator[list[str]]:
    """Načte UNL soubor po řádcích jako seznam polí."""
    with open(path, encoding=ENCODING, errors="replace") as f:
        for line in f:
            yield line.rstrip("\n").split("|")
