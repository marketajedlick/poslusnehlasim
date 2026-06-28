"""Konfigurace z proměnných prostředí."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SECRETS_ENV = ROOT / "secrets.env"


def load_secrets_env(path: Path | None = None) -> None:
    """Načte secrets.env; existující proměnné prostředí nepřepisuje."""
    env_path = path or SECRETS_ENV
    if not env_path.is_file():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        key, sep, value = line.partition("=")
        if not sep:
            continue
        key = key.strip()
        if not key or key in os.environ:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ[key] = value


load_secrets_env()

PSP_DATA_DIR = Path(os.environ.get("PSP_DATA_DIR", ROOT))
HLIDAC_TOKEN = (os.environ.get("HLIDAC_TOKEN") or "").strip()
PSP_ORGAN_ID = os.environ.get("PSP_ORGAN_ID", "174")
