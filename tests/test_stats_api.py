import runpy
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

runpy.run_path(str(Path(__file__).resolve().with_name("_paths.py")))

from api.cache import bump_cache_epoch  # noqa: E402
from api.services import stats_service  # noqa: E402
from util.app_tables import ensure_app_tables  # noqa: E402
from util.db_migrate import ensure_card_columns  # noqa: E402
from util.storage_tables import ensure_storage_tables  # noqa: E402


class StatsApiServiceTests(unittest.TestCase):
    def setUp(self):
        bump_cache_epoch()
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

    @patch("api.services.pricing_helpers.values_by_strategy_for_finish")
    def test_strategy_switch_reuses_valued_owned_cache(self, values_mock):
        values_mock.return_value = {"trend": 2.0, "low": 1.5}
        trend_payload = stats_service.load_collection_stats(self.conn, set_code="LTR")
        self.assertEqual(trend_payload["stats"]["profit"], 1.0)
        self.conn.execute(
            """
            INSERT OR REPLACE INTO user_settings (key, value)
            VALUES ('price_strategy', 'low')
            """
        )
        self.conn.commit()
        low_payload = stats_service.load_collection_stats(self.conn, set_code="LTR")
        self.assertEqual(low_payload["stats"]["profit"], 0.5)
        self.assertEqual(values_mock.call_count, 3)

    @patch("api.services.stats_service.load_owned_collection_data")
    def test_set_scoped_stats_loads_one_set(self, load_owned):
        import pandas as pd

        load_owned.return_value = pd.DataFrame([{
            "set_code": "LTR",
            "collector_number": "1",
            "name": "Test Card",
            "art_style": "Main",
            "finish": 0,
            "purchase_value": 1.0,
            "market_value": 2.0,
            "market_value_foil": 3.0,
            "market_value_etched": None,
            "has_nonfoil": 1,
            "has_foil": 1,
            "has_etched": 0,
            "cardmarket_url": None,
            "cardmarket_url_foil": None,
        }])
        stats_service.load_collection_stats(self.conn, set_code="LTR")
        load_owned.assert_called_once_with(self.conn, "LTR")

    def test_all_then_set_drilldown_reuses_owned_cache(self):
        stats_service.load_collection_stats(self.conn, set_code="All")
        with patch("api.services.stats_service.load_owned_collection_data") as load_owned:
            stats_service.load_collection_stats(self.conn, set_code="LTR")
            load_owned.assert_not_called()

    def test_vectorized_strategy_apply_matches_legacy_path(self):
        import pandas as pd

        from api.services.pricing_helpers import (
            _apply_strategy_from_price_columns,
            _apply_strategy_from_values_by_finish,
            build_neutral_owned_df,
        )

        raw = pd.DataFrame([{
            "set_code": "LTR",
            "collector_number": "1",
            "name": "Test Card",
            "art_style": "Main",
            "finish": 0,
            "purchase_value": 1.0,
            "market_value": 2.0,
            "market_value_foil": 3.0,
            "market_value_etched": None,
            "has_nonfoil": 1,
            "has_foil": 1,
            "has_etched": 0,
            "cardmarket_url": None,
            "cardmarket_url_foil": None,
        }])
        neutral = build_neutral_owned_df(raw)
        vectorized = _apply_strategy_from_price_columns(neutral, "trend")
        legacy = _apply_strategy_from_values_by_finish(neutral, "trend")
        self.assertEqual(vectorized["current_value"].iloc[0], legacy["current_value"].iloc[0])
        self.assertEqual(vectorized["profit_loss"].iloc[0], legacy["profit_loss"].iloc[0])


if __name__ == "__main__":
    unittest.main()
