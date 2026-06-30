import sqlite3

from util.card_finishes import FINISH_ETCHED, FINISH_FOIL, FINISH_NONFOIL


def _table_has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(row[1] == column for row in rows)


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def _drop_orphan_migration_table(conn: sqlite3.Connection, table: str) -> None:
    orphan = f"{table}_new"
    if _table_exists(conn, orphan):
        conn.execute(f"DROP TABLE {orphan}")


def _ensure_etched_only_temp(conn: sqlite3.Connection) -> None:
    conn.execute("DROP TABLE IF EXISTS etched_only_prints")
    conn.execute(
        """
        CREATE TEMP TABLE etched_only_prints AS
        SELECT set_code, collector_number
        FROM cards
        WHERE COALESCE(has_etched, 0) = 1
          AND COALESCE(has_foil, 0) = 0
          AND COALESCE(has_nonfoil, 0) = 0
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_etched_only_prints
            ON etched_only_prints(set_code, collector_number)
        """
    )


def _finish_case_join_sql(*, foil_expr: str) -> str:
    return f"""
        CASE
            WHEN {foil_expr} = 0 AND e.set_code IS NOT NULL THEN {FINISH_ETCHED}
            WHEN {foil_expr} = 0 THEN {FINISH_NONFOIL}
            WHEN {foil_expr} = 1 AND e.set_code IS NOT NULL THEN {FINISH_ETCHED}
            ELSE {FINISH_FOIL}
        END
    """


