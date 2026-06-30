import sqlite3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from report.storage_data import (  # noqa: E402
    _load_location_summaries,
    load_storage_location_cards,
    location_script_filename,
)
from util.storage_tables import ensure_storage_tables, seed_storage_locations  # noqa: E402


class StorageDataTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        ensure_storage_tables(self.conn)
        self.conn.executescript(
            """
            CREATE TABLE cards (
                set_code TEXT NOT NULL,
                collector_number TEXT NOT NULL,
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
                card_type TEXT
            );
            CREATE TABLE decks (
                deck_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                slug TEXT NOT NULL UNIQUE
            );
            """
        )
        self.conn.execute(
            "INSERT INTO decks (deck_id, name, slug) VALUES (1, 'Food and Fellowship', 'food_and_fellowship')"
        )
        seed_storage_locations(self.conn)
        self.conn.executemany(
            """
            INSERT INTO cards (
                set_code, collector_number, name, art_style, image_uri,
                market_value, market_value_foil, market_value_etched,
                has_nonfoil, has_foil, has_etched,
                colors, type_line, card_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("LTR", "10", "Test Card", "Main", "http://img/10", 1.0, 2.0, None, 1, 1, 0, None, None, None),
                ("MH3", "100", "Deck Card", "Main", "http://img/100", 3.0, 4.0, None, 1, 1, 0, None, None, None),
            ],
        )
        self.conn.executemany(
            """
            INSERT INTO card_instances (
                set_code, collector_number, finish, location_slug, purchase_value
            ) VALUES (?, ?, ?, ?, ?)
            """,
            [
                ("LTR", "10", 0, "binder:ltr-black", 1.0),
                ("LTR", "10", 0, "binder:ltr-black", 1.0),
                ("MH3", "100", 0, "deck:food_and_fellowship", 3.0),
            ],
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_location_script_filename(self):
        self.assertEqual(
            location_script_filename("binder:ltr-black"),
            "binder_ltr-black.js",
        )

    def test_load_storage_location_cards_bulk(self):
        cards_by_location = load_storage_location_cards(self.conn)
        self.assertEqual(len(cards_by_location["binder:ltr-black"]), 1)
        self.assertEqual(cards_by_location["binder:ltr-black"][0]["copy_count"], 2)
        self.assertEqual(cards_by_location["deck:food_and_fellowship"][0]["name"], "Deck Card")

    def test_load_storage_location_summaries(self):
        summaries = _load_location_summaries(self.conn)
        slugs = {item["slug"] for item in summaries}
        self.assertIn("binder:ltr-black", slugs)
        self.assertIn("deck:food_and_fellowship", slugs)


if __name__ == "__main__":
    unittest.main()
