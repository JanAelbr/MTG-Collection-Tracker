"""Run the MTG Collection API with uvicorn."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = Path(__file__).resolve().parent
COLLECTION_DIR = BACKEND_DIR / "collection"

for path in (BACKEND_DIR, COLLECTION_DIR):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)

import uvicorn

from lib.port_util import free_listening_port

if __name__ == "__main__":
    free_listening_port(8000)
    uvicorn.run(
        "api.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        reload_dirs=[
            str(BACKEND_DIR / "api"),
            str(COLLECTION_DIR / "lib"),
            str(COLLECTION_DIR / "report"),
            str(COLLECTION_DIR / "util"),
        ],
    )