def _backfill_card_finish_flags(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        UPDATE cards
        SET has_etched = 1
        WHERE COALESCE(has_nonfoil, 0) = 0
          AND COALESCE(has_foil, 0) = 0
          AND COALESCE(has_etched, 0) = 0
        """
    )
    conn.execute(
        """
        UPDATE cards
        SET market_value = NULL
        WHERE COALESCE(has_nonfoil, 0) = 0
          AND market_value IS NOT NULL
        """
    )
    conn.execute(
        """
        UPDATE cards
        SET market_value_foil = NULL
        WHERE COALESCE(has_foil, 0) = 0
          AND market_value_foil IS NOT NULL
        """
    )


def _refresh_deck_in_catalog(conn: sqlite3.Connection) -> None:
    if not _table_exists(conn, "deck_cards"):
        return
    conn.execute(
        """
        UPDATE deck_cards
        SET in_catalog = 1
        WHERE in_catalog = 0
          AND set_code IS NOT NULL
          AND collector_number IS NOT NULL
          AND EXISTS (
              SELECT 1
              FROM cards c
              WHERE c.set_code = deck_cards.set_code
                AND c.collector_number = deck_cards.collector_number
          )
        """
    )


def _migrate_purchases(conn: sqlite3.Connection) -> None:
    if not _table_exists(conn, "purchases") or _table_has_column(conn, "purchases", "finish"):
        return
    _drop_orphan_migration_table(conn, "purchases")
    finish_sql = _finish_case_join_sql(foil_expr="p.foil")
    conn.executescript(
        f"""
        CREATE TABLE purchases_new (
            purchase_id INTEGER PRIMARY KEY AUTOINCREMENT,
            set_code TEXT NOT NULL,
            collector_number TEXT NOT NULL,
            finish INTEGER NOT NULL CHECK (finish IN (0, 1, 2)),
            purchase_value REAL NOT NULL DEFAULT 0,
            UNIQUE (set_code, collector_number, finish)
        );
        INSERT INTO purchases_new (purchase_id, set_code, collector_number, finish, purchase_value)
        SELECT MIN(purchase_id), set_code, collector_number, finish, SUM(purchase_value)
        FROM (
            SELECT
                p.purchase_id,
                p.set_code,
                p.collector_number,
                {finish_sql} AS finish,
                p.purchase_value
            FROM purchases p
            LEFT JOIN etched_only_prints e
                ON e.set_code = p.set_code
               AND e.collector_number = p.collector_number
        )
        GROUP BY set_code, collector_number, finish;
        DROP TABLE purchases;
        ALTER TABLE purchases_new RENAME TO purchases;
        CREATE UNIQUE INDEX IF NOT EXISTS idx_purchases_card
            ON purchases(set_code, collector_number, finish);
        """
    )


def _migrate_card_prices(conn: sqlite3.Connection) -> None:
    if not _table_exists(conn, "card_prices") or _table_has_column(conn, "card_prices", "finish"):
        return
    _drop_orphan_migration_table(conn, "card_prices")
    finish_sql = _finish_case_join_sql(foil_expr="cp.foil")
    conn.executescript(
        f"""
        CREATE TABLE card_prices_new (
            price_id INTEGER PRIMARY KEY AUTOINCREMENT,
            set_code TEXT NOT NULL,
            collector_number TEXT NOT NULL,
            finish INTEGER NOT NULL CHECK (finish IN (0, 1, 2)),
            price REAL NOT NULL,
            source TEXT NOT NULL CHECK (source IN ('scryfall', 'cardmarket')),
            price_date TEXT NOT NULL,
            UNIQUE (set_code, collector_number, finish, source, price_date)
        );
        WITH converted AS (
            SELECT
                cp.price_id,
                cp.set_code,
                cp.collector_number,
                {finish_sql} AS finish,
                cp.price,
                cp.source,
                cp.price_date
            FROM card_prices cp
            LEFT JOIN etched_only_prints e
                ON e.set_code = cp.set_code
               AND e.collector_number = cp.collector_number
        ),
        ranked AS (
            SELECT
                price_id,
                set_code,
                collector_number,
                finish,
                price,
                source,
                price_date,
                ROW_NUMBER() OVER (
                    PARTITION BY set_code, collector_number, finish, source, price_date
                    ORDER BY price_id DESC
                ) AS rn
            FROM converted
        )
        INSERT INTO card_prices_new (
            price_id, set_code, collector_number, finish, price, source, price_date
        )
        SELECT price_id, set_code, collector_number, finish, price, source, price_date
        FROM ranked
        WHERE rn = 1;
        DROP TABLE card_prices;
        ALTER TABLE card_prices_new RENAME TO card_prices;
        CREATE INDEX IF NOT EXISTS idx_card_prices_lookup
            ON card_prices(set_code, collector_number, finish, price_date);
        """
    )


def _migrate_deck_cards(conn: sqlite3.Connection) -> None:
    if not _table_exists(conn, "deck_cards") or _table_has_column(conn, "deck_cards", "finish"):
        return
    _drop_orphan_migration_table(conn, "deck_cards")
    finish_sql = _finish_case_join_sql(foil_expr="dc.foil")
    conn.executescript(
        f"""
        CREATE TABLE deck_cards_new (
            deck_card_id INTEGER PRIMARY KEY AUTOINCREMENT,
            deck_id INTEGER NOT NULL,
            card_name TEXT NOT NULL,
            set_code TEXT,
            collector_number TEXT,
            finish INTEGER NOT NULL DEFAULT 0 CHECK (finish IN (0, 1, 2)),
            qty INTEGER NOT NULL DEFAULT 1 CHECK (qty > 0),
            owned_qty INTEGER NOT NULL DEFAULT 1 CHECK (owned_qty >= 0),
            section TEXT NOT NULL DEFAULT 'main',
            sort_order INTEGER NOT NULL DEFAULT 0,
            in_catalog INTEGER NOT NULL DEFAULT 0,
            UNIQUE (deck_id, set_code, collector_number, finish, section),
            FOREIGN KEY (deck_id) REFERENCES decks(deck_id) ON DELETE CASCADE
        );
        INSERT INTO deck_cards_new (
            deck_card_id, deck_id, card_name, set_code, collector_number, finish,
            qty, owned_qty, section, sort_order, in_catalog
        )
        SELECT
            MIN(deck_card_id),
            deck_id,
            MAX(card_name),
            set_code,
            collector_number,
            finish,
            SUM(qty),
            SUM(owned_qty),
            section,
            MIN(sort_order),
            MAX(in_catalog)
        FROM (
            SELECT
                dc.deck_card_id,
                dc.deck_id,
                dc.card_name,
                dc.set_code,
                dc.collector_number,
                {finish_sql} AS finish,
                dc.qty,
                dc.owned_qty,
                dc.section,
                dc.sort_order,
                dc.in_catalog
            FROM deck_cards dc
            LEFT JOIN etched_only_prints e
                ON e.set_code = dc.set_code
               AND e.collector_number = dc.collector_number
        )
        GROUP BY deck_id, set_code, collector_number, finish, section;
        DROP TABLE deck_cards;
        ALTER TABLE deck_cards_new RENAME TO deck_cards;
        CREATE INDEX IF NOT EXISTS idx_deck_cards_deck
            ON deck_cards(deck_id, sort_order);
        CREATE INDEX IF NOT EXISTS idx_deck_cards_print
            ON deck_cards(set_code, collector_number, finish);
        """
    )


def _migrate_card_instances(conn: sqlite3.Connection) -> None:
    if not _table_exists(conn, "card_instances") or _table_has_column(conn, "card_instances", "finish"):
        return
    _drop_orphan_migration_table(conn, "card_instances")
    finish_sql = _finish_case_join_sql(foil_expr="ci.foil")
    conn.executescript(
        f"""
        CREATE TABLE card_instances_new (
            instance_id INTEGER PRIMARY KEY AUTOINCREMENT,
            set_code TEXT NOT NULL,
            collector_number TEXT NOT NULL,
            finish INTEGER NOT NULL CHECK (finish IN (0, 1, 2)),
            location_slug TEXT NOT NULL
                REFERENCES storage_locations(location_slug),
            purchase_value REAL
        );
        INSERT INTO card_instances_new (
            instance_id, set_code, collector_number, finish, location_slug, purchase_value
        )
        SELECT
            ci.instance_id,
            ci.set_code,
            ci.collector_number,
            {finish_sql},
            ci.location_slug,
            ci.purchase_value
        FROM card_instances ci
        LEFT JOIN etched_only_prints e
            ON e.set_code = ci.set_code
           AND e.collector_number = ci.collector_number;
        DROP TABLE card_instances;
        ALTER TABLE card_instances_new RENAME TO card_instances;
        CREATE INDEX IF NOT EXISTS idx_card_instances_print
            ON card_instances(set_code, collector_number, finish);
        CREATE INDEX IF NOT EXISTS idx_card_instances_location
            ON card_instances(location_slug);
        """
    )


def ensure_finish_migration(conn: sqlite3.Connection) -> None:
    _backfill_card_finish_flags(conn)
    _ensure_etched_only_temp(conn)
    _migrate_purchases(conn)
    _migrate_card_prices(conn)
    _migrate_deck_cards(conn)
    _migrate_card_instances(conn)
    _refresh_deck_in_catalog(conn)
    conn.execute("DROP TABLE IF EXISTS etched_only_prints")
