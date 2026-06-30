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
        self.temp_dir = tempfile.TemporaryDirectory()
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
            })

    def tearDown(self):
        self.conn.close()
        self.temp_dir.cleanup()

    @patch("update_prices.update_cardmarket_prices_only")
    def test_start_and_complete_price_sync(self, mock_update_prices):
        mock_update_prices.return_value = None
        started = price_sync_service.start_price_sync()
        self.assertTrue(started["started"])

        deadline = time.time() + 2
        status = None
        while time.time() < deadline:
            status = price_sync_service.get_price_sync_status(self.conn)
            if status["status"] != "running":
                break
            time.sleep(0.05)

        self.assertEqual(status["status"], "completed")
        mock_update_prices.assert_called_once()

    @patch("update_prices.update_cardmarket_prices_only", side_effect=RuntimeError("boom"))
    def test_failed_price_sync_records_error(self, _mock_update_prices):
        price_sync_service.start_price_sync()

        deadline = time.time() + 2
        status = None
        while time.time() < deadline:
            status = price_sync_service.get_price_sync_status(self.conn)
            if status["status"] != "running":
                break
            time.sleep(0.05)

        self.assertEqual(status["status"], "failed")
        self.assertIn("boom", status["error"])

    @patch("update_prices.update_cardmarket_prices_only")
    def test_second_start_while_running_raises(self, mock_update_prices):
        started = threading.Event()

        def slow_update():
            started.set()
            time.sleep(0.3)

        mock_update_prices.side_effect = slow_update
        price_sync_service.start_price_sync()
        started.wait(timeout=1)
        with self.assertRaises(price_sync_service.PriceSyncError):
            price_sync_service.start_price_sync()


if __name__ == "__main__":
    unittest.main()
