"""Shared import path setup for tests (unittest and pytest)."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "server-backend"
COLLECTION_DIR = BACKEND_DIR / "collection"

for path in (BACKEND_DIR, COLLECTION_DIR):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)
