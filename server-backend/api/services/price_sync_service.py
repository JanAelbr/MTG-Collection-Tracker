import sqlite3
import threading
from datetime import datetime, timezone

from util.price_history import load_last_updated_display, prices_are_outdated

_lock = threading.Lock()
_state = {
    "status": "idle",
    "started_at": None,
    "finished_at": None,
    "message": None,
    "error": None,
}


class PriceSyncError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _run_price_sync() -> None:
    try:
        from update_prices import update_cardmarket_prices_only

        update_cardmarket_prices_only()
        from api.cache import bump_cache_epoch
        from api.services.pricing_service import refresh_guide_cache

        refresh_guide_cache()
        bump_cache_epoch()
        with _lock:
            _state["status"] = "completed"
            _state["finished_at"] = _utc_now()
            _state["message"] = "Price sync completed"
            _state["error"] = None
    except Exception as exc:
        with _lock:
            _state["status"] = "failed"
            _state["finished_at"] = _utc_now()
            _state["message"] = "Price sync failed"
            _state["error"] = str(exc)


def start_price_sync() -> dict:
    with _lock:
        if _state["status"] == "running":
            raise PriceSyncError("Price sync is already running", status_code=409)
        _state["status"] = "running"
        _state["started_at"] = _utc_now()
        _state["finished_at"] = None
        _state["message"] = "Price sync started"
        _state["error"] = None

    thread = threading.Thread(target=_run_price_sync, daemon=True)
    thread.start()
    return {"started": True}


def get_price_sync_status(conn: sqlite3.Connection) -> dict:
    with _lock:
        payload = {
            "status": _state["status"],
            "startedAt": _state["started_at"],
            "finishedAt": _state["finished_at"],
            "message": _state["message"],
            "error": _state["error"],
            "lastPriceUpdate": load_last_updated_display(conn),
            "pricesOutdated": prices_are_outdated(conn),
        }
    return payload
