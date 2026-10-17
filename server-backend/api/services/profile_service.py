"""Profile management: registry rows plus their profile.db files."""

import sqlite3

from api.cache import bump_cache_epoch, bump_catalog_epoch
from lib.db import connect_profile, get_layout
from lib.profile_context import profile_scope
from lib.run_log import get_logger
from util.collection_backup import BackupError, import_collection, manifest_profile, parse_backup_zip
from util.profile_registry import (
    Profile,
    ProfileValidationError,
    delete_profile_row,
    get_profile,
    insert_profile,
    list_profiles,
    new_profile_id,
    reorder_profiles,
    touch_profile_last_used,
    unique_profile_name,
    update_profile,
    validate_new_profile,
)
from util.profile_store import (
    discard_profile_database,
    duplicate_profile_database,
    initialize_profile_database,
    profile_disk_size,
    trash_profile_database,
)

log = get_logger(__name__)
IMPORTED_PROFILE_NAME = "Imported collection"


class ProfileError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _require(profile_id: str) -> Profile:
    profile = get_profile(profile_id)
    if profile is None:
        raise ProfileError("Profile not found", status_code=404)
    return profile


def _count(conn: sqlite3.Connection, sql: str) -> int:
    try:
        return int(conn.execute(sql).fetchone()[0] or 0)
    except sqlite3.Error:
        return 0


OWNED_COPIES_SQL = """
SELECT p.set_code, p.collector_number, p.finish,
       MAX(1, COALESCE(ic.copies, 0)) AS copies
FROM purchases p
LEFT JOIN (
    SELECT set_code, collector_number, finish, COUNT(*) AS copies
    FROM card_instances
    GROUP BY set_code, collector_number, finish
) ic ON ic.set_code = p.set_code
    AND ic.collector_number = p.collector_number
    AND ic.finish = p.finish
"""

# Trend value of owned copies; a quick summary for the profile list.
PROFILE_VALUE_SQL = f"""
SELECT COALESCE(SUM(owned.copies * COALESCE(
    CASE owned.finish
        WHEN 1 THEN c.market_value_foil
        WHEN 2 THEN c.market_value_etched
        ELSE c.market_value
    END, 0)), 0)
FROM ({OWNED_COPIES_SQL}) owned
JOIN cards c ON c.set_code = owned.set_code AND c.collector_number = owned.collector_number
"""


def _value(conn: sqlite3.Connection, sql: str) -> float:
    try:
        return round(float(conn.execute(sql).fetchone()[0] or 0), 2)
    except sqlite3.Error:
        return 0.0


def _profile_stats(profile_id: str) -> dict:
    stats = {
        "ownedPrints": 0,
        "ownedCopies": 0,
        "decks": 0,
        "storageLocations": 0,
        "value": 0.0,
        "sizeBytes": 0,
    }
    try:
        conn = connect_profile(profile_id, row_factory=None)
    except (LookupError, sqlite3.Error):
        return stats
    try:
        stats["ownedPrints"] = _count(conn, "SELECT COUNT(*) FROM purchases")
        stats["ownedCopies"] = _count(
            conn, f"SELECT COALESCE(SUM(copies), 0) FROM ({OWNED_COPIES_SQL})"
        )
        stats["decks"] = _count(conn, "SELECT COUNT(*) FROM decks")
        stats["storageLocations"] = _count(
            conn, "SELECT COUNT(*) FROM storage_locations WHERE is_system = 0"
        )
        stats["value"] = _value(conn, PROFILE_VALUE_SQL)
    finally:
        conn.close()
    stats["sizeBytes"] = profile_disk_size(profile_id)
    return stats


def serialize_profile(profile: Profile, *, with_stats: bool = False) -> dict:
    payload = profile.to_api()
    if with_stats:
        payload["stats"] = _profile_stats(profile.id)
    return payload


def list_profiles_payload(*, with_stats: bool = False) -> dict:
    profiles = list_profiles()
    default_id = next((p.id for p in profiles if p.is_default), profiles[0].id if profiles else None)
    return {
        "profiles": [serialize_profile(profile, with_stats=with_stats) for profile in profiles],
        "defaultProfileId": default_id,
    }


def get_profile_payload(profile_id: str) -> dict:
    return serialize_profile(_require(profile_id), with_stats=True)


