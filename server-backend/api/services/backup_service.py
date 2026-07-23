import sqlite3

from api.cache import bump_cache_epoch
from lib.config import normalize_set_code
from lib.run_log import get_logger
from util.collection_backup import (
    BackupError,
    export_collection_zip,
    import_collection_zip,
    preview_backup,
)
from util.scryfall_catalog_sync import import_set_catalog_from_scryfall
from util.tracked_sets import add_tracked_set, is_set_tracked, remove_tracked_set

log = get_logger(__name__)


def build_export_bytes(conn: sqlite3.Connection) -> bytes:
    log.info("Building collection backup export")
    data = export_collection_zip(conn)
    log.info("Collection backup export ready (%s bytes)", len(data))
    return data


def preview_import_file(data: bytes) -> dict:
    try:
        return preview_backup(data)
    except BackupError as exc:
        raise BackupImportError(exc.message) from exc


def import_backup_file(conn: sqlite3.Connection, data: bytes, *, mode: str) -> dict:
    log.info("Importing collection backup (mode=%s, %s bytes)", mode, len(data))
    try:
        result = import_collection_zip(conn, data, mode=mode)
        bump_cache_epoch()
        log.info("Collection backup import completed (mode=%s)", mode)
        return result
    except BackupError as exc:
        log.warning("Collection backup import failed: %s", exc.message)
        raise BackupImportError(exc.message) from exc


def sync_catalogs_for_sets(conn: sqlite3.Connection, set_codes: list[str]) -> dict:
    synced: list[str] = []
    skipped: list[str] = []
    errors: list[dict[str, str]] = []
    seen: set[str] = set()

    log.info("Backup catalog sync starting for %s set code(s)", len(set_codes or []))
    for raw in set_codes or []:
        normalized = normalize_set_code(raw)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)

        card_count = conn.execute(
            "SELECT COUNT(*) FROM cards WHERE set_code = ?",
            (normalized,),
        ).fetchone()[0]
        tracked = is_set_tracked(conn, normalized)
        if card_count > 0 and tracked:
            skipped.append(normalized)
            continue

        added = False
        try:
            if not tracked:
                add_tracked_set(conn, normalized)
                added = True
            import_set_catalog_from_scryfall(conn, normalized)
            synced.append(normalized)
        except ValueError as exc:
            if added:
                remove_tracked_set(conn, normalized)
            errors.append({"setCode": normalized, "message": str(exc)})
            log.warning("Catalog sync failed for %s: %s", normalized, exc)
        except Exception as exc:
            if added:
                remove_tracked_set(conn, normalized)
            errors.append({"setCode": normalized, "message": str(exc)})
            log.exception("Catalog sync failed for %s", normalized)

    conn.commit()
    bump_cache_epoch()
    message = (
        f"Catalog sync finished: {len(synced)} imported, "
        f"{len(skipped)} already present, {len(errors)} failed."
    )
    log.info(message)
    return {
        "synced": synced,
        "skipped": skipped,
        "errors": errors,
        "message": message,
    }


class BackupImportError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message
