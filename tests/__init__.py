"""Shared import path setup for tests (unittest and pytest)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
BACKEND_DIR = ROOT / "server-backend"

for path in (SCRIPTS_DIR, BACKEND_DIR):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)
