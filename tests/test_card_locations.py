import sqlite3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from lib.card_locations import (  # noqa: E402
    binder_location_for_print,
    deck_location_slug,
    sync_card_instances,
)
from util.storage_tables import ensure_storage_tables, seed_storage_locations  # noqa: E402


class CardLocationTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        ensure_storage_tables(self.conn)
        self.conn.executescript(
            """
            CREATE TABLE decks (
                deck_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                slug TEXT NOT NULL UNIQUE
            );
            CREATE TABLE deck_cards (
                deck_id INTEGER NOT NULL,
                set_code TEXT,
                collector_number TEXT,
                finish INTEGER NOT NULL DEFAULT 0 CHECK (finish IN (0, 1, 2)),
                owned_qty INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE purchases (
                set_code TEXT NOT NULL,
                collector_number TEXT NOT NULL,
                finish INTEGER NOT NULL CHECK (finish IN (0, 1, 2)),
                purchase_value REAL
            );
            """
        )
        self.conn.execute(
            "INSERT INTO decks (deck_id, name, slug) VALUES (1, 'Food and Fellowship', 'food_and_fellowship')"
        )
        seed_storage_locations(self.conn)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_binder_location_for_print(self):
        cases = [
            ("LTR", "1", "binder:ltr-black"),
            ("LTR", "398", "binder:ltr-black"),
            ("LTR", "399", "binder:ltr-blue"),
            ("LTR", "833", "binder:ltr-blue"),
            ("LTR", "834", "binder:ltr-blue"),
            ("LTC", "12", "binder:ltc-green"),
            ("MH3", "100", None),
        ]
        for set_code, collector_number, expected in cases:
            with self.subTest(set_code=set_code, collector_number=collector_number):
                self.assertEqual(
                    binder_location_for_print(set_code, collector_number),
                    expected,
                )

    def test_deck_location_slug(self):
        self.assertEqual(
            deck_location_slug("Food_And_Fellowship"),
            "deck:food_and_fellowship",
        )

    def test_sync_assigns_lotr_to_binders_and_other_sets_to_decks(self):
        self.conn.execute(
            """
            INSERT INTO deck_cards (deck_id, set_code, collector_number, finish, owned_qty)
            VALUES
                (1, 'LTR', '10', 0, 2),
                (1, 'LTR', '400', 0, 1),
                (1, 'LTC', '5', 0, 1),
                (1, 'MH3', '100', 0, 2)
            """
        )
        self.conn.commit()

        inserted = sync_card_instances(self.conn)
        self.assertEqual(inserted, 6)

        rows = self.conn.execute(
            """
            SELECT set_code, collector_number, location_slug, COUNT(*) AS copies
            FROM card_instances
            GROUP BY set_code, collector_number, location_slug
            ORDER BY set_code, collector_number
            """
        ).fetchall()
        self.assertEqual(
            rows,
            [
                ("LTC", "5", "binder:ltc-green", 1),
                ("LTR", "10", "binder:ltr-black", 2),
                ("LTR", "400", "binder:ltr-blue", 1),
                ("MH3", "100", "deck:food_and_fellowship", 2),
            ],
        )

    def test_sync_orphan_purchase_goes_to_general_storage(self):
        self.conn.execute(
            """
            INSERT INTO purchases (set_code, collector_number, finish, purchase_value)
            VALUES ('MH3', '200', 0, 1.5)
            """
        )
        self.conn.commit()

        sync_card_instances(self.conn)

        row = self.conn.execute(
            "SELECT location_slug, COUNT(*) FROM card_instances GROUP BY location_slug"
        ).fetchone()
        self.assertEqual(row, ("storage:general", 1))


if __name__ == "__main__":
    unittest.main()
