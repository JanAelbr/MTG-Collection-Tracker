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
        self.assertGreater(len(settings["priceStrategies"]), 0)
        self.assertEqual(settings["pageSize"], 25)
        self.assertEqual(settings["pageSizeOptions"], [25, 50, 100])

    def test_page_size_setting(self):
        updated = settings_service.update_settings(self.conn, page_size=100)
        self.assertEqual(updated["pageSize"], 100)

        settings = settings_service.get_settings(self.conn)
        self.assertEqual(settings["pageSize"], 100)

        with self.assertRaises(settings_service.SettingsError):
            settings_service.update_settings(self.conn, page_size=75)


if __name__ == "__main__":
    unittest.main()
