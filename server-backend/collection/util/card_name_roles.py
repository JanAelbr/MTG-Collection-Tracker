"""Persist inferred card roles keyed by card name (shared across printings)."""

from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime, timezone

from lib.run_log import format_duration, get_logger
from util.card_role_seed import card_roles_for

log = get_logger(__name__)

CARD_NAME_ROLES_BACKFILL_KEY = "card_name_roles_backfill_v1"


def ensure_card_name_roles_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS card_name_roles (
            name TEXT PRIMARY KEY COLLATE NOCASE,
            roles TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def serialize_roles(roles: list[str] | None) -> str:
    return json.dumps(list(roles or []), separators=(",", ":"))


def parse_roles(raw) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(role) for role in raw if role]
    text = str(raw).strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(role) for role in parsed if role]


def upsert_card_name_roles(
    conn: sqlite3.Connection,
    name: str,
    roles: list[str] | None = None,
    *,
    card: dict | None = None,
) -> list[str]:
    ensure_card_name_roles_table(conn)
    resolved_name = str(name or "").strip()
    if not resolved_name:
        return []
    resolved_roles = list(roles) if roles is not None else card_roles_for(card, name=resolved_name)
    conn.execute(
        """
        INSERT INTO card_name_roles (name, roles, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
            roles = excluded.roles,
            updated_at = excluded.updated_at
        """,
        (resolved_name, serialize_roles(resolved_roles), _utc_now()),
    )
    return resolved_roles


def load_card_name_roles_map(conn: sqlite3.Connection) -> dict[str, list[str]]:
    ensure_card_name_roles_table(conn)
    rows = conn.execute("SELECT name, roles FROM card_name_roles").fetchall()
    mapping: dict[str, list[str]] = {}
    for row in rows:
        name = str(row[0] or "").strip()
        if not name:
            continue
        mapping[name] = parse_roles(row[1])
        mapping[name.casefold()] = mapping[name]
    return mapping


def roles_for_card_name(conn: sqlite3.Connection, name: str) -> list[str]:
    ensure_card_name_roles_table(conn)
    resolved = str(name or "").strip()
    if not resolved:
        return []
    row = conn.execute(
        "SELECT roles FROM card_name_roles WHERE name = ? COLLATE NOCASE",
        (resolved,),
    ).fetchone()
    if row is None:
        return []
    return parse_roles(row[0])


def backfill_card_name_roles(conn: sqlite3.Connection, *, force: bool = False) -> int:
    """Fill card_name_roles from distinct catalog names. Returns upserted count."""
    from util.app_tables import ensure_app_tables

    ensure_card_name_roles_table(conn)
    ensure_app_tables(conn)

    if not force:
        row = conn.execute(
            "SELECT value FROM user_settings WHERE key = ?",
            (CARD_NAME_ROLES_BACKFILL_KEY,),
        ).fetchone()
        if row and row[0] == "done":
            log.debug("Card name roles backfill skipped (already done)")
            return 0

    started = time.perf_counter()
    rows = conn.execute(
        """
        SELECT name, type_line, oracle_text, card_type
        FROM cards
        WHERE name IS NOT NULL AND TRIM(name) != ''
        GROUP BY LOWER(TRIM(name))
        """
    ).fetchall()
    log.info("Backfilling card name roles for %s distinct name(s)", len(rows))

    upserted = 0
    for name, type_line, oracle_text, card_type in rows:
        card = {
            "name": name,
            "type_line": type_line,
            "oracle_text": oracle_text,
            "card_type": card_type,
        }
        upsert_card_name_roles(conn, str(name), card=card)
        upserted += 1

    conn.execute(
        """
        INSERT INTO user_settings (key, value)
        VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (CARD_NAME_ROLES_BACKFILL_KEY, "done"),
    )
    conn.commit()
    log.info(
        "Card name roles backfill finished: %s name(s) (%s)",
        upserted,
        format_duration(time.perf_counter() - started),
    )
    if upserted:
        try:
            from api.cache import bump_cache_epoch

            bump_cache_epoch()
        except ImportError:
            pass
    return upserted


def refresh_card_name_roles_for_card(conn: sqlite3.Connection, card: dict) -> list[str]:
    """Recompute and store roles for one catalog card's name."""
    name = str(card.get("name") or "").strip()
    if not name:
        return []
    return upsert_card_name_roles(conn, name, card=card)
