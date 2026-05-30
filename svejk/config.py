"""Konfigurace z proměnných prostředí."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{ROOT / 'svejk.db'}")
PSP_DATA_DIR = Path(os.environ.get("PSP_DATA_DIR", ROOT))
HLIDAC_TOKEN = os.environ.get("HLIDAC_TOKEN", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
PSP_ORGAN_ID = os.environ.get("PSP_ORGAN_ID", "174")
