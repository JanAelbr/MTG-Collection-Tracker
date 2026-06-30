import sqlite3
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from util.price_history import (  # noqa: E402
    compute_portfolio_history,
    default_compare_date,
    get_compare_dates,
    prices_are_outdated,
)


class PriceHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.conn = sqlite3.connect(self.db_path)
        self.conn.executescript(
            """
            CREATE TABLE cards (
                set_code TEXT,
                collector_number TEXT,
                market_value REAL,
                market_value_foil REAL
            );
            CREATE TABLE purchases (
                set_code TEXT,
                collector_number TEXT,
                finish INTEGER CHECK (finish IN (0, 1, 2)),
                purchase_value REAL
            );
            CREATE TABLE card_prices (
                set_code TEXT,
                collector_number TEXT,
                finish INTEGER CHECK (finish IN (0, 1, 2)),
                price REAL,
                source TEXT,
                price_date TEXT
            );
            """
        )
        self.conn.execute(
            "INSERT INTO cards VALUES ('LTR', '1', 10.0, 20.0)"
        )
        self.conn.execute(
            "INSERT INTO purchases VALUES ('LTR', '1', 0, 5.0)"
        )
        self.conn.executemany(
            "INSERT INTO card_prices VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("LTR", "1", 0, 8.0, "cardmarket", "2026-06-11"),
                ("LTR", "1", 0, 10.0, "cardmarket", "2026-06-12"),
            ],
        )
        self.conn.commit()

        self.owned_df = pd.DataFrame([{
            "set_code": "LTR",
            "collector_number": "1",
            "finish": 0,
            "purchase_value": 5.0,
            "current_value": 10.0,
            "profit_loss": 5.0,
        }])

    def tearDown(self):
        self.conn.close()
        self.temp_dir.cleanup()

    def test_get_compare_dates_excludes_latest(self):
        dates = ["2026-06-12", "2026-06-11"]
        self.assertEqual(get_compare_dates(dates), ["2026-06-11"])

    def test_default_compare_date_is_previous_snapshot(self):
        dates = ["2026-06-12", "2026-06-11"]
        self.assertEqual(default_compare_date(dates), "2026-06-11")

    def test_compute_portfolio_history_sums_owned_cards(self):
        history = compute_portfolio_history(self.conn, self.owned_df)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["date"], "2026-06-11")
        self.assertEqual(history[0]["value"], 8.0)
        self.assertEqual(history[-1]["date"], "2026-06-12")
        self.assertEqual(history[-1]["value"], 10.0)
        self.assertEqual(history[-1]["invested"], 5.0)

    def test_prices_are_outdated_when_snapshot_is_before_today(self):
        self.assertTrue(
            prices_are_outdated(self.conn, today=date(2026, 6, 13)),
        )

    def test_prices_are_current_when_snapshot_is_today(self):
        self.assertFalse(
            prices_are_outdated(self.conn, today=date(2026, 6, 12)),
        )

    def test_prices_are_outdated_when_no_snapshots_exist(self):
        empty = sqlite3.connect(":memory:")
        empty.execute(
            """
            CREATE TABLE card_prices (
                set_code TEXT,
                collector_number TEXT,
                finish INTEGER CHECK (finish IN (0, 1, 2)),
                price REAL,
                source TEXT,
                price_date TEXT
            )
            """
        )
        self.assertTrue(prices_are_outdated(empty, today=date(2026, 6, 12)))
        empty.close()


if __name__ == "__main__":
    unittest.main()
