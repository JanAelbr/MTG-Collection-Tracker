import sqlite3
import tempfile
import unittest
from pathlib import Path

import runpy
import sys
from pathlib import Path

runpy.run_path(str(Path(__file__).resolve().with_name("_paths.py")))

from api.services import stats_service  # noqa: E402
from util.app_tables import ensure_app_tables  # noqa: E402
from util.db_migrate import ensure_card_columns  # noqa: E402
from util.storage_tables import ensure_storage_tables  # noqa: E402


class StatsApiServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        ensure_storage_tables(self.conn)
        self.conn.executescript(
            """
            CREATE TABLE cards (
                set_code TEXT,
                collector_number TEXT,
                name TEXT,
                art_style TEXT,
                image_uri TEXT,
                market_value REAL,
                market_value_foil REAL,
                market_value_etched REAL,
                has_nonfoil INTEGER,
                has_foil INTEGER,
                has_etched INTEGER,
                colors TEXT,
                type_line TEXT,
                card_type TEXT,
                cardmarket_url TEXT
            );
            CREATE TABLE purchases (
                purchase_id INTEGER PRIMARY KEY AUTOINCREMENT,
                set_code TEXT NOT NULL,
                collector_number TEXT NOT NULL,
                purchase_value REAL NOT NULL DEFAULT 0,
                finish INTEGER NOT NULL CHECK (finish IN (0, 1, 2)),
                UNIQUE (set_code, collector_number, finish)
            );
            CREATE TABLE card_prices (
                price_id INTEGER PRIMARY KEY AUTOINCREMENT,
                set_code TEXT NOT NULL,
                collector_number TEXT NOT NULL,
                finish INTEGER NOT NULL CHECK (finish IN (0, 1, 2)),
                price REAL NOT NULL,
                source TEXT NOT NULL CHECK (source IN ('scryfall', 'cardmarket')),
                price_date TEXT NOT NULL,
                UNIQUE (set_code, collector_number, finish, source, price_date)
            );
            CREATE TABLE sets (
                set_code TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                released_at TEXT,
                scryfall_uri TEXT,
                updated_at TEXT NOT NULL
            );
            """
        )
        ensure_card_columns(self.conn)
        self.conn.execute(
            """
            INSERT INTO cards (
                set_code, collector_number, name, art_style,
                market_value, market_value_foil, market_value_etched,
                has_nonfoil, has_foil, has_etched,
                colors, type_line, card_type, cardmarket_url
            ) VALUES ('LTR', '1', 'Test Card', 'Main', 2.0, 3.0, NULL, 1, 1, 0, NULL, NULL, NULL, NULL)
            """
        )
        self.conn.execute(
            """
            INSERT INTO purchases (set_code, collector_number, purchase_value, finish) VALUES ('LTR', '1', 1.0, 0)
            """
        )
        ensure_app_tables(self.conn)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        self.temp_dir.cleanup()

    def test_collection_stats_returns_summary(self):
        payload = stats_service.load_collection_stats(self.conn, set_code="LTR")
        self.assertEqual(payload["setCode"], "LTR")
        self.assertEqual(payload["stats"]["ownedCount"], 1)
        self.assertEqual(payload["stats"]["profit"], 1.0)
        self.assertEqual(len(payload["stats"]["artStyles"]), 1)
        self.assertEqual(payload["stats"]["setBreakdown"], [])

    def test_all_sets_stats_group_by_set(self):
        self.conn.execute(
            """
            INSERT INTO cards (
                set_code, collector_number, name, art_style,
                market_value, market_value_foil, market_value_etched,
                has_nonfoil, has_foil, has_etched,
                colors, type_line, card_type, cardmarket_url
            ) VALUES ('LTC', '1', 'Other Card', 'Main', 4.0, 5.0, NULL, 1, 1, 0, NULL, NULL, NULL, NULL)
            """
        )
        self.conn.execute(
            """
            INSERT INTO purchases (set_code, collector_number, purchase_value, finish)
            VALUES ('LTC', '1', 2.0, 0)
            """
        )
        self.conn.commit()

        payload = stats_service.load_collection_stats(self.conn, set_code="All")
        breakdown = payload["stats"]["setBreakdown"]
        self.assertEqual(len(breakdown), 2)
        self.assertEqual(
            {row["setCode"] for row in breakdown},
            {"LTR", "LTC"},
        )
        ltr = next(row for row in breakdown if row["setCode"] == "LTR")
        self.assertEqual(ltr["count"], 1)
        self.assertEqual(ltr["profit"], 1.0)


if __name__ == "__main__":
    unittest.main()
