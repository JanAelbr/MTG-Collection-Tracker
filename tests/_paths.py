"""Add scripts/ and server-backend/ to sys.path for test modules."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

for sub in ("scripts", "server-backend"):
    path = str(ROOT / sub)
    if path not in sys.path:
        sys.path.insert(0, path)
