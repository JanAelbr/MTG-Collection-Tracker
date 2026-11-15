"""Persist inferred card roles keyed by card name (shared across printings)."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from lib.db import is_attached_table
from util.card_role_seed import card_roles_for


def ensure_card_name_roles_table(conn: sqlite3.Connection) -> None:
    if is_attached_table(conn, "card_name_roles"):
        return
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


def refresh_card_name_roles_for_card(conn: sqlite3.Connection, card: dict) -> list[str]:
    """Recompute and store roles for one catalog card's name."""
    name = str(card.get("name") or "").strip()
    if not name:
        return []
    return upsert_card_name_roles(conn, name, card=card)
