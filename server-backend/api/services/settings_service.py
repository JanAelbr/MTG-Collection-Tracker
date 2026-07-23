import json
import sqlite3
import threading

from api.cache import bump_cache_epoch
from api.services.pricing_service import list_price_strategies, normalize_strategy
from lib.run_log import get_logger
from report.set_order import normalize_favorite_sets, normalize_set_sort_mode
from util.favorites import normalize_favorite_art_styles, normalize_favorite_cards
from util.price_history import (
    default_compare_date,
    get_compare_dates,
    get_price_snapshot_dates,
)

log = get_logger(__name__)

FAVORITE_SETS_KEY = "favorite_sets"
FAVORITE_CARDS_KEY = "favorite_cards"
FAVORITE_ART_STYLES_KEY = "favorite_art_styles"
PAGE_SIZE_KEY = "page_size"
DEFAULT_PAGE_SIZE = 25
PAGE_SIZE_OPTIONS = (25, 50, 100)
COLLECTION_CARD_SCALE_KEY = "collection_card_scale"
DEFAULT_COLLECTION_CARD_SCALE = 100
COLLECTION_CARD_SCALE_OPTIONS = (75, 100, 125, 150)
SET_SORT_MODE_KEY = "set_sort_mode"
DEFAULT_SET_SORT_MODE = "alphabetical"
SET_SORT_MODE_OPTIONS = ("alphabetical", "owned")
DEFAULT_STORAGE_LOCATION_KEY = "default_storage_location"
DEFAULT_STORAGE_LOCATION = "storage:general"
PRICE_STRATEGY_KEY = "price_strategy"
FAVORITES_CARDS_PRICE_STRATEGY_KEY = "price_strategy_favorites_cards"
FAVORITES_ART_STYLES_PRICE_STRATEGY_KEY = "price_strategy_favorites_art_styles"
OBSOLETE_SETTING_KEYS = ("compare_date", "set_picker_mode")

_purge_lock = threading.Lock()
_purged_obsolete_settings = False


class SettingsError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def _purge_obsolete_settings(conn: sqlite3.Connection) -> None:
    """Drop legacy keys once per process — avoid a write lock on every GET /settings."""
    global _purged_obsolete_settings
    if _purged_obsolete_settings:
        return
    with _purge_lock:
        if _purged_obsolete_settings:
            return
        placeholders = ", ".join("?" for _ in OBSOLETE_SETTING_KEYS)
        exists = conn.execute(
            f"SELECT 1 FROM user_settings WHERE key IN ({placeholders}) LIMIT 1",
            OBSOLETE_SETTING_KEYS,
        ).fetchone()
        if exists:
            conn.executemany(
                "DELETE FROM user_settings WHERE key = ?",
                [(key,) for key in OBSOLETE_SETTING_KEYS],
            )
        _purged_obsolete_settings = True


def get_price_strategy(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        "SELECT value FROM user_settings WHERE key = ?",
        (PRICE_STRATEGY_KEY,),
    ).fetchone()
    if row is None or row["value"] is None:
        return normalize_strategy(None)
    return normalize_strategy(row["value"])


def _optional_price_strategy(values: dict, key: str) -> str | None:
    raw = values.get(key)
    if raw is None or not str(raw).strip():
        return None
    return normalize_strategy(raw)


def _set_price_strategy_setting(conn: sqlite3.Connection, key: str, strategy: str) -> str:
    normalized = normalize_strategy(strategy)
    conn.execute(
        """
        INSERT INTO user_settings (key, value)
        VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (key, normalized),
    )
    return normalized


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


def get_favorite_cards(conn: sqlite3.Connection) -> list[dict]:
    row = conn.execute(
        "SELECT value FROM user_settings WHERE key = ?",
        (FAVORITE_CARDS_KEY,),
    ).fetchone()
    if row is None or row["value"] is None:
        return []
    try:
        parsed = json.loads(row["value"])
    except json.JSONDecodeError:
        return []
    return normalize_favorite_cards(parsed)


def save_favorite_cards(conn: sqlite3.Connection, favorite_cards: list) -> list[dict]:
    normalized = normalize_favorite_cards(favorite_cards)
    conn.execute(
        """
        INSERT INTO user_settings (key, value)
        VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (FAVORITE_CARDS_KEY, json.dumps(normalized)),
    )
    bump_cache_epoch()
    return normalized


def get_favorite_art_styles(conn: sqlite3.Connection) -> list[dict]:
    row = conn.execute(
        "SELECT value FROM user_settings WHERE key = ?",
        (FAVORITE_ART_STYLES_KEY,),
    ).fetchone()
    if row is None or row["value"] is None:
        return []
    try:
        parsed = json.loads(row["value"])
    except json.JSONDecodeError:
        return []
    return normalize_favorite_art_styles(parsed)


