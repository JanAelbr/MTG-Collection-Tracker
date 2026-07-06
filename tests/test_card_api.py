import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import runpy
import sys
from pathlib import Path

runpy.run_path(str(Path(__file__).resolve().with_name("_paths.py")))

from api.services import card_service  # noqa: E402
from util.app_tables import ensure_app_tables  # noqa: E402
from util.card_prices import CARD_PRICES_TABLE_SQL  # noqa: E402
from util.set_catalog import SETS_TABLE_SQL  # noqa: E402
from util.storage_tables import ensure_storage_tables  # noqa: E402


class CardApiServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        ensure_storage_tables(self.conn)
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
            (
                "LTR-1",
                "LTR",
                "1",
                "Test Card",
                "Main",
                2.0,
                4.0,
                1,
                1,
                "https://example.test/card.jpg",
                None,
            ),
        )
        self.conn.execute(
            """
            INSERT INTO cards (
                id, set_code, collector_number, name, art_style,
                market_value, market_value_foil, has_nonfoil, has_foil,
                image_uri, cardmarket_url
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("LTR-2", "LTR", "2", "Other Card", "Main", 1.0, 2.0, 1, 0, None, None),
        )
        self.conn.execute(
            """
            INSERT INTO purchases (set_code, collector_number, purchase_value, finish) VALUES ('LTR', '1', 1.0, 0)
            """
        )
        self.conn.execute(
            """
            INSERT INTO card_instances (
                set_code, collector_number, finish, location_slug, purchase_value
            ) VALUES ('LTR', '1', 0, 'storage:general', 1.0)
            """
        )
        self.conn.execute(
            """
            INSERT INTO card_prices (
                set_code, collector_number, finish, price, source, price_date
            ) VALUES ('LTR', '1', 0, 1.5, 'cardmarket', '2026-06-01')
            """
        )
        ensure_app_tables(self.conn)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        self.temp_dir.cleanup()

    @patch("api.services.card_service.all_guide_prices_for_card")
    def test_load_card_detail_includes_guide_matrix_and_neighbors(self, guide_prices):
        guide_prices.return_value = {
            "nonfoil": {
                "trend": 2.0,
                "avg": 1.9,
                "avg7": 1.8,
                "avg30": 1.7,
                "avg1": 2.1,
                "low": 1.2,
            },
            "foil": {
                "trend": 4.0,
                "avg": 3.8,
                "avg7": 3.7,
                "avg30": 3.6,
                "avg1": 4.1,
                "low": 3.0,
            },
        }
        payload = card_service.load_card_detail(self.conn, "LTR", "1")
        self.assertEqual(payload["setCode"], "LTR")
        self.assertEqual(len(payload["guidePriceMatrix"]["rows"]), 6)
        self.assertEqual(payload["finishes"]["0"]["profitLoss"], 1.0)
        self.assertEqual(payload["finishes"]["0"]["locations"][0]["slug"], "storage:general")
        self.assertEqual(payload["setGallery"]["currentIndex"], 0)
        self.assertEqual(len(payload["setGallery"]["cards"]), 2)
        self.assertEqual(payload["setGallery"]["cards"][1]["collectorNumber"], "2")
        self.assertEqual(payload["finishes"]["0"]["guidePrices"]["trend"], 2.0)

    @patch("api.services.card_service.all_guide_prices_for_card")
    def test_load_card_detail_includes_owned_unpriced_finish(self, guide_prices):
        guide_prices.return_value = {}
        self.conn.execute(
            """
            INSERT INTO cards (
                id, set_code, collector_number, name, art_style,
                market_value, market_value_foil, has_nonfoil, has_foil,
                image_uri, cardmarket_url
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "LTR-3",
                "LTR",
                "3",
                "Etched Only Owned",
                "Main",
                None,
                None,
                0,
                0,
                None,
                None,
            ),
        )
        self.conn.execute(
            """
            INSERT INTO purchases (set_code, collector_number, purchase_value, finish)
            VALUES ('LTR', '3', 2.5, 2)
            """
        )
        self.conn.commit()

        payload = card_service.load_card_detail(self.conn, "LTR", "3", finish=2)

        self.assertIn("2", payload["finishes"])
        self.assertTrue(payload["finishes"]["2"]["owned"])
        self.assertEqual(payload["finishes"]["2"]["purchaseValue"], 2.5)
        self.assertIsNone(payload["finishes"]["2"]["currentValue"])

    def test_missing_card_raises(self):
        with self.assertRaises(card_service.CardError):
            card_service.load_card_detail(self.conn, "LTR", "999")


if __name__ == "__main__":
    unittest.main()
