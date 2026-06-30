import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import runpy
import sys
from pathlib import Path

runpy.run_path(str(Path(__file__).resolve().with_name("_paths.py")))

from api.services import reports_service  # noqa: E402
from api.services import search_service  # noqa: E402
from api.cache import bump_cache_epoch  # noqa: E402
from util.app_tables import ensure_app_tables  # noqa: E402
from util.set_catalog import ensure_sets_table  # noqa: E402
from util.storage_tables import ensure_storage_tables  # noqa: E402


class ReportsApiServiceTests(unittest.TestCase):
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
            """
        )
        self.conn.execute(
            """
            INSERT INTO cards (
                set_code, collector_number, name, art_style,
                market_value, market_value_foil, market_value_etched, has_nonfoil, has_foil, has_etched, colors, type_line, card_type
            ) VALUES ('LTR', '1', 'Test Card', '01. Main set', 2.0, 4.0, NULL, 1, 1, 0, NULL, NULL, NULL)
            """
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

        self.ranked_rows = [{
            "set_code": "LTR",
            "collector_number": "1",
            "name": "Test Card",
            "art_style": "01. Main set",
            "finish": 0,
            "purchase_value": 1.0,
            "current_value": 2.0,
            "profit_loss": 1.0,
            "market_value": 2.0,
            "market_value_foil": 4.0,
            "market_value_etched": None,
            "image_uri": "",
            "cardmarket_url": "",
        }]

    def tearDown(self):
        self.conn.close()
        self.temp_dir.cleanup()

    @patch("api.services.reports_service.load_ranked_cards_data")
    def test_top_report_includes_locations_and_gain_loss(self, load_ranked):
        import pandas as pd

        load_ranked.return_value = pd.DataFrame(self.ranked_rows)
        payload = reports_service.list_report_cards(
            self.conn,
            report="top",
            set_code="LTR",
            page_size=25,
        )
        self.assertEqual(payload["totalMatches"], 1)
        card = payload["cards"][0]
        self.assertEqual(card["profitLoss"], 1.0)
        self.assertEqual(len(card["locations"]), 1)
        self.assertEqual(card["locations"][0]["slug"], "storage:general")

    @patch("api.services.reports_service.load_ranked_cards_data")
    def test_risers_require_positive_change(self, load_ranked):
        import pandas as pd

        load_ranked.return_value = pd.DataFrame(self.ranked_rows)
        payload = reports_service.list_report_cards(
            self.conn,
            report="risers",
            set_code="LTR",
            compare_date="2026-06-01",
            page_size=25,
        )
        self.assertEqual(payload["totalMatches"], 1)
        self.assertGreater(payload["cards"][0]["priceChange"], 0)

    def test_apply_filters_by_type_and_color(self):
        cards = [
            {
                "setCode": "LTR",
                "collectorNumber": "1",
                "artStyle": "",
                "finish": 0,
                "owned": True,
                "cardType": "creature",
                "colors": ["U"],
            },
            {
                "setCode": "LTR",
                "collectorNumber": "2",
                "artStyle": "",
                "finish": 0,
                "owned": True,
                "cardType": "instant",
                "colors": ["R"],
            },
        ]
        filtered = reports_service._apply_filters(
            cards,
            set_code="All",
            art_style="",
            owned_filter="all",
            foil_filter="all",
            type_filter="creature",
            color_filters=["U"],
        )
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["collectorNumber"], "1")

    def test_apply_filters_by_enchantment_type(self):
        cards = [
            {
                "setCode": "LTR",
                "collectorNumber": "1",
                "cardType": "enchantment",
                "colors": ["G"],
            },
            {
                "setCode": "LTR",
                "collectorNumber": "2",
                "cardType": "creature",
                "colors": ["G"],
            },
        ]
        filtered = reports_service._apply_filters(
            cards,
            set_code="All",
            art_style="",
            owned_filter="all",
            foil_filter="all",
            type_filter="enchantment",
            color_filters=[],
        )
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["collectorNumber"], "1")

    @patch("api.services.reports_service.load_ranked_cards_data")
    def test_instance_only_card_is_marked_owned(self, load_ranked):
        import pandas as pd

        self.conn.execute("DELETE FROM purchases")
        self.conn.commit()
        load_ranked.return_value = pd.DataFrame([{
            "set_code": "LTR",
            "collector_number": "1",
            "name": "Test Card",
            "art_style": "01. Main set",
            "finish": 0,
            "purchase_value": None,
            "current_value": 2.0,
            "profit_loss": None,
            "market_value": 2.0,
            "market_value_foil": 4.0,
            "market_value_etched": None,
            "image_uri": "",
            "cardmarket_url": "",
        }])
        payload = reports_service.list_report_cards(
            self.conn,
            report="all",
            set_code="LTR",
            owned_filter="all",
            page_size=25,
        )
        self.assertEqual(payload["totalMatches"], 1)
        self.assertTrue(payload["cards"][0]["owned"])
        self.assertEqual(len(payload["cards"][0]["locations"]), 1)

    @patch("api.services.reports_service.load_ranked_cards_data")
    def test_filter_changes_reuse_enriched_cache(self, load_ranked):
        import pandas as pd

        load_ranked.return_value = pd.DataFrame(self.ranked_rows)
        reports_service.list_report_cards(
            self.conn,
            report="top",
            set_code="All",
            page_size=25,
        )
        reports_service.list_report_cards(
            self.conn,
            report="risers",
            set_code="LTR",
            art_style="01. Main set",
            page_size=25,
        )
        load_ranked.assert_called_once()

    @patch("api.services.search_service._load_enriched_report_cards")
    def test_search_matches_name(self, load_enriched):
        load_enriched.return_value = (
            [
                {
                    "setCode": "LTR",
                    "collectorNumber": "1",
                    "name": "Frodo Baggins",
                    "artStyle": "01. Main set",
                    "finish": 0,
                    "owned": True,
                    "typeLine": "Legendary Creature — Halfling Scout",
                    "currentValue": 2.0,
                },
                {
                    "setCode": "LTR",
                    "collectorNumber": "2",
                    "name": "Samwise Gamgee",
                    "artStyle": "01. Main set",
                    "finish": 0,
                    "owned": False,
                    "typeLine": "Legendary Creature — Halfling Peasant",
                    "currentValue": 1.0,
                },
            ],
            "2024-01-01",
        )
        payload = search_service.search_cards(self.conn, search="frodo")
        self.assertEqual(payload["totalMatches"], 1)
        self.assertEqual(payload["cards"][0]["name"], "Frodo Baggins")

    @patch("api.services.search_service._load_enriched_report_cards")
    def test_search_empty_query_returns_no_cards(self, load_enriched):
        load_enriched.return_value = ([], None)
        payload = search_service.search_cards(self.conn, search="")
        self.assertEqual(payload["totalMatches"], 0)
        self.assertEqual(payload["cards"], [])

    @patch("api.services.search_service._load_enriched_report_cards")
    def test_random_name_explore(self, load_enriched):
        load_enriched.return_value = (
            [
                {
                    "setCode": "LTR",
                    "collectorNumber": "1",
                    "name": "Frodo Baggins",
                    "artStyle": "01. Main set",
                    "finish": 0,
                    "owned": True,
                    "typeLine": "",
                    "currentValue": 2.0,
                    "imageUri": "https://example.com/frodo.jpg",
                },
                {
                    "setCode": "LTR",
                    "collectorNumber": "1",
                    "name": "Frodo Baggins",
                    "artStyle": "01. Main set",
                    "finish": 1,
                    "owned": False,
                    "typeLine": "",
                    "currentValue": 4.0,
                    "imageUri": "https://example.com/frodo.jpg",
                },
            ],
            None,
        )
        payload = search_service.random_name_explore(self.conn, owned_filter="all")
        self.assertEqual(payload["name"], "Frodo Baggins")
        self.assertEqual(payload["totalVariants"], 1)
        self.assertEqual(len(payload["variants"][0]["availableFinishes"]), 2)

    @patch("api.services.search_service._load_enriched_report_cards")
    def test_list_name_variants(self, load_enriched):
        load_enriched.return_value = (
            [
                {
                    "setCode": "LTR",
                    "collectorNumber": "1",
                    "name": "Frodo Baggins",
                    "artStyle": "01. Main set",
                    "finish": 0,
                    "owned": True,
                    "currentValue": 2.0,
                },
                {
                    "setCode": "HOU",
                    "collectorNumber": "99",
                    "name": "Frodo Baggins",
                    "artStyle": "Borderless",
                    "finish": 0,
                    "owned": False,
                    "currentValue": 5.0,
                },
            ],
            None,
        )
        payload = search_service.list_name_variants(self.conn, name="Frodo Baggins")
        self.assertEqual(payload["totalVariants"], 2)
        set_codes = [variant["setCode"] for variant in payload["variants"]]
        self.assertEqual(set(set_codes), {"LTR", "HOU"})

    @patch("api.services.search_service._load_enriched_report_cards")
    def test_search_and_variants_order_newest_first(self, load_enriched):
        ensure_sets_table(self.conn)
        self.conn.executemany(
            """
            INSERT INTO sets (set_code, name, released_at, scryfall_uri, updated_at)
            VALUES (?, ?, ?, NULL, '2026-01-01')
            """,
            [
                ("LTR", "The Lord of the Rings", "2023-06-09"),
                ("MH3", "Modern Horizons 3", "2024-06-14"),
            ],
        )
        self.conn.commit()
        load_enriched.return_value = (
            [
                {
                    "setCode": "LTR",
                    "collectorNumber": "1",
                    "name": "Lightning Bolt",
                    "artStyle": "01. Main set",
                    "finish": 0,
                    "owned": False,
                    "typeLine": "Instant",
                    "currentValue": 1.0,
                },
                {
                    "setCode": "MH3",
                    "collectorNumber": "120",
                    "name": "Lightning Bolt",
                    "artStyle": "Borderless",
                    "finish": 0,
                    "owned": False,
                    "typeLine": "Instant",
                    "currentValue": 2.0,
                },
                {
                    "setCode": "LTR",
                    "collectorNumber": "2",
                    "name": "Shock",
                    "artStyle": "01. Main set",
                    "finish": 0,
                    "owned": False,
                    "typeLine": "Instant",
                    "currentValue": 1.0,
                },
                {
                    "setCode": "MH3",
                    "collectorNumber": "121",
                    "name": "Shock",
                    "artStyle": "Borderless",
                    "finish": 0,
                    "owned": False,
                    "typeLine": "Instant",
                    "currentValue": 1.5,
                },
            ],
            None,
        )
        search_payload = search_service.search_cards(self.conn, search="instant")
        self.assertEqual(search_payload["totalMatches"], 2)
        self.assertEqual(
            [card["setCode"] for card in search_payload["cards"]],
            ["MH3", "MH3"],
        )
        self.assertEqual(
            {card["name"] for card in search_payload["cards"]},
            {"Lightning Bolt", "Shock"},
        )

        variants_payload = search_service.list_name_variants(self.conn, name="Lightning Bolt")
        self.assertEqual(
            [variant["setCode"] for variant in variants_payload["variants"]],
            ["MH3", "LTR"],
        )

    @patch("api.services.search_service._load_enriched_report_cards")
    def test_random_card_empty_pool_returns_error(self, load_enriched):
        load_enriched.return_value = ([], None)
        with self.assertRaises(reports_service.ReportsError):
            search_service.random_name_explore(self.conn, owned_filter="owned")


if __name__ == "__main__":
    unittest.main()
