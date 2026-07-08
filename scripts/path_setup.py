"""Add collection, scripts, and server-backend to sys.path for CLI entrypoints."""

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_ROOT = _SCRIPTS.parent
_COLLECTION = _ROOT / "server-backend" / "collection"
_BACKEND = _ROOT / "server-backend"

for _path in (_COLLECTION, _SCRIPTS, _BACKEND):
    text = str(_path)
    if text not in sys.path:
        sys.path.insert(0, text)
