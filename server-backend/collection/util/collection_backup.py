"""Export and import collection user data without catalog rows or prices."""

from __future__ import annotations

import io
import json
import sqlite3
import zipfile
from collections import Counter
from datetime import datetime, timezone

from lib.config import normalize_set_code
from lib.art_styles import import_art_style_rules, load_art_style_rules_for_sets
from util.app_tables import ensure_app_tables
from util.card_finishes import normalize_finish
from util.deck_tables import ensure_deck_tables
from util.schema import ensure_database_schema
from util.storage_tables import ensure_storage_tables, seed_storage_locations

FORMAT_VERSION = 1
COLLECTION_JSON = "collection.json"
MANIFEST_JSON = "manifest.json"
ART_STYLES_ZIP_DIR = "art_styles"

EXPORT_SETTING_KEYS = frozenset({
    "price_strategy",
    "favorite_sets",
    "page_size",
    "collection_card_scale",
    "set_sort_mode",
    "set_picker_mode",
    "default_storage_location",
})

IMPORT_MODES = frozenset({"replace", "merge"})


class BackupError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _row_dict(row) -> dict:
    if isinstance(row, dict):
        return row
    return {key: row[key] for key in row.keys()}


def _normalize_set_code(value) -> str:
    return str(value or "").strip().upper()


def _normalize_collector_number(value) -> str:
    return str(value or "").strip()


def _float_or_none(value) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _values_equal(left, right) -> bool:
    if left is None and right is None:
        return True
    if left is None or right is None:
        return False
    return float(left) == float(right)


def _instance_identity(
    *,
    set_code: str,
    collector_number: str,
    finish: int,
    location_slug: str,
    purchase_value,
) -> tuple:
    return (
        _normalize_set_code(set_code),
        _normalize_collector_number(collector_number),
        normalize_finish(finish),
        str(location_slug).strip(),
        _float_or_none(purchase_value),
    )


def _instance_identity_from_row(row: dict) -> tuple:
    return _instance_identity(
        set_code=row["setCode"],
        collector_number=row["collectorNumber"],
        finish=row.get("finish"),
        location_slug=row["locationSlug"],
        purchase_value=row.get("purchaseValue"),
    )


def _instance_identity_from_db(row) -> tuple:
    return _instance_identity(
        set_code=row["set_code"],
        collector_number=row["collector_number"],
        finish=row["finish"],
        location_slug=row["location_slug"],
        purchase_value=row["purchase_value"],
    )


def _count_card_instances(conn: sqlite3.Connection) -> Counter:
    counts: Counter = Counter()
    for row in conn.execute(
        """
        SELECT set_code, collector_number, finish, location_slug, purchase_value
        FROM card_instances
        """
    ).fetchall():
        counts[_instance_identity_from_db(row)] += 1
    return counts


def _sets_referenced(collection: dict) -> list[str]:
    codes: set[str] = set()
    for row in collection.get("purchases") or []:
        code = _normalize_set_code(row.get("setCode"))
        if code:
            codes.add(code)
    for row in collection.get("deckCards") or []:
        code = _normalize_set_code(row.get("setCode"))
        if code:
            codes.add(code)
    for row in collection.get("storageLocations") or []:
        code = _normalize_set_code(row.get("setCode"))
        if code:
            codes.add(code)
    return sorted(codes)


