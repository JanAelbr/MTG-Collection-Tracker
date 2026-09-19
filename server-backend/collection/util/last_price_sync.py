import json
from datetime import datetime, timezone
from pathlib import Path

from lib.config import DATA_DIR

LAST_PRICE_SYNC_CACHE = DATA_DIR / "last_price_sync.json"


def empty_price_sync_movers() -> dict:
    return {
        "absolute": {"risers": [], "fallers": []},
        "relative": {"risers": [], "fallers": []},
    }


def _pair(raw) -> dict:
    if not isinstance(raw, dict):
        return {"risers": [], "fallers": []}
    return {
        "risers": list(raw.get("risers") or []),
        "fallers": list(raw.get("fallers") or []),
    }


def normalize_price_sync_movers(raw) -> dict:
    empty = empty_price_sync_movers()
    if not isinstance(raw, dict):
        return empty
    if "absolute" in raw or "relative" in raw:
        return {
            "absolute": _pair(raw.get("absolute")),
            "relative": _pair(raw.get("relative")),
        }
    pair = _pair(raw)
    return {"absolute": pair, "relative": pair}


def movers_have_rows(movers: dict | None) -> bool:
    payload = normalize_price_sync_movers(movers)
    for view in (payload["absolute"], payload["relative"]):
        if view["risers"] or view["fallers"]:
            return True
    return False


def save_last_price_sync(payload: dict, *, path: Path | None = None) -> dict:
    target = path or LAST_PRICE_SYNC_CACHE
    target.parent.mkdir(parents=True, exist_ok=True)
    stored = {
        "syncedAt": payload.get("syncedAt") or datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "applied": bool(payload.get("applied")),
        "pricesUnchanged": bool(payload.get("pricesUnchanged")),
        "message": payload.get("message") or "",
        "movers": normalize_price_sync_movers(payload.get("movers")),
        "cards": list(payload.get("cards") or []),
    }
    tmp = target.with_name(f"{target.name}.tmp")
    tmp.write_text(json.dumps(stored, indent=2), encoding="utf-8")
    tmp.replace(target)
    return stored


def load_last_price_sync(*, path: Path | None = None) -> dict | None:
    target = path or LAST_PRICE_SYNC_CACHE
    if not target.is_file():
        return None
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    return {
        "syncedAt": raw.get("syncedAt") or "",
        "applied": bool(raw.get("applied")),
        "pricesUnchanged": bool(raw.get("pricesUnchanged")),
        "message": raw.get("message") or "",
        "movers": normalize_price_sync_movers(raw.get("movers")),
        "cards": list(raw.get("cards") or []),
    }
