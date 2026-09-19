import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import runpy
import sys
from pathlib import Path

runpy.run_path(str(Path(__file__).resolve().with_name("_paths.py")))

from api.services import price_sync_service  # noqa: E402
from util.app_tables import ensure_app_tables  # noqa: E402
from util.storage_tables import ensure_storage_tables  # noqa: E402


class PriceSyncServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.conn = sqlite3.connect(self.db_path)
        ensure_storage_tables(self.conn)
        self.conn.executescript(
            """
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
            """
        )
        ensure_app_tables(self.conn)
        self.conn.commit()
        with price_sync_service._lock:
            price_sync_service._state.update({
                "status": "idle",
                "started_at": None,
                "finished_at": None,
                "message": None,
                "error": None,
                "prices_unchanged": False,
                "movers": {"absolute": {"risers": [], "fallers": []}, "relative": {"risers": [], "fallers": []}},
                "cards": [],
            })
        self.snapshot_patcher = patch(
            "api.services.storage_service.record_daily_collection_snapshot",
            return_value={"id": 1},
        )
        self.snapshot_patcher.start()
        self.checked_patcher = patch("util.price_history.mark_price_sync_checked")
        self.checked_patcher.start()
        self.sync_cache = Path(self.temp_dir.name) / "last_price_sync.json"
        self.cache_patcher = patch(
            "util.last_price_sync.LAST_PRICE_SYNC_CACHE",
            self.sync_cache,
        )
        self.cache_patcher.start()

    def tearDown(self):
        self.cache_patcher.stop()
        self.checked_patcher.stop()
        self.snapshot_patcher.stop()
        self.conn.close()
        self.temp_dir.cleanup()

    @patch("util.price_sync.update_cardmarket_prices_only")
    def test_start_and_complete_price_sync(self, mock_update_prices):
        mock_update_prices.return_value = None
        started = price_sync_service.start_price_sync(self.conn)
        self.assertTrue(started["started"])

        deadline = time.time() + 2
        status = None
        while time.time() < deadline:
            status = price_sync_service.get_price_sync_status(self.conn)
            if status["status"] != "running":
                break
            time.sleep(0.05)

        self.assertEqual(status["status"], "completed")
        self.assertTrue(status["pricesUnchanged"])
        mock_update_prices.assert_called_once()
        kwargs = mock_update_prices.call_args.kwargs
        self.assertEqual(kwargs.get("set_codes"), set())
        self.assertEqual(kwargs.get("extra_qualifying_sets"), set())

    @patch("util.price_sync.update_cardmarket_prices_only", side_effect=RuntimeError("boom"))
    def test_failed_price_sync_records_error(self, _mock_update_prices):
        price_sync_service.start_price_sync(self.conn)

        deadline = time.time() + 2
        status = None
        while time.time() < deadline:
            status = price_sync_service.get_price_sync_status(self.conn)
            if status["status"] != "running":
                break
            time.sleep(0.05)

        self.assertEqual(status["status"], "failed")
        self.assertIn("boom", status["error"])

    @patch("util.price_sync.update_cardmarket_prices_only")
    def test_second_start_while_running_raises(self, mock_update_prices):
        started = threading.Event()

        def slow_update(**_kwargs):
            started.set()
            time.sleep(0.3)

        mock_update_prices.side_effect = slow_update
        price_sync_service.start_price_sync(self.conn)
        started.wait(timeout=1)
        with self.assertRaises(price_sync_service.PriceSyncError):
            price_sync_service.start_price_sync(self.conn)

    @patch("util.price_sync.update_cardmarket_prices_only")
    def test_default_sync_uses_favourite_sets(self, mock_update_prices):
        mock_update_prices.return_value = None
        self.conn.execute(
            "INSERT INTO user_settings (key, value) VALUES (?, ?)",
            ("favorite_sets", '["ltr"]'),
        )
        self.conn.commit()
        self.conn.row_factory = sqlite3.Row
        price_sync_service.start_price_sync(self.conn)

        deadline = time.time() + 2
        while time.time() < deadline:
            status = price_sync_service.get_price_sync_status(self.conn)
            if status["status"] != "running":
                break
            time.sleep(0.05)

        mock_update_prices.assert_called_once()
        self.assertEqual(mock_update_prices.call_args.kwargs.get("set_codes"), {"LTR"})
        self.assertEqual(mock_update_prices.call_args.kwargs.get("extra_qualifying_sets"), {"LTR"})

    @patch("util.price_sync.update_cardmarket_prices_only")
    def test_default_sync_includes_owned_sets(self, mock_update_prices):
        mock_update_prices.return_value = None
        self.conn.execute(
            "INSERT INTO user_settings (key, value) VALUES (?, ?)",
            ("favorite_sets", '["ltr"]'),
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS purchases (
                purchase_id INTEGER PRIMARY KEY AUTOINCREMENT,
                set_code TEXT NOT NULL,
                collector_number TEXT NOT NULL,
                purchase_value REAL NOT NULL DEFAULT 0,
                finish INTEGER NOT NULL CHECK (finish IN (0, 1, 2)),
                UNIQUE (set_code, collector_number, finish)
            )
            """
        )
        self.conn.execute(
            "INSERT INTO purchases (set_code, collector_number, purchase_value, finish) VALUES (?, ?, ?, ?)",
            ("MH3", "12", 0, 0),
        )
        self.conn.commit()
        self.conn.row_factory = sqlite3.Row
        price_sync_service.start_price_sync(self.conn)

        deadline = time.time() + 2
        while time.time() < deadline:
            status = price_sync_service.get_price_sync_status(self.conn)
            if status["status"] != "running":
                break
            time.sleep(0.05)

        mock_update_prices.assert_called_once()
        self.assertEqual(
            mock_update_prices.call_args.kwargs.get("set_codes"),
            {"LTR", "MH3"},
        )
        self.assertEqual(mock_update_prices.call_args.kwargs.get("extra_qualifying_sets"), {"LTR"})

    @patch("util.price_sync.update_cardmarket_prices_only")
    def test_explicit_set_code_syncs_that_set(self, mock_update_prices):
        mock_update_prices.return_value = None
        price_sync_service.start_price_sync(self.conn, set_code="mh3")

        deadline = time.time() + 2
        while time.time() < deadline:
            status = price_sync_service.get_price_sync_status(self.conn)
            if status["status"] != "running":
                break
            time.sleep(0.05)

        mock_update_prices.assert_called_once()
        self.assertEqual(mock_update_prices.call_args.kwargs.get("set_codes"), {"MH3"})
        self.assertEqual(mock_update_prices.call_args.kwargs.get("extra_qualifying_sets"), {"MH3"})

    @patch("api.cache.bump_cache_epoch")
    @patch("api.services.pricing_service.refresh_guide_cache")
    @patch("util.price_sync.update_cardmarket_prices_only")
    def test_applied_sync_returns_movers(self, mock_update_prices, _refresh, _bump):
        mock_update_prices.return_value = {
            "applied": True,
            "updated_fields": 2,
            "movers": {
                "risers": [{"id": "up", "label": "Up", "percent": 20, "delta": 2}],
                "fallers": [{"id": "down", "label": "Down", "percent": -10, "delta": -1}],
            },
        }
        price_sync_service.start_price_sync(self.conn)

        deadline = time.time() + 2
        status = None
        while time.time() < deadline:
            status = price_sync_service.get_price_sync_status(self.conn)
            if status["status"] != "running":
                break
            time.sleep(0.05)

        self.assertEqual(status["status"], "completed")
        self.assertFalse(status["pricesUnchanged"])
        self.assertEqual(status["movers"]["absolute"]["risers"][0]["label"], "Up")
        self.assertEqual(status["movers"]["absolute"]["fallers"][0]["label"], "Down")
        self.assertTrue(self.sync_cache.is_file())
        self.assertEqual(status["lastSync"]["movers"]["absolute"]["risers"][0]["label"], "Up")


if __name__ == "__main__":
    unittest.main()
