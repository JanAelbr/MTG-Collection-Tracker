import sqlite3

BINDER_LOCATIONS = (
    (
        "binder:ltr-black",
        "Black binder (LTR 1–398)",
        "binder",
        10,
        "LTR",
        "LTR collector numbers 1 through 398",
    ),
    (
        "binder:ltr-blue",
        "Blue binder (LTR 399–833)",
        "binder",
        20,
        "LTR",
        "LTR collector numbers 399 through 833",
    ),
    (
        "binder:ltc-green",
        "Green binder (LTC)",
        "binder",
        30,
        "LTC",
        "All LTC cards",
    ),
)

GENERAL_LOCATION = (
    "storage:general",
    "General storage",
    "storage",
    900,
    None,
    "Owned cards not assigned to a deck or LOTR binder",
)


# Create storage tables when missing.
def ensure_storage_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS storage_locations (
            location_slug TEXT PRIMARY KEY,
            label TEXT NOT NULL,
            location_type TEXT NOT NULL
                CHECK (location_type IN ('binder', 'deck', 'storage')),
            sort_order INTEGER NOT NULL DEFAULT 0,
            set_code TEXT,
            description TEXT,
            deck_id INTEGER REFERENCES decks(deck_id) ON DELETE SET NULL,
            is_system INTEGER NOT NULL DEFAULT 1 CHECK (is_system IN (0, 1))
        );

        CREATE TABLE IF NOT EXISTS card_instances (
            instance_id INTEGER PRIMARY KEY AUTOINCREMENT,
            set_code TEXT NOT NULL,
            collector_number TEXT NOT NULL,
            finish INTEGER NOT NULL CHECK (finish IN (0, 1, 2)),
            location_slug TEXT NOT NULL
                REFERENCES storage_locations(location_slug),
            purchase_value REAL
        );

        CREATE INDEX IF NOT EXISTS idx_card_instances_print
            ON card_instances(set_code, collector_number, finish);
        CREATE INDEX IF NOT EXISTS idx_card_instances_location
            ON card_instances(location_slug);
        """
    )
    _ensure_card_instances_finish_column(conn)
    _ensure_storage_location_columns(conn)


def _ensure_storage_location_columns(conn: sqlite3.Connection) -> None:
    columns = conn.execute("PRAGMA table_info(storage_locations)").fetchall()
    names = {row[1] for row in columns}
    if "is_system" not in names:
        conn.execute(
            "ALTER TABLE storage_locations ADD COLUMN is_system INTEGER NOT NULL DEFAULT 1 CHECK (is_system IN (0, 1))"
        )


def _ensure_card_instances_finish_column(conn: sqlite3.Connection) -> None:
    columns = conn.execute("PRAGMA table_info(card_instances)").fetchall()
    names = {row[1] for row in columns}
    if "finish" in names or "foil" not in names:
        return
    conn.executescript(
        """
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
            instance_id, set_code, collector_number, foil, location_slug, purchase_value
        FROM card_instances;
        DROP TABLE card_instances;
        ALTER TABLE card_instances_new RENAME TO card_instances;
        CREATE INDEX IF NOT EXISTS idx_card_instances_print
            ON card_instances(set_code, collector_number, finish);
        CREATE INDEX IF NOT EXISTS idx_card_instances_location
            ON card_instances(location_slug);
        """
    )


def _upsert_location(
    conn: sqlite3.Connection,
    slug: str,
    label: str,
    location_type: str,
    sort_order: int,
    set_code: str | None = None,
    description: str | None = None,
    deck_id: int | None = None,
    *,
    is_system: int = 1,
) -> None:
    conn.execute(
        """
        INSERT INTO storage_locations (
            location_slug, label, location_type, sort_order,
            set_code, description, deck_id, is_system
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(location_slug) DO UPDATE SET
            label = excluded.label,
            location_type = excluded.location_type,
            sort_order = excluded.sort_order,
            set_code = excluded.set_code,
            description = excluded.description,
            deck_id = excluded.deck_id,
            is_system = excluded.is_system
        """,
        (slug, label, location_type, sort_order, set_code, description, deck_id, is_system),
    )


# Seed binder locations and one row per registered deck.
def seed_storage_locations(conn: sqlite3.Connection) -> None:
    ensure_storage_tables(conn)
    for slug, label, location_type, sort_order, set_code, description in BINDER_LOCATIONS:
        _upsert_location(
            conn,
            slug,
            label,
            location_type,
            sort_order,
            set_code=set_code,
            description=description,
        )

    slug, label, location_type, sort_order, set_code, description = GENERAL_LOCATION
    _upsert_location(
        conn,
        slug,
        label,
        location_type,
        sort_order,
        set_code=set_code,
        description=description,
    )

    deck_table = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'decks'"
    ).fetchone()
    if not deck_table:
        return

    decks = conn.execute(
        "SELECT deck_id, name, slug FROM decks ORDER BY name"
    ).fetchall()
    for index, (deck_id, name, slug) in enumerate(decks, start=100):
        deck_slug = str(slug).lower()
        _upsert_location(
            conn,
            f"deck:{deck_slug}",
            name,
            "deck",
            index,
            deck_id=int(deck_id),
            description=f"Cards stored with the {name} deck",
        )
