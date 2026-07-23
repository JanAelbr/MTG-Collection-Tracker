import sqlite3
import tempfile
import unittest
from pathlib import Path

import runpy
import sys
from pathlib import Path

runpy.run_path(str(Path(__file__).resolve().with_name("_paths.py")))

from api.services import settings_service, storage_service  # noqa: E402
from util.app_tables import ensure_app_tables  # noqa: E402
from util.card_prices import CARD_PRICES_TABLE_SQL  # noqa: E402
from util.storage_tables import ensure_storage_tables  # noqa: E402


class StorageApiServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        ensure_storage_tables(self.conn)
        self.conn.execute(
            """
            CREATE TABLE cards (
                set_code TEXT,
                collector_number TEXT,
                name TEXT,
                art_style TEXT,
                image_uri TEXT,
                market_value REAL,
                market_value_foil REAL,
                cardmarket_url TEXT
            )
            """
        )
        ensure_app_tables(self.conn)
        self.conn.executescript(CARD_PRICES_TABLE_SQL)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        self.temp_dir.cleanup()

    def test_create_update_delete_custom_location(self):
        created = storage_service.create_location(
            self.conn,
            label="Trade binder",
            description="Cards for trades",
        )
        self.assertTrue(created["slug"].startswith("custom:"))
        self.assertEqual(created["locationType"], "storage")
        self.assertFalse(created["isSystem"])
        self.assertTrue(created["canDelete"])

        updated = storage_service.update_location(
            self.conn,
            created["slug"],
            label="Trade box",
        )
        self.assertEqual(updated["label"], "Trade box")

        storage_service.delete_location(self.conn, created["slug"])
        locations = storage_service.list_locations(self.conn)
        slugs = [item["slug"] for item in locations]
        self.assertNotIn(created["slug"], slugs)

    def test_storage_breakdown_aggregates_value_and_mix(self):
        from unittest.mock import patch

        from util.db_migrate import ensure_card_columns

        ensure_card_columns(self.conn)
        general = next(
            loc for loc in storage_service.list_locations(self.conn)
            if loc["slug"] == "storage:general"
        )
        binder = storage_service.create_location(
            self.conn,
            label="LTR binder",
            location_type="binder",
        )
        self.conn.execute(
            """
            INSERT INTO cards (
                set_code, collector_number, name, art_style, image_uri,
                market_value, market_value_foil, cardmarket_url
            ) VALUES
                ('LTR', '1', 'Card A', '', '', 10.0, 20.0, NULL),
                ('LTR', '2', 'Card B', '', '', 5.0, NULL, NULL)
            """
        )
        self.conn.executemany(
            """
            INSERT INTO card_instances (
                set_code, collector_number, finish, location_slug, purchase_value
            ) VALUES (?, ?, ?, ?, ?)
            """,
            [
                ("LTR", "1", 0, general["slug"], 4.0),
                ("LTR", "1", 1, binder["slug"], 8.0),
                ("LTR", "2", 0, general["slug"], 2.0),
            ],
        )
        self.conn.commit()

        def fake_price(_url, finish, _strategy, **_kwargs):
            return 20.0 if int(finish) == 1 else 10.0

        with patch("api.services.storage_service.price_from_strategy", side_effect=fake_price):
            result = storage_service.get_storage_breakdown(
                self.conn,
                general["slug"],
                price_strategy="trend",
            )
            binder_result = storage_service.get_storage_breakdown(
                self.conn,
                binder["slug"],
                price_strategy="trend",
            )

        totals = result["totals"]
        self.assertEqual(result["location"]["slug"], general["slug"])
        self.assertEqual(totals["copies"], 2)
        self.assertEqual(totals["uniquePrints"], 2)
        self.assertEqual(totals["current"], 20.0)
        self.assertEqual(totals["invested"], 6.0)
        self.assertNotIn("byType", result)
        self.assertNotIn("byLocation", result)
        self.assertTrue(result["byFinish"])
        self.assertEqual(result["bySet"][0]["setCode"], "LTR")
        self.assertEqual(len(result["topCards"]), 2)
        self.assertEqual(binder_result["totals"]["copies"], 1)

    def test_create_custom_binder(self):
        created = storage_service.create_location(
            self.conn,
            label="Modern trades",
            description="Cards for trade nights",
            location_type="binder",
        )
        self.assertTrue(created["slug"].startswith("binder:custom:"))
        self.assertEqual(created["locationType"], "binder")
        self.assertTrue(created["isCustom"])
        self.assertTrue(created["canDelete"])

    def test_delete_instance_updates_location(self):
        general = storage_service.get_location(self.conn, "storage:general")
        self.conn.execute(
            """
            INSERT INTO card_instances (
                set_code, collector_number, finish, location_slug, purchase_value
            ) VALUES ('LTR', '1', 0, ?, 1.0)
            """,
            (general["slug"],),
        )
        self.conn.commit()

        payload = storage_service.list_location_cards(
            self.conn,
            general["slug"],
            price_strategy="trend",
        )
        self.assertEqual(payload["totalCopies"], 1)
        instance_id = payload["cards"][0]["instanceIds"][0]

        storage_service.delete_instance(self.conn, instance_id)
        payload = storage_service.list_location_cards(
            self.conn,
            general["slug"],
            price_strategy="trend",
        )
        self.assertEqual(payload["totalCopies"], 0)

    def test_default_price_strategy(self):
        settings = settings_service.get_settings(self.conn)
        self.assertEqual(settings["priceStrategy"], "trend")
        self.assertIsNone(settings["favoritesCardsPriceStrategy"])
        self.assertIsNone(settings["favoritesArtStylesPriceStrategy"])
        self.assertGreater(len(settings["priceStrategies"]), 0)
        self.assertEqual(settings["pageSize"], 25)
        self.assertEqual(settings["pageSizeOptions"], [25, 50, 100])

    def test_favorites_price_strategy_overrides(self):
        updated = settings_service.update_settings(
            self.conn,
            favorites_cards_price_strategy="avg",
            favorites_art_styles_price_strategy="low",
        )
        self.assertEqual(updated["favoritesCardsPriceStrategy"], "avg")
        self.assertEqual(updated["favoritesArtStylesPriceStrategy"], "low")
        self.assertEqual(updated["priceStrategy"], "trend")

        settings = settings_service.get_settings(self.conn)
        self.assertEqual(settings["favoritesCardsPriceStrategy"], "avg")
        self.assertEqual(settings["favoritesArtStylesPriceStrategy"], "low")

    def test_page_size_setting(self):
        updated = settings_service.update_settings(self.conn, page_size=100)
        self.assertEqual(updated["pageSize"], 100)

        settings = settings_service.get_settings(self.conn)
        self.assertEqual(settings["pageSize"], 100)

        with self.assertRaises(settings_service.SettingsError):
            settings_service.update_settings(self.conn, page_size=75)

    def test_assert_location_assignable_rejects_deck(self):
        self.conn.execute(
            """
            INSERT INTO storage_locations (
                location_slug, label, location_type, sort_order, description, is_system
            ) VALUES ('deck:sample', 'Sample', 'deck', 10, '', 1)
            """
        )
        self.conn.commit()
        with self.assertRaises(storage_service.StorageError) as ctx:
            storage_service.assert_location_assignable(self.conn, "deck:sample")
        self.assertIn("deck ownership", ctx.exception.message.lower())

        ok = storage_service.assert_location_assignable(self.conn, "storage:general")
        self.assertEqual(ok["slug"], "storage:general")

    def test_delete_instance_rejects_deck_storage(self):
        self.conn.execute(
            """
            INSERT INTO storage_locations (
                location_slug, label, location_type, sort_order, description, is_system
            ) VALUES ('deck:sample', 'Sample', 'deck', 10, '', 1)
            """
        )
        self.conn.execute(
            """
            INSERT INTO card_instances (
                set_code, collector_number, finish, location_slug, purchase_value
            ) VALUES ('LTR', '1', 0, 'deck:sample', 1.0)
            """
        )
        self.conn.commit()
        instance_id = self.conn.execute(
            "SELECT instance_id FROM card_instances LIMIT 1"
        ).fetchone()[0]
        with self.assertRaises(storage_service.StorageError):
            storage_service.delete_instance(self.conn, instance_id)


if __name__ == "__main__":
    unittest.main()
