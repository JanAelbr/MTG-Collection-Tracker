import sqlite3

from api.cache import bump_cache_epoch
from util.collection_backup import (
    BackupError,
    export_collection_zip,
    import_collection_zip,
    preview_backup,
)


def build_export_bytes(conn: sqlite3.Connection) -> bytes:
    return export_collection_zip(conn)


def preview_import_file(data: bytes) -> dict:
    try:
        return preview_backup(data)
    except BackupError as exc:
        raise BackupImportError(exc.message) from exc


def import_backup_file(conn: sqlite3.Connection, data: bytes, *, mode: str) -> dict:
    try:
        result = import_collection_zip(conn, data, mode=mode)
        bump_cache_epoch()
        return result
    except BackupError as exc:
        raise BackupImportError(exc.message) from exc


class BackupImportError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message
