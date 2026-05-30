"""Cesty k souborové vrstvě processed/{obdobi}-s{cislo}/."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from svejk.config import ROOT


def processed_root(base: Path | None = None) -> Path:
    import os

    return Path(os.environ.get("SVEJK_PROCESSED_DIR", base or ROOT / "processed"))


@dataclass(frozen=True)
class SchuzePaths:
    obdobi: int
    schuze: int
    root: Path

    @classmethod
    def create(cls, obdobi: int, schuze: int, base: Path | None = None) -> SchuzePaths:
        r = processed_root(base) / f"{obdobi}-s{schuze}"
        return cls(obdobi=obdobi, schuze=schuze, root=r)

    @property
    def manifest(self) -> Path:
        return self.root / "manifest.json"

    @property
    def raw(self) -> Path:
        return self.root / "raw"

    @property
    def votes_jsonl(self) -> Path:
        return self.raw / "votes.jsonl"

    @property
    def steno_jsonl(self) -> Path:
        return self.raw / "steno.jsonl"

    @property
    def aligned(self) -> Path:
        return self.root / "aligned"

    @property
    def topics_json(self) -> Path:
        return self.aligned / "topics.json"

    @property
    def facts(self) -> Path:
        return self.root / "facts"

    @property
    def facts_by_topic(self) -> Path:
        return self.facts / "by_topic"

    @property
    def facts_by_day(self) -> Path:
        return self.facts / "by_day"

    @property
    def out(self) -> Path:
        return self.root / "out"

    def noviny_dlouhe_dir(self) -> Path:
        return self.out / "noviny-dlouhe"

    def noviny_dlouhe_md(self, datum_unl: str) -> Path:
        """datum_unl = DD.MM.RRRR → soubor YYYY-MM-DD.md"""
        from datetime import datetime

        d = datetime.strptime(datum_unl, "%d.%m.%Y")
        return self.noviny_dlouhe_dir() / f"{d.strftime('%Y-%m-%d')}.md"

    def noviny_dlouhe_html(self, datum_unl: str) -> Path:
        """datum_unl = DD.MM.RRRR → soubor YYYY-MM-DD.html"""
        from datetime import datetime

        d = datetime.strptime(datum_unl, "%d.%m.%Y")
        return self.noviny_dlouhe_dir() / f"{d.strftime('%Y-%m-%d')}.html"

    def ensure_dirs(self) -> None:
        for p in (
            self.raw,
            self.aligned,
            self.facts_by_topic,
            self.facts_by_day,
            self.noviny_dlouhe_dir(),
        ):
            p.mkdir(parents=True, exist_ok=True)
