"""Sale listings: for-sale catalog and sold archive."""

from __future__ import annotations

import sqlite3


def ensure_sale_listings_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sale_listings (
            listing_id INTEGER PRIMARY KEY AUTOINCREMENT,
            status TEXT NOT NULL CHECK (status IN ('listed', 'sold')),
            set_code TEXT NOT NULL,
            collector_number TEXT NOT NULL,
            finish INTEGER NOT NULL CHECK (finish IN (0, 1, 2)),
            listing_price REAL NOT NULL CHECK (listing_price >= 0),
            sale_price REAL,
            purchase_value REAL,
            location_slug TEXT,
            instance_id INTEGER,
            notes TEXT NOT NULL DEFAULT '',
            listed_at TEXT NOT NULL,
            sold_at TEXT,
            sort_order INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_sale_listings_status
            ON sale_listings(status, sort_order, listing_id)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_sale_listings_instance
            ON sale_listings(instance_id)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_sale_listings_print
            ON sale_listings(set_code, collector_number, finish, status)
        """
    )
