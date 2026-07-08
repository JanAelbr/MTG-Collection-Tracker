import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from report.card_detail_data import (  # noqa: E402
    load_card_detail_assets,
)
from util.card_prices import CARD_PRICES_TABLE_SQL  # noqa: E402
from util.set_catalog import SETS_TABLE_SQL  # noqa: E402


class CardDetailDataTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.conn = sqlite3.connect(self.db_path)
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
                has_nonfoil INTEGER,
                has_foil INTEGER,
                image_uri TEXT,
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
            """
        )
        self.conn.executescript(SETS_TABLE_SQL)
        self.conn.executescript(CARD_PRICES_TABLE_SQL)
        self.conn.execute(
            """
            INSERT INTO cards (
                id, set_code, collector_number, name, art_style,
                market_value, market_value_foil, has_nonfoil, has_foil,
                image_uri, cardmarket_url
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("LTR-1", "LTR", "1", "Test Card", "Main", 2.0, 3.0, 1, 1, None, None),
        )
        self.conn.execute(
            """
            INSERT INTO purchases (set_code, collector_number, purchase_value, finish) VALUES (?, ?, ?, ?)
            """,
            ("LTR", "1", 1.5, 0),
        )
        self.conn.executemany(
            """
            INSERT INTO card_prices (set_code, collector_number, finish, price, source, price_date)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                ("LTR", "1", 0, 1.0, "scryfall", "2026-06-10"),
                ("LTR", "1", 0, 2.0, "scryfall", "2026-06-16"),
            ],
        )
        self.conn.execute(
            """
            INSERT INTO sets (set_code, name, released_at, scryfall_uri, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("LTR", "Test Set", "2023-06-09", "https://scryfall.com/sets/ltr", "2026-06-16"),
        )
        self.conn.commit()

    def tearDown(self):
        if self.conn is not None:
            self.conn.close()
            self.conn = None
        self.temp_dir._ignore_cleanup_errors = True
        self.temp_dir.cleanup()

    def test_index_payload_omits_history_and_snapshots(self):
        with patch("report.card_detail_data.DB_PATH", self.db_path):
            self.conn.close()
            payload, histories = load_card_detail_assets()

        self.assertNotIn("snapshots", payload)
        finish = payload["cards"]["LTR|1"]["finishes"]["0"]
        self.assertNotIn("history", finish)
        self.assertNotIn("chart", finish)
        self.assertEqual(finish["purchase_value"], 1.5)
        self.assertEqual(finish["current_value"], 2.0)
        self.assertEqual(finish["previous_value"], 1.0)
        self.assertEqual(finish["price_change"], 1.0)
        self.assertIn("LTR", histories)
        self.assertIn("1|0", histories["LTR"])


if __name__ == "__main__":
    unittest.main()
