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
                "progress": None,
                "processed": 0,
                "total": 0,
                "movers": {"absolute": {"risers": [], "fallers": []}, "relative": {"risers": [], "fallers": []}},
                "cards": [],
            })
        self.snapshot_patcher = patch(
            "api.services.storage_service.record_daily_collection_snapshot",
            return_value={"id": 1},
        )
        self.snapshot_mock = self.snapshot_patcher.start()
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
        self.assertEqual(status["progress"], 100)
        mock_update_prices.assert_called_once()
        kwargs = mock_update_prices.call_args.kwargs
        self.assertEqual(kwargs.get("set_codes"), set())
        self.assertEqual(kwargs.get("extra_qualifying_sets"), set())
        self.assertFalse(kwargs.get("force_cardmarket"))
        self.snapshot_mock.assert_not_called()

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
        self.snapshot_mock.assert_called()
        self.assertTrue(self.snapshot_mock.call_args.kwargs.get("skip_if_unchanged", True))

    @patch("api.cache.bump_cache_epoch")
    @patch("api.services.pricing_service.refresh_guide_cache")
    @patch("util.price_sync.update_cardmarket_prices_only")
    def test_force_sync_overwrites_snapshot_and_redownloads(self, mock_update_prices, _refresh, _bump):
        started = threading.Event()

        def slow_update(*, on_progress=None, force_cardmarket=False, **_kwargs):
            self.assertTrue(force_cardmarket)
            if on_progress:
                on_progress(42, "Comparing Cardmarket prices", processed=42, total=100)
            started.set()
            time.sleep(0.2)
            return {"applied": False, "updated_fields": 0, "movers": {}}

        mock_update_prices.side_effect = slow_update
        price_sync_service.start_price_sync(self.conn, force=True)
        started.wait(timeout=1)
        running = price_sync_service.get_price_sync_status(self.conn)
        self.assertEqual(running["status"], "running")
        self.assertEqual(running["progress"], 42)
        self.assertEqual(running["processed"], 42)
        self.assertEqual(running["total"], 100)
        self.assertIn("Comparing", running["message"])

        deadline = time.time() + 2
        status = None
        while time.time() < deadline:
            status = price_sync_service.get_price_sync_status(self.conn)
            if status["status"] != "running":
                break
            time.sleep(0.05)

        self.assertEqual(status["status"], "completed")
        self.assertEqual(status["progress"], 100)
        self.assertIn("matched", status["message"])
        self.snapshot_mock.assert_called()
        self.assertFalse(self.snapshot_mock.call_args.kwargs.get("skip_if_unchanged", True))

    @patch("util.price_sync.update_cardmarket_prices_only")
    def test_unchanged_sync_keeps_previous_card_diffs(self, mock_update_prices):
        from util.last_price_sync import save_last_price_sync

        save_last_price_sync(
            {
                "applied": True,
                "pricesUnchanged": False,
                "message": "Price sync completed",
                "movers": {
                    "absolute": {"risers": [{"id": "LTR|1|0", "delta": 4}], "fallers": []},
                    "relative": {"risers": [{"id": "LTR|1|0", "percent": 10}], "fallers": []},
                },
                "cards": [{
                    "id": "LTR|1|0",
                    "setCode": "LTR",
                    "collectorNumber": "1",
                    "artStyle": "Showcase",
                    "delta": 4,
                }],
            },
            path=self.sync_cache,
        )
        mock_update_prices.return_value = {"applied": False, "updated_fields": 0, "movers": {}, "cards": []}
        price_sync_service.start_price_sync(self.conn)

        deadline = time.time() + 2
        status = None
        while time.time() < deadline:
            status = price_sync_service.get_price_sync_status(self.conn)
            if status["status"] != "running":
                break
            time.sleep(0.05)

        self.assertEqual(status["status"], "completed")
        self.assertTrue(status["pricesUnchanged"])
        self.assertEqual(status["cards"][0]["id"], "LTR|1|0")
        self.assertEqual(status["movers"]["absolute"]["risers"][0]["id"], "LTR|1|0")

    def test_status_hydrates_missing_card_images(self):
        from util.last_price_sync import save_last_price_sync

        self.conn.executescript(
            """
            CREATE TABLE cards (
                set_code TEXT,
                collector_number TEXT,
                name TEXT,
                image_uri TEXT
            );
            """
        )
        self.conn.execute(
            "INSERT INTO cards VALUES (?, ?, ?, ?)",
            ("LTR", "1", "Gandalf", "https://example.com/gandalf.jpg"),
        )
        self.conn.commit()
        save_last_price_sync(
            {
                "applied": True,
                "cards": [{
                    "id": "LTR|1|0",
                    "setCode": "LTR",
                    "collectorNumber": "1",
                    "artStyle": "Showcase",
                    "delta": 4,
                }],
            },
            path=self.sync_cache,
        )
        status = price_sync_service.get_price_sync_status(self.conn)
        self.assertEqual(status["cards"][0]["name"], "Gandalf")
        self.assertEqual(status["cards"][0]["imageUri"], "https://example.com/gandalf.jpg")

    def test_list_art_style_card_movers_uses_previous_prices(self):
        self.conn.executescript(
            """
            CREATE TABLE cards (
                id TEXT PRIMARY KEY,
                set_code TEXT,
                collector_number TEXT,
                name TEXT,
                art_style TEXT,
                market_value REAL,
                market_value_foil REAL,
                market_value_etched REAL,
                has_nonfoil INTEGER,
                has_foil INTEGER,
                has_etched INTEGER
            );
            """
        )
        self.conn.execute(
            """
            INSERT INTO cards (
                id, set_code, collector_number, name, art_style,
                market_value, market_value_foil, market_value_etched,
                has_nonfoil, has_foil, has_etched
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("LTR-1", "LTR", "1", "Gandalf", "Showcase", 12.0, None, None, 1, 0, 0),
        )
        self.conn.execute(
            """
            INSERT INTO card_prices (
                set_code, collector_number, finish, price, source, price_date
            ) VALUES
                ('LTR', '1', 0, 10.0, 'cardmarket', '2026-09-18'),
                ('LTR', '1', 0, 12.0, 'cardmarket', '2026-09-19')
            """
        )
        self.conn.commit()
        cards = price_sync_service.list_art_style_card_movers(
            self.conn,
            set_code="ltr",
            art_style="Showcase",
        )
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["label"], "Gandalf (Non-foil)")
        self.assertEqual(cards[0]["collectorNumber"], "1")
        self.assertEqual(cards[0]["previous"], 10.0)
        self.assertEqual(cards[0]["current"], 12.0)


if __name__ == "__main__":
    unittest.main()