def save_favorite_art_styles(conn: sqlite3.Connection, favorite_art_styles: list) -> list[dict]:
    normalized = normalize_favorite_art_styles(favorite_art_styles)
    conn.execute(
        """
        INSERT INTO user_settings (key, value)
        VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (FAVORITE_ART_STYLES_KEY, json.dumps(normalized)),
    )
    bump_cache_epoch()
    return normalized


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
    """Return the previous price snapshot (or an explicit API override)."""
    dates = get_price_snapshot_dates(conn)
    compare_dates = get_compare_dates(dates)
    if override and override in compare_dates:
        return override
    return default_compare_date(dates)


def get_settings(conn: sqlite3.Connection) -> dict:
    _purge_obsolete_settings(conn)
    rows = conn.execute("SELECT key, value FROM user_settings").fetchall()
    values = {row["key"]: row["value"] for row in rows}
    return {
        "priceStrategy": normalize_strategy(values.get("price_strategy")),
        "favoritesCardsPriceStrategy": _optional_price_strategy(
            values, FAVORITES_CARDS_PRICE_STRATEGY_KEY
        ),
        "favoritesArtStylesPriceStrategy": _optional_price_strategy(
            values, FAVORITES_ART_STYLES_PRICE_STRATEGY_KEY
        ),
        "priceStrategies": list_price_strategies(),
        "favoriteSets": get_favorite_sets(conn),
        "favoriteCards": get_favorite_cards(conn),
        "favoriteArtStyles": get_favorite_art_styles(conn),
        "compareDate": resolve_compare_date(conn),
        "pageSize": get_page_size(conn),
        "pageSizeOptions": list(PAGE_SIZE_OPTIONS),
        "collectionCardScale": get_collection_card_scale(conn),
        "collectionCardScaleOptions": list(COLLECTION_CARD_SCALE_OPTIONS),
        "setSortMode": get_set_sort_mode(conn),
        "setSortModeOptions": list(SET_SORT_MODE_OPTIONS),
        "defaultStorageLocation": get_default_storage_location(conn),
    }


def update_settings(
    conn: sqlite3.Connection,
    *,
    price_strategy: str | None = None,
    favorites_cards_price_strategy: str | None = None,
    favorites_art_styles_price_strategy: str | None = None,
    favorite_sets: list[str] | None = None,
    favorite_cards: list | None = None,
    favorite_art_styles: list | None = None,
    page_size: int | None = None,
    collection_card_scale: int | None = None,
    set_sort_mode: str | None = None,
    default_storage_location: str | None = None,
) -> dict:
    _purge_obsolete_settings(conn)
    changed: list[str] = []
    if price_strategy is not None:
        normalized = _set_price_strategy_setting(conn, PRICE_STRATEGY_KEY, price_strategy)
        changed.append(f"price_strategy={normalized}")
    if favorites_cards_price_strategy is not None:
        normalized = _set_price_strategy_setting(
            conn, FAVORITES_CARDS_PRICE_STRATEGY_KEY, favorites_cards_price_strategy
        )
        changed.append(f"price_strategy_favorites_cards={normalized}")
    if favorites_art_styles_price_strategy is not None:
        normalized = _set_price_strategy_setting(
            conn,
            FAVORITES_ART_STYLES_PRICE_STRATEGY_KEY,
            favorites_art_styles_price_strategy,
        )
        changed.append(f"price_strategy_favorites_art_styles={normalized}")
    if favorite_sets is not None:
        save_favorite_sets(conn, favorite_sets)
        changed.append(f"favorite_sets={len(favorite_sets)}")
    if favorite_cards is not None:
        saved_cards = save_favorite_cards(conn, favorite_cards)
        changed.append(f"favorite_cards={len(saved_cards)}")
    if favorite_art_styles is not None:
        saved_styles = save_favorite_art_styles(conn, favorite_art_styles)
        changed.append(f"favorite_art_styles={len(saved_styles)}")
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
        changed.append(f"page_size={parsed}")
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
        changed.append(f"collection_card_scale={parsed_scale}")
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
        changed.append(f"set_sort_mode={normalized_sort_mode}")
    if default_storage_location is not None:
        save_default_storage_location(conn, default_storage_location)
        changed.append(f"default_storage_location={default_storage_location}")
    if changed:
        log.info("Updated settings: %s", ", ".join(changed))
    return get_settings(conn)