def build_collection_payload(conn: sqlite3.Connection) -> dict:
    ensure_database_schema(conn)
    ensure_app_tables(conn)

    purchases = [
        {
            "setCode": _normalize_set_code(row["set_code"]),
            "collectorNumber": _normalize_collector_number(row["collector_number"]),
            "finish": int(row["finish"]),
            "purchaseValue": float(row["purchase_value"]),
        }
        for row in conn.execute(
            """
            SELECT set_code, collector_number, finish, purchase_value
            FROM purchases
            ORDER BY set_code, CAST(collector_number AS INTEGER), finish
            """
        ).fetchall()
    ]

    decks = [
        {
            "name": row["name"],
            "slug": str(row["slug"]).strip().lower(),
            "purchasePrice": _float_or_none(row["purchase_price"]),
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
        }
        for row in conn.execute(
            """
            SELECT name, slug, purchase_price, created_at, updated_at
            FROM decks
            ORDER BY name
            """
        ).fetchall()
    ]

    deck_slug_by_id = {
        int(row["deck_id"]): str(row["slug"]).strip().lower()
        for row in conn.execute("SELECT deck_id, slug FROM decks").fetchall()
    }

    deck_cards = [
        {
            "deckSlug": deck_slug_by_id[int(row["deck_id"])],
            "cardName": row["card_name"],
            "setCode": _normalize_set_code(row["set_code"]) or None,
            "collectorNumber": _normalize_collector_number(row["collector_number"]) or None,
            "finish": int(row["finish"]),
            "qty": int(row["qty"]),
            "ownedQty": int(row["owned_qty"]),
            "section": row["section"] or "main",
            "sortOrder": int(row["sort_order"]),
            "inCatalog": bool(int(row["in_catalog"] or 0)),
        }
        for row in conn.execute(
            """
            SELECT deck_id, card_name, set_code, collector_number, finish,
                   qty, owned_qty, section, sort_order, in_catalog
            FROM deck_cards
            ORDER BY deck_id, sort_order, deck_card_id
            """
        ).fetchall()
        if int(row["deck_id"]) in deck_slug_by_id
    ]

    storage_locations = [
        {
            "locationSlug": row["location_slug"],
            "label": row["label"],
            "locationType": row["location_type"],
            "sortOrder": int(row["sort_order"]),
            "setCode": _normalize_set_code(row["set_code"]) or None,
            "description": row["description"],
            "isSystem": bool(int(row["is_system"] or 0)),
        }
        for row in conn.execute(
            """
            SELECT location_slug, label, location_type, sort_order,
                   set_code, description, is_system
            FROM storage_locations
            ORDER BY sort_order, location_slug
            """
        ).fetchall()
    ]

    card_instances = [
        {
            "setCode": _normalize_set_code(row["set_code"]),
            "collectorNumber": _normalize_collector_number(row["collector_number"]),
            "finish": int(row["finish"]),
            "locationSlug": row["location_slug"],
            "purchaseValue": _float_or_none(row["purchase_value"]),
        }
        for row in conn.execute(
            """
            SELECT set_code, collector_number, finish, location_slug, purchase_value
            FROM card_instances
            ORDER BY set_code, CAST(collector_number AS INTEGER), finish, location_slug
            """
        ).fetchall()
    ]

    settings = {
        row["key"]: row["value"]
        for row in conn.execute(
            "SELECT key, value FROM user_settings WHERE key IN ({})".format(
                ",".join("?" for _ in EXPORT_SETTING_KEYS),
            ),
            tuple(sorted(EXPORT_SETTING_KEYS)),
        ).fetchall()
    }

    return {
        "purchases": purchases,
        "decks": decks,
        "deckCards": deck_cards,
        "storageLocations": storage_locations,
        "cardInstances": card_instances,
        "settings": settings,
    }


def _load_art_style_rules(conn: sqlite3.Connection, set_codes: list[str]) -> dict[str, list]:
    return load_art_style_rules_for_sets(conn, set_codes)


def build_manifest(collection: dict, *, art_style_sets: list[str]) -> dict:
    sets_referenced = _sets_referenced(collection)
    return {
        "formatVersion": FORMAT_VERSION,
        "exportedAt": _utc_now_iso(),
        "summary": {
            "purchases": len(collection.get("purchases") or []),
            "decks": len(collection.get("decks") or []),
            "deckCards": len(collection.get("deckCards") or []),
            "cardInstances": len(collection.get("cardInstances") or []),
            "storageLocations": len(collection.get("storageLocations") or []),
            "artStyleSets": len(art_style_sets),
            "setsReferenced": sets_referenced,
        },
    }


def summarize_backup(collection: dict, art_styles: dict[str, list]) -> dict:
    manifest = build_manifest(collection, art_style_sets=sorted(art_styles))
    return {
        "formatVersion": manifest["formatVersion"],
        "exportedAt": manifest.get("exportedAt"),
        "summary": manifest["summary"],
        "artStyleSets": sorted(art_styles),
    }


