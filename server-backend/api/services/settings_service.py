import json
import sqlite3

from api.cache import bump_cache_epoch
from api.services.pricing_service import list_price_strategies, normalize_strategy
from report.set_order import normalize_favorite_sets, normalize_set_picker_mode, normalize_set_sort_mode
from util.price_history import (
    default_compare_date,
    get_compare_dates,
    get_price_snapshot_dates,
)

FAVORITE_SETS_KEY = "favorite_sets"
COMPARE_DATE_KEY = "compare_date"
PAGE_SIZE_KEY = "page_size"
DEFAULT_PAGE_SIZE = 25
PAGE_SIZE_OPTIONS = (25, 50, 100)
COLLECTION_CARD_SCALE_KEY = "collection_card_scale"
DEFAULT_COLLECTION_CARD_SCALE = 100
COLLECTION_CARD_SCALE_OPTIONS = (75, 100, 125, 150)
SET_SORT_MODE_KEY = "set_sort_mode"
DEFAULT_SET_SORT_MODE = "alphabetical"
SET_SORT_MODE_OPTIONS = ("alphabetical", "owned")
SET_PICKER_MODE_KEY = "set_picker_mode"
DEFAULT_SET_PICKER_MODE = "dropdown"
SET_PICKER_MODE_OPTIONS = ("dropdown", "browser")
DEFAULT_STORAGE_LOCATION_KEY = "default_storage_location"
DEFAULT_STORAGE_LOCATION = "storage:general"


class SettingsError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def get_favorite_sets(conn: sqlite3.Connection) -> list[str]:
    row = conn.execute(
        "SELECT value FROM user_settings WHERE key = ?",
        (FAVORITE_SETS_KEY,),
    ).fetchone()
    if row is None or row["value"] is None:
        return []
    try:
        parsed = json.loads(row["value"])
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return normalize_favorite_sets([str(item) for item in parsed])


def save_favorite_sets(conn: sqlite3.Connection, favorite_sets: list[str]) -> list[str]:
    normalized = normalize_favorite_sets(favorite_sets)
    conn.execute(
        """
        INSERT INTO user_settings (key, value)
        VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (FAVORITE_SETS_KEY, json.dumps(normalized)),
    )
    bump_cache_epoch()
    return normalized


def get_compare_date_setting(conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        "SELECT value FROM user_settings WHERE key = ?",
        (COMPARE_DATE_KEY,),
    ).fetchone()
    if row is None or row["value"] is None:
        return None
    value = str(row["value"]).strip()
    return value or None


def normalize_page_size(value) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return DEFAULT_PAGE_SIZE
    if parsed in PAGE_SIZE_OPTIONS:
        return parsed
    return DEFAULT_PAGE_SIZE


def get_page_size(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT value FROM user_settings WHERE key = ?",
        (PAGE_SIZE_KEY,),
    ).fetchone()
    if row is None or row["value"] is None:
        return DEFAULT_PAGE_SIZE
    return normalize_page_size(row["value"])


def normalize_collection_card_scale(value) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return DEFAULT_COLLECTION_CARD_SCALE
    if parsed in COLLECTION_CARD_SCALE_OPTIONS:
        return parsed
    return DEFAULT_COLLECTION_CARD_SCALE


def get_collection_card_scale(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT value FROM user_settings WHERE key = ?",
        (COLLECTION_CARD_SCALE_KEY,),
    ).fetchone()
    if row is None or row["value"] is None:
        return DEFAULT_COLLECTION_CARD_SCALE
    return normalize_collection_card_scale(row["value"])


def get_set_sort_mode(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        "SELECT value FROM user_settings WHERE key = ?",
        (SET_SORT_MODE_KEY,),
    ).fetchone()
    if row is None or row["value"] is None:
        return DEFAULT_SET_SORT_MODE
    return normalize_set_sort_mode(row["value"])


def get_set_picker_mode(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        "SELECT value FROM user_settings WHERE key = ?",
        (SET_PICKER_MODE_KEY,),
    ).fetchone()
    if row is None or row["value"] is None:
        return DEFAULT_SET_PICKER_MODE
    return normalize_set_picker_mode(row["value"])


def get_default_storage_location(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        "SELECT value FROM user_settings WHERE key = ?",
        (DEFAULT_STORAGE_LOCATION_KEY,),
    ).fetchone()
    if row is None or row["value"] is None:
        return DEFAULT_STORAGE_LOCATION
    value = str(row["value"]).strip()
    return value or DEFAULT_STORAGE_LOCATION


def save_default_storage_location(conn: sqlite3.Connection, location_slug: str) -> str:
    from api.services.storage_service import StorageError, get_location

    normalized = str(location_slug or "").strip() or DEFAULT_STORAGE_LOCATION
    try:
        get_location(conn, normalized)
    except StorageError as exc:
        raise SettingsError(exc.message) from exc
    conn.execute(
        """
        INSERT INTO user_settings (key, value)
        VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (DEFAULT_STORAGE_LOCATION_KEY, normalized),
    )
    bump_cache_epoch()
    return normalized


