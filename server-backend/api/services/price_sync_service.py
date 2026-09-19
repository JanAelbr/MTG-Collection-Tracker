import sqlite3
import threading
from datetime import datetime, timezone

from lib.config import normalize_set_code
from lib.run_log import get_logger
from util.last_price_sync import (
    empty_price_sync_movers,
    load_last_price_sync,
    movers_have_rows,
    normalize_price_sync_movers,
    save_last_price_sync,
)
from util.price_history import load_last_updated_display, prices_are_outdated
from util.set_families import expand_set_codes_with_families

log = get_logger(__name__)

_lock = threading.Lock()
_state = {
    "status": "idle",
    "started_at": None,
    "finished_at": None,
    "message": None,
    "error": None,
    "prices_unchanged": False,
    "movers": empty_price_sync_movers(),
    "cards": [],
}


class PriceSyncError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def resolve_price_sync_scope(
    conn: sqlite3.Connection,
    *,
    set_code: str | None = None,
) -> tuple[set[str], set[str]]:
    """Return (sets to scan, sets to price in full including unowned prints)."""
    from api.services import settings_service
    from util.cardmarket_prices import load_owned_price_set_codes

    if set_code:
        full_sets = expand_set_codes_with_families(
            conn,
            [code for code in [normalize_set_code(set_code)] if code],
        )
        return full_sets, full_sets

    favourite_sets = expand_set_codes_with_families(
        conn,
        [code for code in settings_service.get_favorite_sets(conn) if code],
    )
    owned_sets = {
        normalize_set_code(code)
        for code in load_owned_price_set_codes(conn)
        if normalize_set_code(code)
    }
    return favourite_sets | owned_sets, favourite_sets


def resolve_price_sync_set_codes(
    conn: sqlite3.Connection,
    *,
    set_code: str | None = None,
) -> set[str]:
    scan_codes, _full_sets = resolve_price_sync_scope(conn, set_code=set_code)
    return scan_codes


def _run_price_sync(set_codes: set[str], extra_qualifying_sets: set[str]) -> None:
    log.info("Price sync running")
    try:
        from util.price_sync import update_cardmarket_prices_only

        result = update_cardmarket_prices_only(
            set_codes=set_codes,
            extra_qualifying_sets=extra_qualifying_sets,
        ) or {}
        from api.cache import bump_cache_epoch
        from api.services.pricing_service import refresh_guide_cache
        from lib.config import DB_PATH
        from util.price_history import mark_price_sync_checked

        applied = bool(result.get("applied") or (result.get("updated_fields") or 0) > 0)
        movers = normalize_price_sync_movers(result.get("movers"))
        message = "Prices unchanged since last sync." if not applied else "Price sync completed"
        if applied:
            refresh_guide_cache()
            bump_cache_epoch()
            try:
                from api.services.storage_service import (
                    art_style_movers_from_history,
                    record_daily_collection_snapshot,
                )

                with sqlite3.connect(DB_PATH) as snap_conn:
                    snap_conn.row_factory = sqlite3.Row
                    saved = record_daily_collection_snapshot(snap_conn)
                    if saved.get("unchanged"):
                        log.info("Daily collection snapshot unchanged; skipped store")
                    else:
                        log.info("Daily collection snapshot saved")
                        if not movers_have_rows(movers):
                            movers = normalize_price_sync_movers(
                                art_style_movers_from_history(snap_conn, limit=25)
                            )
                    snap_conn.commit()
            except Exception:
                log.exception("Daily collection snapshot failed")
            try:
                mark_price_sync_checked()
            except Exception:
                log.exception("Could not mark price sync as checked")
        else:
            message = "Prices unchanged since last sync."
            try:
                mark_price_sync_checked()
            except Exception:
                log.exception("Could not mark price sync as checked")
            log.info("Price sync found no changes")
        try:
            stored = save_last_price_sync({
                "syncedAt": _utc_now(),
                "applied": applied,
                "pricesUnchanged": not applied,
                "message": message,
                "movers": movers,
                "cards": result.get("cards") or [],
            })
            movers = stored["movers"]
            cards = stored.get("cards") or []
        except Exception:
            log.exception("Could not store last price sync")
            cards = result.get("cards") or []
        with _lock:
            _state["status"] = "completed"
            _state["finished_at"] = _utc_now()
            _state["message"] = message
            _state["error"] = None
            _state["prices_unchanged"] = not applied
            _state["movers"] = movers
            _state["cards"] = cards
        log.info("Price sync completed")
    except Exception as exc:
        log.exception("Price sync failed")
        with _lock:
            _state["status"] = "failed"
            _state["finished_at"] = _utc_now()
            _state["message"] = "Price sync failed"
            _state["error"] = str(exc)
            _state["prices_unchanged"] = False
            _state["movers"] = empty_price_sync_movers()
            _state["cards"] = []


def start_price_sync(
    conn: sqlite3.Connection,
    *,
    set_code: str | None = None,
) -> dict:
    set_codes, extra_qualifying_sets = resolve_price_sync_scope(conn, set_code=set_code)
    with _lock:
        if _state["status"] == "running":
            raise PriceSyncError("Price sync is already running", status_code=409)
        _state["status"] = "running"
        _state["started_at"] = _utc_now()
        _state["finished_at"] = None
        _state["message"] = "Price sync started"
        _state["error"] = None
        _state["prices_unchanged"] = False
        _state["movers"] = empty_price_sync_movers()
        _state["cards"] = []

    if set_code:
        log.info("Price sync started for set %s", normalize_set_code(set_code) or set_code)
    else:
        log.info(
            "Price sync started for favourite sets and owned cards (%s set(s))",
            len(set_codes),
        )
    thread = threading.Thread(
        target=_run_price_sync,
        args=(set_codes, extra_qualifying_sets),
        daemon=True,
    )
    thread.start()
    return {"started": True}


def get_price_sync_status(conn: sqlite3.Connection) -> dict:
    last_sync = load_last_price_sync()
    with _lock:
        movers = normalize_price_sync_movers(_state.get("movers"))
        if _state["status"] != "running" and not movers_have_rows(movers) and last_sync:
            movers = last_sync.get("movers") or empty_price_sync_movers()
        payload = {
            "status": _state["status"],
            "startedAt": _state["started_at"],
            "finishedAt": _state["finished_at"],
            "message": _state["message"],
            "error": _state["error"],
            "pricesUnchanged": bool(_state.get("prices_unchanged")),
            "movers": movers,
            "cards": _state.get("cards") or (last_sync or {}).get("cards") or [],
            "lastSync": last_sync,
            "lastPriceUpdate": load_last_updated_display(conn),
            "pricesOutdated": prices_are_outdated(conn),
        }
    return payload
