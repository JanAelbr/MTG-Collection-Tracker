"""Run the MTG Collection API with uvicorn."""

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = Path(__file__).resolve().parent
COLLECTION_DIR = BACKEND_DIR / "collection"
SCRIPTS_DIR = REPO_ROOT / "scripts"

for path in (BACKEND_DIR, COLLECTION_DIR, SCRIPTS_DIR):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)

import uvicorn

from lib.port_util import free_listening_port


def _resolve_host() -> str:
    raw = (os.environ.get("MTG_HOST") or "127.0.0.1").strip().lower()
    if raw in {"lan", "0.0.0.0", "*"}:
        return "0.0.0.0"
    return raw or "127.0.0.1"


def _lan_tls_kwargs(host: str) -> dict:
    if host != "0.0.0.0":
        return {}
    if os.environ.get("MTG_LAN_HTTP", "").strip().lower() in {"1", "true", "yes", "on"}:
        return {}
    from ensure_lan_tls import ensure_lan_tls

    cert_path, key_path = ensure_lan_tls(REPO_ROOT / "data" / "lan_tls")
    return {
        "ssl_certfile": str(cert_path),
        "ssl_keyfile": str(key_path),
    }


if __name__ == "__main__":
    host = _resolve_host()
    free_listening_port(8000)
    uvicorn.run(
        "api.main:app",
        host=host,
        port=8000,
        reload=True,
        reload_dirs=[
            str(BACKEND_DIR / "api"),
            str(COLLECTION_DIR / "lib"),
            str(COLLECTION_DIR / "report"),
            str(COLLECTION_DIR / "util"),
        ],
        **_lan_tls_kwargs(host),
    )