def export_collection_zip(conn: sqlite3.Connection) -> bytes:
    collection = build_collection_payload(conn)
    sets_referenced = _sets_referenced(collection)
    art_styles = _load_art_style_rules(conn, sets_referenced)
    manifest = build_manifest(collection, art_style_sets=sorted(art_styles))

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(MANIFEST_JSON, json.dumps(manifest, indent=2) + "\n")
        archive.writestr(COLLECTION_JSON, json.dumps(collection, indent=2) + "\n")
        for set_code, rules in sorted(art_styles.items()):
            archive.writestr(
                f"{ART_STYLES_ZIP_DIR}/{set_code}.json",
                json.dumps(rules, indent=4, ensure_ascii=False) + "\n",
            )
    return buffer.getvalue()


def parse_backup_zip(data: bytes) -> tuple[dict, dict, dict[str, list]]:
    if not data:
        raise BackupError("Backup file is empty")
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise BackupError("Backup file is not a valid ZIP archive") from exc

    names = set(archive.namelist())
    if COLLECTION_JSON not in names:
        raise BackupError(f"Backup is missing {COLLECTION_JSON}")
    if MANIFEST_JSON not in names:
        raise BackupError(f"Backup is missing {MANIFEST_JSON}")

    try:
        manifest = json.loads(archive.read(MANIFEST_JSON).decode("utf-8"))
        collection = json.loads(archive.read(COLLECTION_JSON).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BackupError("Backup JSON is invalid") from exc

    version = manifest.get("formatVersion")
    if version != FORMAT_VERSION:
        raise BackupError(f"Unsupported backup format version: {version}")

    art_styles: dict[str, list] = {}
    prefix = f"{ART_STYLES_ZIP_DIR}/"
    for name in names:
        if not name.startswith(prefix) or not name.endswith(".json"):
            continue
        set_code = name[len(prefix): -len(".json")].strip().lower()
        if not set_code:
            continue
        try:
            rules = json.loads(archive.read(name).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BackupError(f"Invalid art style file in backup: {name}") from exc
        if not isinstance(rules, list):
            raise BackupError(f"Art style file must contain a list: {name}")
        art_styles[set_code] = rules

    _validate_collection(collection)
    return manifest, collection, art_styles


def preview_backup(data: bytes) -> dict:
    manifest, collection, art_styles = parse_backup_zip(data)
    summary = summarize_backup(collection, art_styles)
    summary["exportedAt"] = manifest.get("exportedAt")
    return summary


def _validate_collection(collection: dict) -> None:
    if not isinstance(collection, dict):
        raise BackupError("Collection payload must be an object")

    for index, row in enumerate(collection.get("purchases") or []):
        _validate_purchase(row, index)

    deck_slugs = set()
    for index, row in enumerate(collection.get("decks") or []):
        slug = _validate_deck(row, index)
        deck_slugs.add(slug)

    for index, row in enumerate(collection.get("deckCards") or []):
        _validate_deck_card(row, index, deck_slugs)

    location_slugs = set()
    for index, row in enumerate(collection.get("storageLocations") or []):
        slug = _validate_storage_location(row, index)
        location_slugs.add(slug)

    for index, row in enumerate(collection.get("cardInstances") or []):
        _validate_card_instance(row, index, location_slugs)

    settings = collection.get("settings") or {}
    if not isinstance(settings, dict):
        raise BackupError("Settings payload must be an object")


def _validate_purchase(row: dict, index: int) -> None:
    if not isinstance(row, dict):
        raise BackupError(f"Purchase row {index} must be an object")
    if not _normalize_set_code(row.get("setCode")):
        raise BackupError(f"Purchase row {index} is missing setCode")
    if not _normalize_collector_number(row.get("collectorNumber")):
        raise BackupError(f"Purchase row {index} is missing collectorNumber")
    normalize_finish(row.get("finish"))


def _validate_deck(row: dict, index: int) -> str:
    if not isinstance(row, dict):
        raise BackupError(f"Deck row {index} must be an object")
    slug = str(row.get("slug") or "").strip().lower()
    if not slug:
        raise BackupError(f"Deck row {index} is missing slug")
    if not str(row.get("name") or "").strip():
        raise BackupError(f"Deck row {index} is missing name")
    return slug


def _validate_deck_card(row: dict, index: int, deck_slugs: set[str]) -> None:
    if not isinstance(row, dict):
        raise BackupError(f"Deck card row {index} must be an object")
    deck_slug = str(row.get("deckSlug") or "").strip().lower()
    if deck_slug not in deck_slugs:
        raise BackupError(f"Deck card row {index} references unknown deck '{deck_slug}'")
    if not str(row.get("cardName") or "").strip():
        raise BackupError(f"Deck card row {index} is missing cardName")
    normalize_finish(row.get("finish"))


def _validate_storage_location(row: dict, index: int) -> str:
    if not isinstance(row, dict):
        raise BackupError(f"Storage location row {index} must be an object")
    slug = str(row.get("locationSlug") or "").strip()
    if not slug:
        raise BackupError(f"Storage location row {index} is missing locationSlug")
    location_type = str(row.get("locationType") or "").strip()
    if location_type not in {"binder", "deck", "storage"}:
        raise BackupError(f"Storage location row {index} has invalid locationType")
    return slug


def _validate_card_instance(row: dict, index: int, location_slugs: set[str]) -> None:
    if not isinstance(row, dict):
        raise BackupError(f"Card instance row {index} must be an object")
    if not _normalize_set_code(row.get("setCode")):
        raise BackupError(f"Card instance row {index} is missing setCode")
    if not _normalize_collector_number(row.get("collectorNumber")):
        raise BackupError(f"Card instance row {index} is missing collectorNumber")
    normalize_finish(row.get("finish"))
    slug = str(row.get("locationSlug") or "").strip()
    if slug not in location_slugs:
        raise BackupError(f"Card instance row {index} references unknown location '{slug}'")


def import_collection(
    conn: sqlite3.Connection,
    collection: dict,
    art_styles: dict[str, list],
    *,
    mode: str,
) -> dict:
    normalized_mode = (mode or "replace").strip().lower()
    if normalized_mode not in IMPORT_MODES:
        raise BackupError("Import mode must be 'replace' or 'merge'")

    ensure_database_schema(conn)
    ensure_app_tables(conn)
    ensure_storage_tables(conn)
    seed_storage_locations(conn)

    if normalized_mode == "replace":
        _clear_collection_data(conn)

    _import_storage_locations(conn, collection.get("storageLocations") or [], merge=normalized_mode == "merge")
    deck_slug_map = _import_decks(conn, collection.get("decks") or [], merge=normalized_mode == "merge")
    seed_storage_locations(conn)
    _import_deck_cards(conn, collection.get("deckCards") or [], deck_slug_map, merge=normalized_mode == "merge")
    _import_purchases(conn, collection.get("purchases") or [], merge=normalized_mode == "merge")
    _import_card_instances(conn, collection.get("cardInstances") or [], merge=normalized_mode == "merge")
    _import_settings(conn, collection.get("settings") or {}, merge=normalized_mode == "merge")
    _import_art_styles(conn, art_styles, merge=normalized_mode == "merge")
    seed_storage_locations(conn)

    sets_referenced = _sets_referenced(collection)
    return {
        "mode": normalized_mode,
        "summary": summarize_backup(collection, art_styles)["summary"],
        "setsNeedingCatalog": sets_referenced,
        "message": (
            "Collection restored. Sync catalog and prices to load card images and EUR values."
        ),
    }


def import_collection_zip(conn: sqlite3.Connection, data: bytes, *, mode: str) -> dict:
    _, collection, art_styles = parse_backup_zip(data)
    return import_collection(conn, collection, art_styles, mode=mode)


def _clear_collection_data(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM card_instances")
    conn.execute("DELETE FROM deck_cards")
    conn.execute("DELETE FROM decks")
    conn.execute("DELETE FROM purchases")
    conn.execute(
        """
        DELETE FROM storage_locations
        WHERE is_system = 0 OR location_slug LIKE 'deck:%'
        """
    )
    placeholders = ",".join("?" for _ in EXPORT_SETTING_KEYS)
    conn.execute(
        f"DELETE FROM user_settings WHERE key IN ({placeholders})",
        tuple(sorted(EXPORT_SETTING_KEYS)),
    )


def _import_storage_locations(conn: sqlite3.Connection, rows: list[dict], *, merge: bool) -> None:
    for row in rows:
        slug = str(row["locationSlug"]).strip()
        is_system = 1 if bool(row.get("isSystem")) else 0
        if merge and slug.startswith("deck:"):
            continue
        if merge:
            existing = conn.execute(
                """
                SELECT label, location_type, sort_order, set_code, description, is_system
                FROM storage_locations
                WHERE location_slug = ?
                """,
                (slug,),
            ).fetchone()
            if existing and (
                existing["label"] == row["label"]
                and existing["location_type"] == row["locationType"]
                and int(existing["sort_order"]) == int(row.get("sortOrder") or 0)
                and (existing["set_code"] or None) == (_normalize_set_code(row.get("setCode")) or None)
                and (existing["description"] or None) == (row.get("description") or None)
                and bool(int(existing["is_system"] or 0)) == bool(is_system)
            ):
                continue
        conn.execute(
            """
            INSERT INTO storage_locations (
                location_slug, label, location_type, sort_order,
                set_code, description, is_system
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(location_slug) DO UPDATE SET
                label = excluded.label,
                location_type = excluded.location_type,
                sort_order = excluded.sort_order,
                set_code = excluded.set_code,
                description = excluded.description,
                is_system = CASE
                    WHEN storage_locations.is_system = 1 THEN storage_locations.is_system
                    ELSE excluded.is_system
                END
            """,
            (
                slug,
                row["label"],
                row["locationType"],
                int(row.get("sortOrder") or 0),
                _normalize_set_code(row.get("setCode")) or None,
                row.get("description"),
                is_system,
            ),
        )


def _import_decks(conn: sqlite3.Connection, rows: list[dict], *, merge: bool) -> dict[str, int]:
    ensure_deck_tables(conn)
    slug_map: dict[str, int] = {}
    for row in rows:
        slug = str(row["slug"]).strip().lower()
        created_at = row.get("createdAt") or _utc_now_iso()
        updated_at = row.get("updatedAt") or created_at
        purchase_price = _float_or_none(row.get("purchasePrice"))
        if merge:
            existing = conn.execute(
                """
                SELECT deck_id, name, purchase_price, created_at, updated_at
                FROM decks
                WHERE slug = ?
                """,
                (slug,),
            ).fetchone()
            if existing and (
                existing["name"] == row["name"]
                and _values_equal(existing["purchase_price"], purchase_price)
                and str(existing["created_at"]) == str(created_at)
                and str(existing["updated_at"]) == str(updated_at)
            ):
                slug_map[slug] = int(existing["deck_id"])
                continue
        conn.execute(
            """
            INSERT INTO decks (name, slug, purchase_price, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(slug) DO UPDATE SET
                name = excluded.name,
                purchase_price = COALESCE(excluded.purchase_price, decks.purchase_price),
                updated_at = excluded.updated_at
            """,
            (
                row["name"],
                slug,
                purchase_price,
                created_at,
                updated_at,
            ),
        )
        deck_id = conn.execute(
            "SELECT deck_id FROM decks WHERE slug = ?",
            (slug,),
        ).fetchone()[0]
        slug_map[slug] = int(deck_id)
    return slug_map


def _import_deck_cards(
    conn: sqlite3.Connection,
    rows: list[dict],
    deck_slug_map: dict[str, int],
    *,
    merge: bool,
) -> None:
    for row in rows:
        deck_slug = str(row["deckSlug"]).strip().lower()
        deck_id = deck_slug_map.get(deck_slug)
        if deck_id is None:
            deck_id = conn.execute(
                "SELECT deck_id FROM decks WHERE slug = ?",
                (deck_slug,),
            ).fetchone()[0]
        set_code = _normalize_set_code(row.get("setCode")) or None
        collector_number = _normalize_collector_number(row.get("collectorNumber")) or None
        finish = normalize_finish(row.get("finish"))
        section = row.get("section") or "main"
        qty = int(row.get("qty") or 1)
        owned_qty = int(row.get("ownedQty") or 0)
        sort_order = int(row.get("sortOrder") or 0)
        in_catalog = 1 if row.get("inCatalog") else 0
        if merge:
            existing = conn.execute(
                """
                SELECT card_name, qty, owned_qty, sort_order, in_catalog
                FROM deck_cards
                WHERE deck_id = ? AND set_code IS ? AND collector_number IS ?
                  AND finish = ? AND section = ?
                """,
                (deck_id, set_code, collector_number, finish, section),
            ).fetchone()
            if existing and (
                existing["card_name"] == row["cardName"]
                and int(existing["qty"]) == qty
                and int(existing["owned_qty"]) == owned_qty
                and int(existing["sort_order"]) == sort_order
                and int(existing["in_catalog"]) == in_catalog
            ):
                continue
        conn.execute(
            """
            INSERT INTO deck_cards (
                deck_id, card_name, set_code, collector_number, finish,
                qty, owned_qty, section, sort_order, in_catalog
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(deck_id, set_code, collector_number, finish, section) DO UPDATE SET
                card_name = excluded.card_name,
                qty = excluded.qty,
                owned_qty = excluded.owned_qty,
                sort_order = excluded.sort_order,
                in_catalog = excluded.in_catalog
            """,
            (
                deck_id,
                row["cardName"],
                set_code,
                collector_number,
                finish,
                qty,
                owned_qty,
                section,
                sort_order,
                in_catalog,
            ),
        )


def _import_purchases(conn: sqlite3.Connection, rows: list[dict], *, merge: bool) -> None:
    for row in rows:
        set_code = _normalize_set_code(row["setCode"])
        collector_number = _normalize_collector_number(row["collectorNumber"])
        finish = normalize_finish(row.get("finish"))
        purchase_value = float(row.get("purchaseValue") or 0)
        if merge:
            existing = conn.execute(
                """
                SELECT purchase_value
                FROM purchases
                WHERE set_code = ? AND collector_number = ? AND finish = ?
                """,
                (set_code, collector_number, finish),
            ).fetchone()
            if existing is not None and _values_equal(existing["purchase_value"], purchase_value):
                continue
        conn.execute(
            """
            INSERT INTO purchases (set_code, collector_number, finish, purchase_value)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(set_code, collector_number, finish) DO UPDATE SET
                purchase_value = excluded.purchase_value
            """,
            (
                set_code,
                collector_number,
                finish,
                purchase_value,
            ),
        )


def _import_card_instances(conn: sqlite3.Connection, rows: list[dict], *, merge: bool) -> None:
    if not merge:
        conn.execute("DELETE FROM card_instances")
        rows_to_insert = rows
    else:
        db_counts = _count_card_instances(conn)
        backup_counts = Counter(_instance_identity_from_row(row) for row in rows)
        surplus = {
            key: backup_counts[key] - db_counts.get(key, 0)
            for key in backup_counts
        }
        rows_to_insert = []
        for row in rows:
            key = _instance_identity_from_row(row)
            if surplus.get(key, 0) > 0:
                rows_to_insert.append(row)
                surplus[key] -= 1

    for row in rows_to_insert:
        conn.execute(
            """
            INSERT INTO card_instances (
                set_code, collector_number, finish, location_slug, purchase_value
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                _normalize_set_code(row["setCode"]),
                _normalize_collector_number(row["collectorNumber"]),
                normalize_finish(row.get("finish")),
                str(row["locationSlug"]).strip(),
                _float_or_none(row.get("purchaseValue")),
            ),
        )


def _import_settings(conn: sqlite3.Connection, settings: dict, *, merge: bool) -> None:
    if not merge:
        placeholders = ",".join("?" for _ in EXPORT_SETTING_KEYS)
        conn.execute(
            f"DELETE FROM user_settings WHERE key IN ({placeholders})",
            tuple(sorted(EXPORT_SETTING_KEYS)),
        )
    for key, value in settings.items():
        if key not in EXPORT_SETTING_KEYS:
            continue
        text_value = str(value)
        if merge:
            existing = conn.execute(
                "SELECT value FROM user_settings WHERE key = ?",
                (key,),
            ).fetchone()
            if existing is not None and str(existing["value"]) == text_value:
                continue
        conn.execute(
            """
            INSERT INTO user_settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, text_value),
        )


def _import_art_styles(
    conn: sqlite3.Connection,
    art_styles: dict[str, list],
    *,
    merge: bool,
) -> None:
    import_art_style_rules(conn, art_styles, merge=merge)
