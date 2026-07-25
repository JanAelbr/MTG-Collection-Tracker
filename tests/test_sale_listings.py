"""Sale listings: for-sale catalog and sold archive."""

from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import runpy

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

runpy.run_path(str(TESTS_DIR / "_paths.py"))

from api.cache import bump_cache_epoch  # noqa: E402
from api.services import sale_listings_service  # noqa: E402
from lib.card_locations import sync_card_instances  # noqa: E402
from util.app_tables import ensure_app_tables  # noqa: E402
from util.deck_tables import ensure_deck_tables  # noqa: E402
from util.sale_listings import ensure_sale_listings_table  # noqa: E402


class SaleListingsServiceTests(unittest.TestCase):
    def setUp(self):
        bump_cache_epoch()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
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
                cardmarket_url TEXT,
                cardmarket_url_foil TEXT,
                colors TEXT,
                type_line TEXT,
                card_type TEXT,
                rarity TEXT
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
        ensure_deck_tables(self.conn)
        ensure_app_tables(self.conn)
        ensure_sale_listings_table(self.conn)
        self.conn.execute(
            """
            INSERT INTO cards (
                set_code, collector_number, name, art_style, image_uri,
                market_value, has_nonfoil, has_foil, has_etched, rarity
            ) VALUES ('LTR', '1', 'Frodo Baggins', '01. Main set', '', 2.0, 1, 0, 0, 'rare')
            """
        )
        self.conn.execute(
            """
            INSERT INTO purchases (set_code, collector_number, purchase_value, finish)
            VALUES ('LTR', '1', 1.5, 0)
            """
        )
        self.conn.execute(
            """
            INSERT INTO card_instances (
                set_code, collector_number, finish, location_slug, purchase_value
            ) VALUES ('LTR', '1', 0, 'storage:general', 1.5)
            """
        )
        self.conn.commit()
        self.instance_id = int(
            self.conn.execute("SELECT instance_id FROM card_instances").fetchone()[0]
        )
        self._patches = [
            patch("api.services.settings_service.get_settings", return_value={
                "priceStrategy": "trend",
                "compareDate": None,
            }),
            patch(
                "api.services.sale_listings_service.price_from_strategy",
                return_value=2.0,
            ),
        ]
        for item in self._patches:
            item.start()

    def tearDown(self):
        for item in reversed(self._patches):
            item.stop()
        self.conn.close()
        self.temp_dir.cleanup()

    def test_list_edit_sell_and_edit_sold_price(self):
        created = sale_listings_service.create_listing(
            self.conn,
            instance_id=self.instance_id,
            listing_price=3.5,
            notes="NM",
        )
        self.assertEqual(created["status"], "listed")
        self.assertEqual(created["listingPrice"], 3.5)
        self.assertEqual(created["instanceId"], self.instance_id)

        listed = sale_listings_service.list_listed(self.conn)
        self.assertEqual(listed["totalListings"], 1)
        self.assertEqual(listed["totalAsking"], 3.5)
        self.assertEqual(listed["cards"][0]["setCode"], "LTR")
        self.assertEqual(listed["cards"][0]["setLabel"], "LTR")

        from util.set_catalog import ensure_sets_table

        ensure_sets_table(self.conn)
        self.conn.execute(
            "INSERT OR REPLACE INTO sets (set_code, name, updated_at) VALUES ('LTR', 'The Lord of the Rings', '2026-01-01')"
        )
        self.conn.commit()
        listed_named = sale_listings_service.list_listed(self.conn)
        self.assertEqual(listed_named["cards"][0]["setLabel"], "The Lord of the Rings")

        updated = sale_listings_service.update_listed(
            self.conn,
            created["listingId"],
            listing_price=4.0,
        )
        self.assertEqual(updated["listingPrice"], 4.0)

        # Still owned while listed.
        owned = self.conn.execute("SELECT COUNT(*) FROM card_instances").fetchone()[0]
        self.assertEqual(owned, 1)
        purchase = self.conn.execute("SELECT COUNT(*) FROM purchases").fetchone()[0]
        self.assertEqual(purchase, 1)

        sold = sale_listings_service.mark_sold(
            self.conn,
            created["listingId"],
            sale_price=3.25,
        )
        self.assertEqual(sold["status"], "sold")
        self.assertEqual(sold["salePrice"], 3.25)
        self.assertIsNone(sold["instanceId"])
        self.assertEqual(sold["profitLoss"], 1.75)  # 3.25 - 1.5

        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM card_instances").fetchone()[0],
            0,
        )
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM purchases").fetchone()[0],
            0,
        )

        edited = sale_listings_service.update_sold(
            self.conn,
            created["listingId"],
            sale_price=5.0,
        )
        self.assertEqual(edited["salePrice"], 5.0)
        self.assertEqual(edited["profitLoss"], 3.5)

    def test_unlist_keeps_copy(self):
        created = sale_listings_service.create_listing(
            self.conn,
            instance_id=self.instance_id,
            listing_price=2.0,
        )
        sale_listings_service.unlist(self.conn, created["listingId"])
        self.assertEqual(sale_listings_service.list_listed(self.conn)["totalListings"], 0)
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM card_instances").fetchone()[0],
            1,
        )

    def test_listed_asking_lookups(self):
        sale_listings_service.create_listing(
            self.conn,
            instance_id=self.instance_id,
            listing_price=7.25,
        )
        by_print = sale_listings_service.listed_asking_by_print_key(self.conn)
        self.assertEqual(by_print.get("LTR|1|0"), 7.25)
        by_instance = sale_listings_service.listed_asking_by_instance_id(self.conn)
        self.assertEqual(by_instance.get(self.instance_id), 7.25)
        listings = sale_listings_service.listed_listings_by_instance_id(self.conn)
        self.assertEqual(listings[self.instance_id]["listingPrice"], 7.25)
        self.assertIsInstance(listings[self.instance_id]["listingId"], int)

    def test_rematch_after_instance_sync(self):
        created = sale_listings_service.create_listing(
            self.conn,
            instance_id=self.instance_id,
            listing_price=2.5,
        )
        # Full wipe + rebuild (sync) must rematch the open listing.
        sync_card_instances(self.conn)
        row = self.conn.execute(
            "SELECT instance_id FROM sale_listings WHERE listing_id = ?",
            (created["listingId"],),
        ).fetchone()
        self.assertIsNotNone(row["instance_id"])
        instance_exists = self.conn.execute(
            "SELECT 1 FROM card_instances WHERE instance_id = ?",
            (row["instance_id"],),
        ).fetchone()
        self.assertIsNotNone(instance_exists)


if __name__ == "__main__":
    unittest.main()
