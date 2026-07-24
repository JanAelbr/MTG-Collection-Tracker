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
from util.db_migrate import ensure_card_columns  # noqa: E402
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
        ensure_card_columns(self.conn)
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
            "has_nonfoil": 1,
            "has_foil": 1,
            "has_etched": 0,
            "image_uri": "",
            "cardmarket_url": "",
            "cardmarket_url_foil": "",
        }]

    def tearDown(self):
        self.conn.close()
        self.temp_dir.cleanup()

    @patch("api.services.reports_service.values_by_strategy_for_finish")
    @patch("api.services.reports_service.load_ranked_cards_data_for_set")
    def test_top_report_includes_locations_and_gain_loss(self, load_ranked, values_mock):
        import pandas as pd

        values_mock.return_value = {
            "trend": 2.0,
            "avg": 2.0,
            "avg7": 2.0,
            "avg30": 2.0,
            "avg1": 2.0,
            "low": 1.5,
        }
        load_ranked.return_value = pd.DataFrame(self.ranked_rows)
        payload = reports_service.list_report_cards(
            self.conn,
            report="all",
            set_code="LTR",
            page_size=25,
        )
        self.assertEqual(payload["totalMatches"], 1)
        card = payload["cards"][0]
        self.assertEqual(card["profitLoss"], 1.0)
        self.assertEqual(len(card["locations"]), 1)
        self.assertEqual(card["locations"][0]["slug"], "storage:general")
        self.assertIn("valuesByStrategy", card)
        self.assertIn("trend", card["valuesByStrategy"])

    @patch("api.services.reports_service.values_by_strategy_for_finish")
    @patch("api.services.reports_service.load_ranked_cards_data_for_set")
    def test_risers_require_positive_change(self, load_ranked, values_mock):
        import pandas as pd

        values_mock.return_value = {
            "trend": 2.0,
            "avg": 2.0,
            "avg7": 2.0,
            "avg30": 2.0,
            "avg1": 2.0,
            "low": 1.5,
        }
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

    def test_apply_filters_by_color(self):
        cards = [
            {
                "setCode": "LTR",
                "collectorNumber": "1",
                "cardType": "creature",
                "colors": ["U"],
            },
            {
                "setCode": "LTR",
                "collectorNumber": "2",
                "cardType": "creature",
                "colors": ["R"],
            },
        ]
        filtered = reports_service._apply_filters(
            cards,
            set_code="All",
            art_style="",
            owned_filter="all",
            foil_filter="all",
            type_filter="all",
            color_filters=["U"],
        )
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["collectorNumber"], "1")

    @patch("api.services.reports_service.load_ranked_cards_data_for_set")
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
            "has_nonfoil": 1,
            "has_foil": 1,
            "has_etched": 0,
            "image_uri": "",
            "cardmarket_url": "",
            "cardmarket_url_foil": "",
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

    @patch("api.services.reports_service.load_ranked_cards_data_for_set")
    def test_all_report_includes_unpriced_unowned_catalog_cards(self, load_ranked):
        import pandas as pd

        load_ranked.return_value = pd.DataFrame([
            {
                "set_code": "HOB",
                "collector_number": "33",
                "name": "Bilbo, Thief in the Night",
                "art_style": "Main Set",
                "finish": 0,
                "purchase_value": None,
                "current_value": None,
                "profit_loss": None,
                "market_value": None,
                "market_value_foil": None,
                "market_value_etched": None,
                "has_nonfoil": 1,
                "has_foil": 0,
                "has_etched": 0,
                "image_uri": "https://example.com/bilbo.jpg",
                "cardmarket_url": "",
                "cardmarket_url_foil": "",
            },
            {
                "set_code": "LTR",
                "collector_number": "1",
                "name": "Priced Card",
                "art_style": "01. Main set",
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
            },
        ])
        payload = reports_service.list_report_cards(
            self.conn,
            report="all",
            set_code="HOB",
            owned_filter="all",
            page_size=25,
        )
        self.assertEqual(payload["totalMatches"], 1)
        card = payload["cards"][0]
        self.assertEqual(card["collectorNumber"], "33")
        self.assertIsNone(card["currentValue"])
        self.assertFalse(card["owned"])

    @patch("api.services.reports_service.load_ranked_cards_data_for_set")
    def test_top_report_still_excludes_unpriced_cards(self, load_ranked):
        import pandas as pd

        load_ranked.return_value = pd.DataFrame([
            {
                "set_code": "HOB",
                "collector_number": "33",
                "name": "Bilbo, Thief in the Night",
                "art_style": "Main Set",
                "finish": 0,
                "purchase_value": None,
                "current_value": None,
                "profit_loss": None,
                "market_value": None,
                "market_value_foil": None,
                "market_value_etched": None,
                "has_nonfoil": 1,
                "has_foil": 0,
                "has_etched": 0,
                "image_uri": "",
                "cardmarket_url": "",
                "cardmarket_url_foil": "",
            },
        ])
        payload = reports_service.list_report_cards(
            self.conn,
            report="all",
            set_code="HOB",
            owned_filter="all",
            page_size=25,
        )
        self.assertEqual(payload["totalMatches"], 0)
        self.assertEqual(payload["cards"], [])

    @patch("api.services.reports_service.load_ranked_cards_data_for_set")
    def test_filter_changes_reuse_enriched_cache(self, load_ranked):
        import pandas as pd

        load_ranked.return_value = pd.DataFrame(self.ranked_rows)
        reports_service.list_report_cards(
            self.conn,
            report="all",
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
        payload_text = search_service.search_cards(self.conn, text_search="")
        self.assertEqual(payload_text["totalMatches"], 0)
        self.assertEqual(payload_text["cards"], [])

    @patch("api.services.search_service._load_enriched_report_cards")
    def test_search_matches_oracle_text(self, load_enriched):
        load_enriched.return_value = (
            [
                {
                    "setCode": "LTR",
                    "collectorNumber": "1",
                    "name": "Lightning Bolt",
                    "artStyle": "01. Main set",
                    "finish": 0,
                    "owned": True,
                    "typeLine": "Instant",
                    "oracleText": "Lightning Bolt deals 3 damage to any target.",
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
                    "oracleText": "Shock deals 2 damage to any target.",
                    "currentValue": 1.0,
                },
            ],
            "2024-01-01",
        )
        payload = search_service.search_cards(self.conn, text_search="3 damage")
        self.assertEqual(payload["totalMatches"], 1)
        self.assertEqual(payload["cards"][0]["name"], "Lightning Bolt")

    @patch("api.services.search_service._load_enriched_report_cards")
    def test_search_matches_creature_type(self, load_enriched):
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
                    "name": "Lightning Bolt",
                    "artStyle": "01. Main set",
                    "finish": 0,
                    "owned": True,
                    "typeLine": "Instant",
                    "currentValue": 1.0,
                },
            ],
            "2024-01-01",
        )
        payload = search_service.search_cards(self.conn, creature_type_search="halfling")
        self.assertEqual(payload["totalMatches"], 1)
        self.assertEqual(payload["cards"][0]["name"], "Frodo Baggins")

    @patch("api.services.search_service._load_enriched_report_cards")
    def test_search_filters_by_role_or_match(self, load_enriched):
        load_enriched.return_value = (
            [
                {
                    "setCode": "LTR",
                    "collectorNumber": "1",
                    "name": "Cultivate",
                    "artStyle": "01. Main set",
                    "finish": 0,
                    "owned": True,
                    "typeLine": "Sorcery",
                    "roles": ["ramp"],
                    "currentValue": 2.0,
                },
                {
                    "setCode": "LTR",
                    "collectorNumber": "2",
                    "name": "Brainstorm",
                    "artStyle": "01. Main set",
                    "finish": 0,
                    "owned": True,
                    "typeLine": "Instant",
                    "roles": ["draw"],
                    "currentValue": 1.0,
                },
                {
                    "setCode": "LTR",
                    "collectorNumber": "3",
                    "name": "Swords to Plowshares",
                    "artStyle": "01. Main set",
                    "finish": 0,
                    "owned": True,
                    "typeLine": "Instant",
                    "roles": ["removal"],
                    "currentValue": 3.0,
                },
            ],
            "2024-01-01",
        )
        payload = search_service.search_cards(
            self.conn,
            role_filters=["ramp", "draw"],
        )
        self.assertEqual(payload["totalMatches"], 2)
        names = {card["name"] for card in payload["cards"]}
        self.assertEqual(names, {"Cultivate", "Brainstorm"})

    @patch("api.services.search_service._load_enriched_report_cards")
    def test_search_role_only_without_name(self, load_enriched):
        load_enriched.return_value = (
            [
                {
                    "setCode": "LTR",
                    "collectorNumber": "1",
                    "name": "Sol Ring",
                    "artStyle": "01. Main set",
                    "finish": 0,
                    "owned": True,
                    "typeLine": "Artifact",
                    "roles": ["ramp", "fast_mana"],
                    "currentValue": 2.0,
                },
            ],
            "2024-01-01",
        )
        payload = search_service.search_cards(self.conn, role_filters=["ramp"])
        self.assertEqual(payload["totalMatches"], 1)
        self.assertEqual(payload["cards"][0]["name"], "Sol Ring")
        self.assertEqual(payload["roleFilters"], ["ramp"])

    def test_parse_role_filters_normalizes_and_dedupes(self):
        self.assertEqual(
            search_service._parse_role_filters("ramp, DRAW, Ramp, bogus"),
            ["ramp", "draw"],
        )

    @patch("api.services.search_service._load_enriched_report_cards")
    def test_search_filters_by_storage(self, load_enriched):
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
                    "locations": [{"slug": "storage:general", "label": "General", "count": 2}],
                    "currentValue": 2.0,
                },
                {
                    "setCode": "LTR",
                    "collectorNumber": "2",
                    "name": "Samwise Gamgee",
                    "artStyle": "01. Main set",
                    "finish": 0,
                    "owned": True,
                    "typeLine": "Legendary Creature — Halfling Peasant",
                    "locations": [{"slug": "binder:lotr", "label": "LOTR Binder", "count": 1}],
                    "currentValue": 1.0,
                },
            ],
            "2024-01-01",
        )
        payload = search_service.search_cards(
            self.conn,
            search="",
            text_search="",
            type_filter="all",
            storage_filters=["binder:lotr"],
        )
        self.assertEqual(payload["totalMatches"], 0)

        payload = search_service.search_cards(
            self.conn,
            search="frodo",
            storage_filters=["storage:general"],
        )
        self.assertEqual(payload["totalMatches"], 1)
        self.assertEqual(payload["cards"][0]["name"], "Frodo Baggins")

    @patch("api.services.search_service._load_enriched_report_cards")
    def test_search_filters_by_type(self, load_enriched):
        load_enriched.return_value = (
            [
                {
                    "setCode": "LTR",
                    "collectorNumber": "1",
                    "name": "Lightning Bolt",
                    "artStyle": "01. Main set",
                    "finish": 0,
                    "owned": True,
                    "typeLine": "Instant",
                    "cardType": "instant",
                    "oracleText": "Lightning Bolt deals 3 damage to any target.",
                    "currentValue": 2.0,
                },
                {
                    "setCode": "LTR",
                    "collectorNumber": "2",
                    "name": "Grizzly Bears",
                    "artStyle": "01. Main set",
                    "finish": 0,
                    "owned": True,
                    "typeLine": "Creature — Bear",
                    "cardType": "creature",
                    "oracleText": "",
                    "currentValue": 0.1,
                },
            ],
            "2024-01-01",
        )
        payload = search_service.search_cards(
            self.conn,
            search="",
            text_search="damage",
            type_filter="instant",
        )
        self.assertEqual(payload["totalMatches"], 1)
        self.assertEqual(payload["cards"][0]["name"], "Lightning Bolt")

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
    def test_list_name_variants_keeps_unowned_prints_when_owned_filter_set(self, load_enriched):
        """Owned search still browses every printing, with prices on unowned ones."""
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
                    "valuesByStrategy": {"trend": 2.0},
                    "hasNonfoil": True,
                    "hasFoil": False,
                    "hasEtched": False,
                },
                {
                    "setCode": "HOU",
                    "collectorNumber": "99",
                    "name": "Frodo Baggins",
                    "artStyle": "Borderless",
                    "finish": 0,
                    "owned": False,
                    "currentValue": 5.0,
                    "valuesByStrategy": {"trend": 5.0},
                    "hasNonfoil": True,
                    "hasFoil": False,
                    "hasEtched": False,
                },
            ],
            None,
        )
        payload = search_service.list_name_variants(
            self.conn,
            name="Frodo Baggins",
            owned_filter="owned",
        )
        self.assertEqual(payload["ownedFilter"], "owned")
        self.assertEqual(payload["totalVariants"], 2)
        by_set = {variant["setCode"]: variant for variant in payload["variants"]}
        self.assertTrue(by_set["LTR"].get("owned"))
        self.assertFalse(by_set["HOU"].get("owned"))
        self.assertEqual(by_set["HOU"].get("finishValues", {}).get(0), 5.0)
        self.assertEqual(
            by_set["HOU"].get("finishValuesByStrategy", {}).get(0, {}).get("trend"),
            5.0,
        )
    @patch("api.services.search_service._resolve_set_codes", return_value=["LTR", "MH3"])
    @patch("api.services.search_service._load_enriched_report_cards")
    def test_search_and_variants_order_newest_first(self, load_enriched, _resolve_sets):
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
        search_payload = search_service.search_cards(self.conn, search="lightning")
        self.assertEqual(search_payload["totalMatches"], 1)
        self.assertEqual(search_payload["sort"], "newest")
        self.assertEqual(search_payload["dir"], "desc")
        self.assertEqual(
            [card["setCode"] for card in search_payload["cards"]],
            ["MH3"],
        )
        self.assertEqual(
            {card["name"] for card in search_payload["cards"]},
            {"Lightning Bolt"},
        )

        variants_payload = search_service.list_name_variants(self.conn, name="Lightning Bolt")
        self.assertEqual(
            [variant["setCode"] for variant in variants_payload["variants"]],
            ["MH3", "LTR"],
        )

    @patch("api.services.search_service._resolve_set_codes", return_value=["LTR", "MH3"])
    @patch("api.services.search_service._load_enriched_report_cards")
    def test_search_sort_by_name_and_value(self, load_enriched, _resolve_sets):
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
                    "cmc": 1.0,
                },
                {
                    "setCode": "MH3",
                    "collectorNumber": "120",
                    "name": "Lightning Bolt",
                    "artStyle": "Borderless",
                    "finish": 0,
                    "owned": False,
                    "typeLine": "Instant",
                    "currentValue": 5.0,
                    "cmc": 1.0,
                },
                {
                    "setCode": "LTR",
                    "collectorNumber": "2",
                    "name": "Shock",
                    "artStyle": "01. Main set",
                    "finish": 0,
                    "owned": False,
                    "typeLine": "Instant",
                    "currentValue": 3.0,
                    "cmc": 1.0,
                },
                {
                    "setCode": "MH3",
                    "collectorNumber": "121",
                    "name": "Shock",
                    "artStyle": "Borderless",
                    "finish": 0,
                    "owned": False,
                    "typeLine": "Instant",
                    "currentValue": 0.5,
                    "cmc": 1.0,
                },
            ],
            None,
        )

        by_name = search_service.search_cards(
            self.conn, creature_type_search="instant", sort="name", sort_dir="asc"
        )
        self.assertEqual(by_name["sort"], "name")
        self.assertEqual(by_name["dir"], "asc")
        self.assertEqual(
            [card["name"] for card in by_name["cards"]],
            ["Lightning Bolt", "Shock"],
        )

        by_value = search_service.search_cards(
            self.conn, creature_type_search="instant", sort="value", sort_dir="desc"
        )
        self.assertEqual(by_value["sort"], "value")
        self.assertEqual(by_value["dir"], "desc")
        # Sort before name dedupe: highest-value print per name is kept.
        self.assertEqual(
            [(card["name"], card["setCode"], card["currentValue"]) for card in by_value["cards"]],
            [
                ("Lightning Bolt", "MH3", 5.0),
                ("Shock", "LTR", 3.0),
            ],
        )

    @patch("api.services.reports_service.values_by_strategy_for_finish")
    def test_enrich_card_stores_values_by_strategy(self, values_mock):
        values_mock.return_value = {"trend": 144.91, "low": 250.0, "avg": 150.0}
        enriched = reports_service._enrich_card(
            {
                "set_code": "LTR",
                "collector_number": "790",
                "name": "The Ozolith",
                "art_style": "",
                "finish": 1,
                "purchase_value": None,
                "cardmarket_url": "https://www.cardmarket.com/en/Magic/Products?idProduct=100",
                "cardmarket_url_foil": "https://www.cardmarket.com/en/Magic/Products?idProduct=200",
                "market_value": 10.0,
                "market_value_foil": 144.91,
                "market_value_etched": None,
            },
            locations_map={},
            owned_keys=frozenset(),
            snapshot_prices={},
            compare_date=None,
        )
        self.assertEqual(enriched["valuesByStrategy"]["low"], 250.0)
        applied = reports_service._apply_strategy(
            {
                **enriched,
                "marketValue": 10.0,
                "marketValueFoil": 144.91,
                "marketValueEtched": None,
            },
            "low",
        )
        self.assertEqual(applied["currentValue"], 250.0)

    @patch("api.services.reports_service.values_by_strategy_for_finish")
    @patch("api.services.reports_service.load_ranked_cards_data_for_set")
    def test_strategy_switch_reuses_per_set_cache(self, load_ranked, values_mock):
        import pandas as pd

        values_mock.return_value = {"trend": 2.0, "low": 1.5}
        load_ranked.return_value = pd.DataFrame(self.ranked_rows)
        trend_payload = reports_service.list_report_cards(
            self.conn,
            report="all",
            set_code="LTR",
            page_size=25,
        )
        self.assertEqual(trend_payload["cards"][0]["currentValue"], 2.0)
        self.conn.execute(
            """
            INSERT OR REPLACE INTO user_settings (key, value)
            VALUES ('price_strategy', 'low')
            """
        )
        self.conn.commit()
        low_payload = reports_service.list_report_cards(
            self.conn,
            report="all",
            set_code="LTR",
            page_size=25,
        )
        load_ranked.assert_called_once()
        self.assertEqual(low_payload["cards"][0]["currentValue"], 1.5)

    @patch("api.services.reports_service.values_by_strategy_for_finish")
    @patch("api.services.reports_service.load_ranked_cards_data_for_set")
    def test_all_report_paginates_sorts_and_reports_scope_stats(self, load_ranked, values_mock):
        import pandas as pd

        values_mock.side_effect = lambda card, finish: {"trend": card.get("market_value")}
        rows = []
        for number, value in [("1", 2.0), ("2", 5.0), ("3", 1.0)]:
            rows.append({
                "set_code": "LTR",
                "collector_number": number,
                "name": f"Card {number}",
                "art_style": "01. Main set",
                "finish": 0,
                "purchase_value": None,
                "current_value": value,
                "profit_loss": None,
                "market_value": value,
                "market_value_foil": None,
                "market_value_etched": None,
                "has_nonfoil": 1,
                "has_foil": 0,
                "has_etched": 0,
                "image_uri": "",
                "cardmarket_url": "",
                "cardmarket_url_foil": "",
            })
        load_ranked.return_value = pd.DataFrame(rows)

        # Card "1" is already owned via setUp's purchase/instance rows; make "3" owned too.
        self.conn.execute(
            "INSERT INTO purchases (set_code, collector_number, purchase_value, finish) "
            "VALUES ('LTR', '3', 1.0, 0)"
        )
        self.conn.commit()

        first_page = reports_service.list_report_cards(
            self.conn,
            report="all",
            set_code="LTR",
            owned_filter="all",
            page_size=2,
            page=1,
            sort="value",
            sort_dir="desc",
        )
        self.assertEqual(first_page["totalMatches"], 3)
        self.assertEqual(first_page["totalPages"], 2)
        self.assertTrue(first_page["hasMore"])
        self.assertEqual(
            [card["collectorNumber"] for card in first_page["cards"]], ["2", "1"]
        )
        self.assertEqual(first_page["scopeStats"]["totalCount"], 3)
        self.assertEqual(first_page["scopeStats"]["ownedCount"], 2)

        second_page = reports_service.list_report_cards(
            self.conn,
            report="all",
            set_code="LTR",
            owned_filter="all",
            page_size=2,
            page=2,
            sort="value",
            sort_dir="desc",
        )
        self.assertFalse(second_page["hasMore"])
        self.assertEqual(
            [card["collectorNumber"] for card in second_page["cards"]], ["3"]
        )

        # Scope stats reflect the whole scope regardless of the interactive owned filter.
        owned_only = reports_service.list_report_cards(
            self.conn,
            report="all",
            set_code="LTR",
            owned_filter="owned",
            page_size=10,
            page=1,
        )
        self.assertEqual(owned_only["totalMatches"], 2)
        self.assertEqual(owned_only["scopeStats"]["totalCount"], 3)

    @patch("api.services.reports_service.values_by_strategy_for_finish")
    @patch("api.services.reports_service.load_ranked_cards_data_for_set")
    def test_all_report_search_matches_collector_number_and_name(self, load_ranked, values_mock):
        import pandas as pd

        values_mock.return_value = {"trend": 1.0}
        load_ranked.return_value = pd.DataFrame([
            {
                "set_code": "LTR", "collector_number": "42", "name": "Frodo Baggins",
                "art_style": "01. Main set", "finish": 0, "purchase_value": None,
                "current_value": 1.0, "profit_loss": None, "market_value": 1.0,
                "market_value_foil": None, "market_value_etched": None,
                "has_nonfoil": 1, "has_foil": 0, "has_etched": 0,
                "image_uri": "", "cardmarket_url": "", "cardmarket_url_foil": "",
            },
            {
                "set_code": "LTR", "collector_number": "7", "name": "Random Card",
                "art_style": "01. Main set", "finish": 0, "purchase_value": None,
                "current_value": 1.0, "profit_loss": None, "market_value": 1.0,
                "market_value_foil": None, "market_value_etched": None,
                "has_nonfoil": 1, "has_foil": 0, "has_etched": 0,
                "image_uri": "", "cardmarket_url": "", "cardmarket_url_foil": "",
            },
        ])

        by_number = reports_service.list_report_cards(
            self.conn, report="all", set_code="LTR", owned_filter="all", search="42",
        )
        self.assertEqual([card["collectorNumber"] for card in by_number["cards"]], ["42"])

        by_name = reports_service.list_report_cards(
            self.conn, report="all", set_code="LTR", owned_filter="all", search="frodo",
        )
        self.assertEqual([card["name"] for card in by_name["cards"]], ["Frodo Baggins"])


if __name__ == "__main__":
    unittest.main()
