import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COLLECTION = ROOT / "server-backend" / "collection"
if str(COLLECTION) not in sys.path:
    sys.path.insert(0, str(COLLECTION))

from util.price_sync import upsert_card  # noqa: E402
from util.card_prices import (  # noqa: E402
    CARD_PRICES_TABLE_SQL,
    load_existing_card_prices,
    preserve_market_value,
    prune_owned_price_history,
    record_card_price,
    restore_market_values_from_history,
)
from util.db_migrate import ensure_card_columns  # noqa: E402


class PreserveMarketValueTests(unittest.TestCase):
    def test_uses_new_value_when_present(self):
        self.assertEqual(preserve_market_value(3.5, 1.0), 3.5)

    def test_keeps_existing_when_new_is_none(self):
        self.assertEqual(preserve_market_value(None, 1.0), 1.0)

    def test_returns_none_when_both_missing(self):
        self.assertIsNone(preserve_market_value(None, None))


class RestoreMarketValuesTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.conn = sqlite3.connect(Path(self.temp_dir.name) / "test.db")
        self.conn.executescript(
            """
            CREATE TABLE cards (
                id TEXT PRIMARY KEY,
                set_code TEXT NOT NULL,
                collector_number TEXT NOT NULL,
                name TEXT NOT NULL,
                art_style TEXT,
                market_value REAL,
                market_value_foil REAL,
                market_value_etched REAL,
                has_nonfoil INTEGER,
                has_foil INTEGER,
                has_etched INTEGER,
                image_uri TEXT,
                cardmarket_url TEXT
            );
            """
        )
        self.conn.executescript(CARD_PRICES_TABLE_SQL)
        ensure_card_columns(self.conn)
        self.conn.execute(
            """
            INSERT INTO cards (
                id, set_code, collector_number, name, art_style,
                market_value, market_value_foil, market_value_etched, has_nonfoil, has_foil, has_etched,
                image_uri, cardmarket_url
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("LTR-1", "LTR", "1", "Test Card", "Unknown", None, None, None, 1, 1, 0, None, None),
        )
        self.conn.executemany(
            """
            INSERT INTO card_prices (
                set_code, collector_number, finish, price, source, price_date
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                ("LTR", "1", 0, 4.0, "cardmarket", "2026-06-10"),
                ("LTR", "1", 0, 5.0, "cardmarket", "2026-06-14"),
                ("LTR", "1", 1, 9.0, "cardmarket", "2026-06-14"),
            ],
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        self.temp_dir.cleanup()

    def test_restore_market_values_from_history(self):
        restored = restore_market_values_from_history(self.conn)
        self.conn.commit()
        row = self.conn.execute(
            "SELECT market_value, market_value_foil FROM cards WHERE id = 'LTR-1'"
        ).fetchone()
        self.assertEqual(restored, 2)
        self.assertEqual(row, (5.0, 9.0))

    def test_prune_owned_price_history_keeps_two_dates_and_owned_only(self):
        self.conn.executescript(
            """
            CREATE TABLE purchases (
                set_code TEXT,
                collector_number TEXT,
                finish INTEGER,
                purchase_value REAL
            );
            """
        )
        self.conn.execute("DELETE FROM card_prices")
        self.conn.execute(
            "INSERT INTO purchases VALUES ('LTR', '1', 0, 1.0)"
        )
        self.conn.executemany(
            """
            INSERT INTO card_prices (
                set_code, collector_number, finish, price, source, price_date
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                ("LTR", "1", 0, 1.0, "cardmarket", "2026-06-10"),
                ("LTR", "1", 0, 2.0, "cardmarket", "2026-06-11"),
                ("LTR", "1", 0, 3.0, "cardmarket", "2026-06-12"),
                ("LTR", "2", 0, 9.0, "cardmarket", "2026-06-12"),
            ],
        )
        deleted_unowned, deleted_old = prune_owned_price_history(self.conn)
        rows = self.conn.execute(
            "SELECT set_code, collector_number, price_date FROM card_prices ORDER BY price_date"
        ).fetchall()
        self.assertEqual(deleted_unowned, 1)
        self.assertEqual(deleted_old, 1)
        self.assertEqual(
            rows,
            [("LTR", "1", "2026-06-11"), ("LTR", "1", "2026-06-12")],
        )

    def test_record_card_price_skips_unowned(self):
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS purchases (
                set_code TEXT,
                collector_number TEXT,
                finish INTEGER,
                purchase_value REAL
            );
            """
        )
        before = self.conn.execute("SELECT COUNT(*) FROM card_prices").fetchone()[0]
        record_card_price(
            self.conn, "LTR", "9", 0, 4.0, "cardmarket", "2026-06-15",
        )
        after = self.conn.execute("SELECT COUNT(*) FROM card_prices").fetchone()[0]
        self.assertEqual(after, before)


class UpsertCardPreserveTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.conn = sqlite3.connect(Path(self.temp_dir.name) / "test.db")
        self.conn.executescript(
            """
            CREATE TABLE cards (
                id TEXT PRIMARY KEY,
                set_code TEXT NOT NULL,
                collector_number TEXT NOT NULL,
                name TEXT NOT NULL,
                art_style TEXT,
                market_value REAL,
                market_value_foil REAL,
                market_value_etched REAL,
                has_nonfoil INTEGER,
                has_foil INTEGER,
                has_etched INTEGER,
                image_uri TEXT,
                cardmarket_url TEXT
            );
            """
        )
        self.conn.executescript(CARD_PRICES_TABLE_SQL)
        ensure_card_columns(self.conn)
        self.conn.execute(
            """
            INSERT INTO cards (
                id, set_code, collector_number, name, art_style,
                market_value, market_value_foil, market_value_etched, has_nonfoil, has_foil, has_etched,
                image_uri, cardmarket_url
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("LTR-42", "LTR", "42", "Old Name", "Unknown", 12.5, 25.0, None, 1, 1, 0, None, None),
        )
        self.conn.commit()
        self.cursor = self.conn.cursor()

    def tearDown(self):
        self.conn.close()
        self.temp_dir.cleanup()

    def test_upsert_preserves_existing_prices_without_recording_history(self):
        card = {
            "collector_number": "42",
            "name": "Updated Name",
            "type_line": "Legendary Creature — Human Wizard",
            "colors": ["U", "W"],
            "prices": {"eur": 99.0, "eur_foil": 199.0},
            "finishes": ["nonfoil", "foil"],
        }
        upsert_card(
            self.cursor,
            "ltr",
            card,
            "2026-06-15",
        )
        self.conn.commit()

        row = self.cursor.execute(
            """
            SELECT name, market_value, market_value_foil, colors, type_line, card_type
            FROM cards WHERE id = 'LTR-42'
            """
        ).fetchone()
        self.assertEqual(row[0], "Updated Name")
        self.assertEqual(row[1], 12.5)
        self.assertEqual(row[2], 25.0)
        self.assertEqual(row[3], '["W","U"]')
        self.assertEqual(row[4], "Legendary Creature — Human Wizard")
        self.assertEqual(row[5], "creature")

        price_rows = self.cursor.execute(
            """
            SELECT COUNT(*)
            FROM card_prices
            WHERE set_code = 'LTR' AND collector_number = '42'
            """
        ).fetchone()[0]
        self.assertEqual(price_rows, 0)

    def test_load_existing_card_prices_returns_none_for_missing_card(self):
        self.assertEqual(load_existing_card_prices(self.cursor, "ltr", "999"), (None, None, None))


if __name__ == "__main__":
    unittest.main()