def resolve_compare_date(conn: sqlite3.Connection, override: str | None = None) -> str | None:
    dates = get_price_snapshot_dates(conn)
    compare_dates = get_compare_dates(dates)
    if override and override in compare_dates:
        return override
    stored = get_compare_date_setting(conn)
    if stored and stored in compare_dates:
        return stored
    return default_compare_date(dates)


def get_settings(conn: sqlite3.Connection) -> dict:
    rows = conn.execute("SELECT key, value FROM user_settings").fetchall()
    values = {row["key"]: row["value"] for row in rows}
    dates = get_price_snapshot_dates(conn)
    compare_dates = get_compare_dates(dates)
    return {
        "priceStrategy": normalize_strategy(values.get("price_strategy")),
        "priceStrategies": list_price_strategies(),
        "favoriteSets": get_favorite_sets(conn),
        "compareDates": compare_dates,
        "defaultCompareDate": default_compare_date(dates),
        "compareDate": resolve_compare_date(conn),
        "pageSize": get_page_size(conn),
        "pageSizeOptions": list(PAGE_SIZE_OPTIONS),
        "collectionCardScale": get_collection_card_scale(conn),
        "collectionCardScaleOptions": list(COLLECTION_CARD_SCALE_OPTIONS),
        "setSortMode": get_set_sort_mode(conn),
        "setSortModeOptions": list(SET_SORT_MODE_OPTIONS),
        "setPickerMode": get_set_picker_mode(conn),
        "setPickerModeOptions": list(SET_PICKER_MODE_OPTIONS),
        "defaultStorageLocation": get_default_storage_location(conn),
    }


def update_settings(
    conn: sqlite3.Connection,
    *,
    price_strategy: str | None = None,
    favorite_sets: list[str] | None = None,
    compare_date: str | None = None,
    set_compare_date: bool = False,
    page_size: int | None = None,
    collection_card_scale: int | None = None,
    set_sort_mode: str | None = None,
    set_picker_mode: str | None = None,
    default_storage_location: str | None = None,
) -> dict:
    if price_strategy is not None:
        normalized = normalize_strategy(price_strategy)
        conn.execute(
            """
            INSERT INTO user_settings (key, value)
            VALUES ('price_strategy', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (normalized,),
        )
        bump_cache_epoch()
    if favorite_sets is not None:
        save_favorite_sets(conn, favorite_sets)
    if set_compare_date:
        dates = get_price_snapshot_dates(conn)
        compare_dates = get_compare_dates(dates)
        normalized_compare = None if compare_date in (None, "") else str(compare_date).strip()
        if normalized_compare and normalized_compare not in compare_dates:
            raise SettingsError("Invalid compare date")
        conn.execute(
            """
            INSERT INTO user_settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (COMPARE_DATE_KEY, normalized_compare or ""),
        )
        bump_cache_epoch()
    if page_size is not None:
        try:
            parsed = int(page_size)
        except (TypeError, ValueError) as exc:
            raise SettingsError("Invalid page size") from exc
        if parsed not in PAGE_SIZE_OPTIONS:
            raise SettingsError("Invalid page size")
        conn.execute(
            """
            INSERT INTO user_settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (PAGE_SIZE_KEY, str(parsed)),
        )
        bump_cache_epoch()
    if collection_card_scale is not None:
        try:
            parsed_scale = int(collection_card_scale)
        except (TypeError, ValueError) as exc:
            raise SettingsError("Invalid collection card scale") from exc
        if parsed_scale not in COLLECTION_CARD_SCALE_OPTIONS:
            raise SettingsError("Invalid collection card scale")
        conn.execute(
            """
            INSERT INTO user_settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (COLLECTION_CARD_SCALE_KEY, str(parsed_scale)),
        )
        bump_cache_epoch()
    if set_sort_mode is not None:
        normalized_sort_mode = normalize_set_sort_mode(set_sort_mode)
        conn.execute(
            """
            INSERT INTO user_settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (SET_SORT_MODE_KEY, normalized_sort_mode),
        )
        bump_cache_epoch()
    if set_picker_mode is not None:
        normalized_picker_mode = normalize_set_picker_mode(set_picker_mode)
        conn.execute(
            """
            INSERT INTO user_settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (SET_PICKER_MODE_KEY, normalized_picker_mode),
        )
        bump_cache_epoch()
    if default_storage_location is not None:
        save_default_storage_location(conn, default_storage_location)
    return get_settings(conn)