def create_profile(
    *,
    name: str,
    color: str | None = None,
    avatar: str | None = None,
    duplicate_from: str | None = None,
) -> dict:
    if duplicate_from:
        _require(duplicate_from)
    try:
        validate_new_profile(name=name, color=color, avatar=avatar)
    except ProfileValidationError as exc:
        raise ProfileError(str(exc)) from exc
    profile_id = new_profile_id()
    try:
        if duplicate_from:
            duplicate_profile_database(duplicate_from, profile_id)
        else:
            initialize_profile_database(profile_id)
        profile = insert_profile(name=name, color=color, avatar=avatar, profile_id=profile_id)
    except ProfileValidationError as exc:
        discard_profile_database(profile_id)
        raise ProfileError(str(exc)) from exc
    except Exception:
        discard_profile_database(profile_id)
        raise
    log.info(
        "Created profile %s (%s)%s",
        profile.name,
        profile.id,
        f" from {duplicate_from}" if duplicate_from else "",
    )
    return serialize_profile(profile, with_stats=True)


def patch_profile(
    profile_id: str,
    *,
    name: str | None = None,
    color: str | None = None,
    avatar: str | None = None,
    is_default: bool | None = None,
) -> dict:
    _require(profile_id)
    try:
        profile = update_profile(
            profile_id, name=name, color=color, avatar=avatar, is_default=is_default,
        )
    except ProfileValidationError as exc:
        raise ProfileError(str(exc)) from exc
    if profile is None:
        raise ProfileError("Profile not found", status_code=404)
    return serialize_profile(profile)


def delete_profile(profile_id: str) -> dict:
    profile = _require(profile_id)
    if len(list_profiles()) <= 1:
        raise ProfileError("The last profile cannot be deleted", status_code=409)
    try:
        trashed = trash_profile_database(profile_id)
    except OSError as exc:
        raise ProfileError(
            f"Could not move profile files to the trash: {exc}", status_code=409,
        ) from exc
    delete_profile_row(profile_id)
    bump_cache_epoch(profile_id)
    log.info("Deleted profile %s (%s)", profile.name, profile.id)
    return {
        "deleted": True,
        "profileId": profile_id,
        "trashPath": str(trashed) if trashed else None,
        **list_profiles_payload(),
    }


def activate_profile(profile_id: str) -> dict:
    _require(profile_id)
    touch_profile_last_used(profile_id)
    return serialize_profile(_require(profile_id))


def reorder(profile_ids: list[str]) -> dict:
    reorder_profiles(profile_ids)
    return list_profiles_payload()


def import_profile_from_backup(
    data: bytes,
    *,
    name: str | None = None,
    color: str | None = None,
) -> dict:
    """Create a new profile and restore a ``.mtgbackup.zip`` into it."""
    try:
        manifest, collection, art_styles = parse_backup_zip(data)
    except BackupError as exc:
        raise ProfileError(exc.message) from exc
    source = manifest_profile(manifest) or {}
    try:
        profile_name = unique_profile_name(name or source.get("name") or IMPORTED_PROFILE_NAME)
    except ProfileValidationError as exc:
        raise ProfileError(str(exc)) from exc

    profile_id = new_profile_id()
    try:
        initialize_profile_database(profile_id)
        conn = connect_profile(profile_id)
        try:
            with profile_scope(profile_id):
                result = import_collection(conn, collection, art_styles, mode="replace")
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        try:
            profile = insert_profile(
                name=profile_name,
                color=color or source.get("color"),
                avatar=source.get("avatar"),
                profile_id=profile_id,
            )
        except ProfileValidationError:
            profile = insert_profile(name=profile_name, profile_id=profile_id)
    except BackupError as exc:
        discard_profile_database(profile_id)
        raise ProfileError(exc.message) from exc
    except Exception:
        discard_profile_database(profile_id)
        raise
    if art_styles:
        bump_catalog_epoch()
    log.info("Imported backup into new profile %s (%s)", profile.name, profile.id)
    return {
        "profile": serialize_profile(profile, with_stats=True),
        "import": result,
    }


def export_profile_backup(profile_id: str) -> tuple[bytes, str]:
    from api.services.backup_service import build_export_bytes

    profile = _require(profile_id)
    conn = connect_profile(profile_id)
    try:
        with profile_scope(profile_id):
            payload = build_export_bytes(
                conn,
                profile={"name": profile.name, "color": profile.color, "avatar": profile.avatar},
            )
    finally:
        conn.close()
    return payload, profile.name


def storage_root() -> str:
    return str(get_layout().root)
