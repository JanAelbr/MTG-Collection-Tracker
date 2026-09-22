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
    "progress": None,
    "processed": 0,
    "total": 0,
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


def _update_sync_progress(
    *,
    percent: float,
    message: str,
    processed: int | None = None,
    total: int | None = None,
    log_line: bool = False,
) -> None:
    clamped = max(0, min(100, int(round(percent))))
    with _lock:
        _state["progress"] = clamped
        _state["message"] = message
        if processed is not None:
            _state["processed"] = int(processed)
        if total is not None:
            _state["total"] = int(total)
        current_processed = _state["processed"]
        current_total = _state["total"]
    if log_line:
        counts = ""
        if current_total:
            counts = f" {current_processed}/{current_total}"
        log.info("Price sync %s%%%s: %s", clamped, counts, message)


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


def _run_price_sync(set_codes: set[str], extra_qualifying_sets: set[str], force: bool) -> None:
    log.info(
        "Price sync running for %s set(s)%s",
        len(set_codes),
        " (forced)" if force else "",
    )
    last_log_bucket = -1

    def on_progress(percent: float, message: str, processed: int | None = None, total: int | None = None) -> None:
        nonlocal last_log_bucket
        clamped = max(0, min(100, int(round(percent))))
        bucket = clamped // 10
        should_log = bucket != last_log_bucket or clamped >= 100
        if should_log:
            last_log_bucket = bucket
        _update_sync_progress(
            percent=percent,
            message=message,
            processed=processed,
            total=total,
            log_line=should_log,
        )

    try:
        from util.price_sync import update_cardmarket_prices_only

        on_progress(1, "Starting price sync")
        result = update_cardmarket_prices_only(
            set_codes=set_codes,
            extra_qualifying_sets=extra_qualifying_sets,
            force_cardmarket=force,
            on_progress=on_progress,
        ) or {}
        from api.cache import bump_cache_epoch
        from api.services.pricing_service import refresh_guide_cache
        from lib.config import DB_PATH
        from util.price_history import mark_price_sync_checked

        applied = bool(result.get("applied") or (result.get("updated_fields") or 0) > 0)
        movers = normalize_price_sync_movers(result.get("movers"))
        message = "Prices unchanged since last sync." if not applied else "Price sync completed"
        if force and not applied:
            message = "Price sync completed. Guide values matched the current prices."
        if applied or force:
            on_progress(92, "Refreshing price cache")
            refresh_guide_cache()
            bump_cache_epoch()
            try:
                from api.services.storage_service import record_daily_collection_snapshot

                on_progress(95, "Saving collection snapshot")
                with sqlite3.connect(DB_PATH) as snap_conn:
                    snap_conn.row_factory = sqlite3.Row
                    saved = record_daily_collection_snapshot(
                        snap_conn,
                        skip_if_unchanged=not force,
                    )
                    if saved.get("unchanged"):
                        log.info("Daily collection snapshot unchanged; skipped store")
                    else:
                        log.info("Daily collection snapshot saved")
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
            previous = load_last_price_sync() or {}
            new_cards = list(result.get("cards") or [])
            if applied:
                cards = new_cards
                if not movers_have_rows(movers):
                    movers = empty_price_sync_movers()
            else:
                cards = new_cards or list(previous.get("cards") or [])
                if not movers_have_rows(movers):
                    movers = normalize_price_sync_movers(previous.get("movers"))
            stored = save_last_price_sync({
                "syncedAt": _utc_now(),
                "applied": applied,
                "pricesUnchanged": not applied,
                "message": message,
                "movers": movers,
                "cards": cards,
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
            _state["progress"] = 100
            _state["processed"] = _state.get("processed") or 0
            _state["total"] = _state.get("total") or 0
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
            _state["progress"] = None
            _state["processed"] = 0
            _state["total"] = 0
            _state["movers"] = empty_price_sync_movers()
            _state["cards"] = []


def start_price_sync(
    conn: sqlite3.Connection,
    *,
    set_code: str | None = None,
    force: bool = False,
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
        _state["progress"] = 0
        _state["processed"] = 0
        _state["total"] = 0
        _state["movers"] = empty_price_sync_movers()
        _state["cards"] = []

    if set_code:
        log.info(
            "Price sync started for set %s%s",
            normalize_set_code(set_code) or set_code,
            " (forced)" if force else "",
        )
    else:
        log.info(
            "Price sync started for favourite sets and owned cards (%s set(s))%s",
            len(set_codes),
            " (forced)" if force else "",
        )
    thread = threading.Thread(
        target=_run_price_sync,
        args=(set_codes, extra_qualifying_sets, force),
        daemon=True,
    )
    thread.start()
    return {"started": True}


def list_art_style_card_movers(
    conn: sqlite3.Connection,
    *,
    set_code: str | None,
    art_style: str | None,
    limit: int = 200,
) -> list[dict]:
    from util.card_finishes import (
        FINISH_ETCHED,
        FINISH_FOIL,
        FINISH_NONFOIL,
        finish_label,
    )
    from util.price_history import get_price_snapshot_dates

    normalized = normalize_set_code(set_code) or str(set_code or "").strip().upper()
    style = str(art_style or "").strip()
    if not normalized or not style:
        raise PriceSyncError("setCode and artStyle are required", status_code=400)

    dates = get_price_snapshot_dates(conn)
    previous_date = dates[1] if len(dates) > 1 else None
    previous_prices: dict[tuple[str, int], float] = {}
    if previous_date:
        for row in conn.execute(
            """
            SELECT collector_number, finish, price
            FROM card_prices
            WHERE set_code = ? AND price_date = ?
            """,
            (normalized, previous_date),
        ):
            number = str(row[0] if not isinstance(row, sqlite3.Row) else row["collector_number"])
            finish = int(row[1] if not isinstance(row, sqlite3.Row) else row["finish"])
            price = float(row[2] if not isinstance(row, sqlite3.Row) else row["price"])
            previous_prices[(number, finish)] = price

    catalog = conn.execute(
        """
        SELECT name, collector_number, art_style,
               market_value, market_value_foil, market_value_etched,
               COALESCE(has_nonfoil, 1) AS has_nonfoil,
               COALESCE(has_foil, 1) AS has_foil,
               COALESCE(has_etched, 0) AS has_etched
        FROM cards
        WHERE set_code = ? AND COALESCE(art_style, '') = ?
        """,
        (normalized, style),
    ).fetchall()

    def field(row, key, index):
        if isinstance(row, sqlite3.Row) and key in row.keys():
            return row[key]
        return row[index]

    moves: list[dict] = []
    finishes = (
        (FINISH_NONFOIL, "market_value", "has_nonfoil", 3, 6),
        (FINISH_FOIL, "market_value_foil", "has_foil", 4, 7),
        (FINISH_ETCHED, "market_value_etched", "has_etched", 5, 8),
    )
    for card in catalog:
        name = str(field(card, "name", 0) or "").strip()
        number = str(field(card, "collector_number", 1) or "").strip()
        for finish_id, value_key, flag_key, value_index, flag_index in finishes:
            if not int(field(card, flag_key, flag_index) or 0):
                continue
            raw_current = field(card, value_key, value_index)
            try:
                current = float(raw_current) if raw_current is not None else 0.0
            except (TypeError, ValueError):
                current = 0.0
            previous = float(previous_prices.get((number, finish_id), 0.0) or 0.0)
            if previous <= 0 or current == previous:
                continue
            delta = current - previous
            finish = finish_label(finish_id)
            label = name or f"{normalized} #{number}"
            if finish:
                label = f"{label} ({finish})"
            moves.append({
                "id": f"{normalized}|{number}|{finish_id}",
                "label": label,
                "setCode": normalized,
                "collectorNumber": number,
                "artStyle": style,
                "finish": finish,
                "previous": previous,
                "current": current,
                "delta": delta,
                "percent": (delta / previous) * 100,
            })

    moves.sort(key=lambda item: (abs(item["delta"]), abs(item["percent"])), reverse=True)
    return moves[: max(0, limit)]


def hydrate_price_sync_cards(conn: sqlite3.Connection, cards) -> list:
    items = [dict(card) for card in cards or [] if isinstance(card, dict)]
    pending = []
    for card in items:
        if card.get("imageUri") and card.get("name"):
            continue
        set_code = str(card.get("setCode") or "").strip().upper()
        number = str(card.get("collectorNumber") or "").strip()
        if set_code and number:
            pending.append((set_code, number))
    if not pending:
        return items
    lookup = {}
    unique = list(dict.fromkeys(pending))
    try:
        for index in range(0, len(unique), 400):
            chunk = unique[index:index + 400]
            placeholders = ",".join("(?, ?)" for _ in chunk)
            params = [value for pair in chunk for value in pair]
            rows = conn.execute(
                f"""
                SELECT set_code, collector_number, name, image_uri
                FROM cards
                WHERE (set_code, collector_number) IN ({placeholders})
                """,
                params,
            ).fetchall()
            for row in rows:
                lookup[(str(row[0] or "").upper(), str(row[1] or ""))] = row
    except sqlite3.Error:
        return items
    hydrated = []
    for card in items:
        key = (
            str(card.get("setCode") or "").strip().upper(),
            str(card.get("collectorNumber") or "").strip(),
        )
        extra = lookup.get(key)
        if not extra:
            hydrated.append(card)
            continue
        next_card = dict(card)
        if not next_card.get("name") and extra[2]:
            next_card["name"] = extra[2]
        if not next_card.get("imageUri") and extra[3]:
            next_card["imageUri"] = extra[3]
        hydrated.append(next_card)
    return hydrated


def get_price_sync_status(conn: sqlite3.Connection) -> dict:
    last_sync = load_last_price_sync()
    if last_sync:
        last_sync = {
            **last_sync,
            "cards": hydrate_price_sync_cards(conn, last_sync.get("cards") or []),
        }
    with _lock:
        movers = normalize_price_sync_movers(_state.get("movers"))
        if _state["status"] != "running" and not movers_have_rows(movers) and last_sync:
            movers = last_sync.get("movers") or empty_price_sync_movers()
        cards = hydrate_price_sync_cards(
            conn,
            _state.get("cards") or (last_sync or {}).get("cards") or [],
        )
        payload = {
            "status": _state["status"],
            "startedAt": _state["started_at"],
            "finishedAt": _state["finished_at"],
            "message": _state["message"],
            "error": _state["error"],
            "pricesUnchanged": bool(_state.get("prices_unchanged")),
            "progress": _state.get("progress"),
            "processed": int(_state.get("processed") or 0),
            "total": int(_state.get("total") or 0),
            "movers": movers,
            "cards": cards,
            "lastSync": last_sync,
            "lastPriceUpdate": load_last_updated_display(conn),
            "pricesOutdated": prices_are_outdated(conn),
        }
    return payload
