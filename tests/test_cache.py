import runpy
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

runpy.run_path(str(Path(__file__).resolve().with_name("_paths.py")))

from api.cache import bump_cache_epoch, get_cache_epoch, memory_cache  # noqa: E402
from api.http_cache import serve_cached_json  # noqa: E402
from api.services import reports_service, settings_service  # noqa: E402
from util.app_tables import ensure_app_tables  # noqa: E402


class CacheTests(unittest.TestCase):
    def setUp(self):
        memory_cache.clear()

    def test_bump_cache_epoch_increments(self):
        first = get_cache_epoch()
        second = bump_cache_epoch()
        self.assertEqual(second, first + 1)

    def test_serve_cached_json_reuses_loader(self):
        request = Mock(headers={})
        loader = Mock(return_value={"value": 1})

        first = serve_cached_json(
            request,
            namespace="test.payload",
            params={"id": 1},
            ttl=60,
            loader=loader,
        )
        second = serve_cached_json(
            request,
            namespace="test.payload",
            params={"id": 1},
            ttl=60,
            loader=loader,
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.headers["ETag"], second.headers["ETag"])
        loader.assert_called_once()

    def test_serve_cached_json_returns_304_when_etag_matches(self):
        request = Mock(headers={})
        loader = Mock(return_value={"value": 1})

        first = serve_cached_json(
            request,
            namespace="test.payload",
            params={"id": 2},
            ttl=60,
            loader=loader,
        )
        etag = first.headers["ETag"]

        cached_request = Mock(headers={"if-none-match": etag})
        second = serve_cached_json(
            cached_request,
            namespace="test.payload",
            params={"id": 2},
            ttl=60,
            loader=loader,
        )

        self.assertEqual(second.status_code, 304)
        loader.assert_called_once()

    def test_bump_invalidates_cached_payload(self):
        request = Mock(headers={})
        loader = Mock(side_effect=[{"value": 1}, {"value": 2}])

        first = serve_cached_json(
            request,
            namespace="test.payload",
            params={"id": 3},
            ttl=60,
            loader=loader,
        )
        bump_cache_epoch()
        second = serve_cached_json(
            request,
            namespace="test.payload",
            params={"id": 3},
            ttl=60,
            loader=loader,
        )

        self.assertNotEqual(first.headers["ETag"], second.headers["ETag"])
        self.assertEqual(loader.call_count, 2)

    def test_price_strategy_update_does_not_bump_epoch(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        conn = sqlite3.connect(Path(temp_dir.name) / "test.db")
        self.addCleanup(conn.close)
        conn.row_factory = sqlite3.Row
        ensure_app_tables(conn)
        conn.commit()

        epoch_before = get_cache_epoch()
        conn.execute(
            """
            INSERT INTO user_settings (key, value)
            VALUES ('price_strategy', 'avg7')
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """
        )
        conn.commit()
        epoch_after = get_cache_epoch()
        self.assertEqual(epoch_before, epoch_after)
        self.assertEqual(settings_service.get_price_strategy(conn), "avg7")

    def test_per_set_enriched_cache_reused_across_strategies(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        conn = sqlite3.connect(Path(temp_dir.name) / "test.db")
        self.addCleanup(conn.close)
        conn.row_factory = sqlite3.Row
        ensure_app_tables(conn)
        conn.executescript(
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
                cardmarket_url TEXT,
                cardmarket_url_foil TEXT
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
        conn.execute(
            """
            INSERT INTO cards (
                set_code, collector_number, name, art_style,
                market_value, market_value_foil, has_nonfoil, has_foil, has_etched
            ) VALUES ('LTR', '1', 'Cached Card', '', 2.0, 4.0, 1, 1, 0)
            """
        )
        conn.commit()

        with patch(
            "api.services.reports_service.load_ranked_cards_data_for_set",
        ) as load_for_set, patch(
            "api.services.reports_service.values_by_strategy_for_finish",
            return_value={"trend": 2.0, "low": 1.5},
        ) as values_mock:
            import pandas as pd

            load_for_set.return_value = pd.DataFrame([{
                "set_code": "LTR",
                "collector_number": "1",
                "name": "Cached Card",
                "art_style": "",
                "finish": 0,
                "purchase_value": None,
                "current_value": 2.0,
                "profit_loss": None,
                "market_value": 2.0,
                "market_value_foil": 4.0,
                "market_value_etched": None,
                "has_nonfoil": 1,
                "has_foil": 1,
                "has_etched": 0,
                "image_uri": "",
                "cardmarket_url": "",
                "cardmarket_url_foil": "",
            }])
            first = reports_service.list_report_cards(
                conn,
                report="all",
                set_code="LTR",
                owned_filter="all",
            )
            conn.execute(
                """
                INSERT OR REPLACE INTO user_settings (key, value)
                VALUES ('price_strategy', 'low')
                """
            )
            conn.commit()
            second = reports_service.list_report_cards(
                conn,
                report="all",
                set_code="LTR",
                owned_filter="all",
            )

        self.assertEqual(first["cards"][0]["currentValue"], 2.0)
        self.assertEqual(second["cards"][0]["currentValue"], 1.5)
        self.assertEqual(values_mock.call_count, 1)
        load_for_set.assert_called_once()


if __name__ == "__main__":
    unittest.main()
