import sqlite3
import tempfile
import unittest
from pathlib import Path

import runpy
import sys
from pathlib import Path

runpy.run_path(str(Path(__file__).resolve().with_name("_paths.py")))

from api.services import decks_service  # noqa: E402
from util.app_tables import ensure_app_tables  # noqa: E402
from util.deck_tables import ensure_deck_tables  # noqa: E402
from util.storage_tables import ensure_storage_tables, seed_storage_locations  # noqa: E402


class DecksApiServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        ensure_storage_tables(self.conn)
        ensure_deck_tables(self.conn)
        self.conn.executescript(
            """
            CREATE TABLE cards (
                id TEXT PRIMARY KEY,
                set_code TEXT NOT NULL,
                collector_number TEXT NOT NULL,
                name TEXT NOT NULL,
                art_style TEXT,
                market_value REAL,
                market_value_foil REAL,
                market_value_etched REAL,
                has_nonfoil INTEGER,
                has_foil INTEGER,
                has_etched INTEGER,
                colors TEXT,
                type_line TEXT,
                card_type TEXT,
                image_uri TEXT,
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
                source TEXT NOT NULL,
                price_date TEXT NOT NULL
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
        self.conn.execute(
            """
            INSERT INTO cards (
                id, set_code, collector_number, name, art_style,
                market_value, market_value_foil, market_value_etched, has_nonfoil, has_foil, has_etched,
                colors, type_line, card_type, image_uri, cardmarket_url
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "LTC-284",
                "LTC",
                "284",
                "Sol Ring",
                "01. New cards",
                2.0,
                3.0,
                None,
                1,
                1,
                0,
                None,
                None,
                None,
                "https://example.test/sol-ring.jpg",
                None,
            ),
        )
        self.conn.execute(
            """
            INSERT INTO sets (set_code, name, released_at, scryfall_uri, updated_at)
            VALUES ('LTC', 'LOTR Commander', '2023-06-01', 'https://example.test/ltc', '2026-01-01')
            """
        )
        ensure_app_tables(self.conn)
        seed_storage_locations(self.conn)
        self.conn.commit()

        self.conn.execute(
            """
            INSERT INTO decks (name, slug, purchase_price, created_at, updated_at)
            VALUES ('Sample Deck', 'sample', 30.0, '2026-01-01', '2026-01-01')
            """
        )
        self.conn.execute(
            """
            INSERT INTO deck_cards (
                deck_id, card_name, set_code, collector_number, finish,
                qty, owned_qty, section, sort_order, in_catalog
            ) VALUES (1, 'Sol Ring', 'LTC', '284', 0, 1, 1, 'commander', 0, 1)
            """
        )
        seed_storage_locations(self.conn)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        self.temp_dir.cleanup()

    def test_browse_index_returns_pages_for_each_deck(self):
        payload = decks_service.load_deck_browse_index(self.conn)
        self.assertEqual(len(payload["decks"]), 1)
        deck_id = str(payload["decks"][0]["id"])
        self.assertIn(deck_id, payload["pages"])
        page = payload["pages"][deck_id]
        self.assertEqual(page["deckSize"], 1)
        self.assertEqual(len(page["cards"]), 1)
        self.assertEqual(page["cards"][0]["imageUri"], "https://example.test/sol-ring.jpg")

    def test_add_card_to_deck_creates_and_increments(self):
        deck_row = self.conn.execute("SELECT deck_id FROM decks LIMIT 1").fetchone()
        deck_id = str(deck_row[0])

        created = decks_service.add_card_to_deck(
            self.conn,
            deck_id=deck_id,
            set_code="LTC",
            collector_number="284",
            finish=0,
            section="main",
        )
        self.assertTrue(created["created"])
        self.assertEqual(created["qty"], 1)
        self.assertEqual(created["section"], "main")

        updated = decks_service.add_card_to_deck(
            self.conn,
            deck_id=deck_id,
            set_code="LTC",
            collector_number="284",
            finish=0,
            section="main",
            qty=2,
        )
        self.assertFalse(updated["created"])
        self.assertEqual(updated["qty"], 3)

        rows = self.conn.execute(
            """
            SELECT qty, section FROM deck_cards
            WHERE deck_id = ? AND set_code = 'LTC' AND collector_number = '284' AND finish = 0
            """,
            (deck_row[0],),
        ).fetchall()
        self.assertEqual(len(rows), 2)
        sections = {row[1]: row[0] for row in rows}
        self.assertEqual(sections["commander"], 1)
        self.assertEqual(sections["main"], 3)

    def test_remove_card_from_deck_moves_owned_copies_to_default_storage(self):
        deck_row = self.conn.execute("SELECT deck_id, slug FROM decks LIMIT 1").fetchone()
        deck_id = str(deck_row[0])
        deck_slug = deck_row[1]

        self.conn.execute(
            """
            INSERT INTO purchases (set_code, collector_number, purchase_value, finish)
            VALUES ('LTC', '284', 1.0, 0)
            """
        )
        self.conn.execute(
            """
            UPDATE deck_cards
            SET qty = 1, owned_qty = 1, section = 'main'
            WHERE deck_id = ? AND set_code = 'LTC' AND collector_number = '284'
            """,
            (deck_row[0],),
        )
        self.conn.execute(
            """
            INSERT INTO card_instances (
                set_code, collector_number, finish, location_slug, purchase_value
            ) VALUES ('LTC', '284', 0, ?, 1.0)
            """,
            (f"deck:{deck_slug.lower()}",),
        )
        self.conn.commit()

        result = decks_service.remove_card_from_deck(
            self.conn,
            deck_id=deck_id,
            set_code="LTC",
            collector_number="284",
            finish=0,
            section="main",
        )
        self.assertTrue(result["removed"])
        self.assertEqual(result["movedToStorage"], 1)
        self.assertEqual(result["storageLocation"], "storage:general")

        deck_cards = self.conn.execute(
            "SELECT COUNT(*) FROM deck_cards WHERE deck_id = ?",
            (deck_row[0],),
        ).fetchone()[0]
        self.assertEqual(deck_cards, 0)

        location = self.conn.execute(
            """
            SELECT location_slug FROM card_instances
            WHERE set_code = 'LTC' AND collector_number = '284' AND finish = 0
            """
        ).fetchone()[0]
        self.assertEqual(location, "storage:general")

    def test_remove_card_without_owned_copies_leaves_storage_unchanged(self):
        decks_service.add_card_to_deck(
            self.conn,
            deck_id=str(self.conn.execute("SELECT deck_id FROM decks LIMIT 1").fetchone()[0]),
            set_code="LTC",
            collector_number="284",
            finish=0,
            section="sideboard",
        )
        deck_row = self.conn.execute("SELECT deck_id FROM decks LIMIT 1").fetchone()
        deck_id = str(deck_row[0])

        before_instances = self.conn.execute("SELECT COUNT(*) FROM card_instances").fetchone()[0]

        result = decks_service.remove_card_from_deck(
            self.conn,
            deck_id=deck_id,
            set_code="LTC",
            collector_number="284",
            finish=0,
            section="sideboard",
        )
        self.assertTrue(result["removed"])
        self.assertEqual(result["movedToStorage"], 0)

        after_instances = self.conn.execute("SELECT COUNT(*) FROM card_instances").fetchone()[0]
        self.assertEqual(before_instances, after_instances)

    def test_adjust_deck_card_qty_increments_and_decrements(self):
        deck_row = self.conn.execute("SELECT deck_id FROM decks LIMIT 1").fetchone()
        deck_id = str(deck_row[0])

        increased = decks_service.adjust_deck_card_qty(
            self.conn,
            deck_id=deck_id,
            set_code="LTC",
            collector_number="284",
            finish=0,
            section="commander",
            delta=1,
        )
        self.assertEqual(increased["qty"], 2)

        decreased = decks_service.adjust_deck_card_qty(
            self.conn,
            deck_id=deck_id,
            set_code="LTC",
            collector_number="284",
            finish=0,
            section="commander",
            delta=-1,
        )
        self.assertEqual(decreased["qty"], 1)
        self.assertFalse(decreased["removed"])

    def test_rename_deck_updates_name_and_storage_label(self):
        deck_row = self.conn.execute("SELECT deck_id, slug FROM decks LIMIT 1").fetchone()
        deck_id = str(deck_row[0])
        slug = str(deck_row[1]).lower()

        result = decks_service.rename_deck(self.conn, deck_id=deck_id, name="Renamed Deck")
        self.assertEqual(result["deck"]["name"], "Renamed Deck")

        name = self.conn.execute(
            "SELECT name FROM decks WHERE deck_id = ?",
            (deck_row[0],),
        ).fetchone()[0]
        self.assertEqual(name, "Renamed Deck")

        label = self.conn.execute(
            "SELECT label FROM storage_locations WHERE location_slug = ?",
            (f"deck:{slug}",),
        ).fetchone()[0]
        self.assertEqual(label, "Renamed Deck")

    def test_rename_deck_rejects_duplicate_name(self):
        self.conn.execute(
            """
            INSERT INTO decks (name, slug, purchase_price, created_at, updated_at)
            VALUES ('Other Deck', 'other', 20.0, '2026-01-01', '2026-01-01')
            """
        )
        self.conn.commit()

        deck_row = self.conn.execute(
            "SELECT deck_id FROM decks WHERE name = 'Sample Deck'"
        ).fetchone()
        with self.assertRaises(decks_service.DeckError) as ctx:
            decks_service.rename_deck(
                self.conn,
                deck_id=str(deck_row[0]),
                name="Other Deck",
            )
        self.assertEqual(ctx.exception.status_code, 400)

    def test_create_deck_with_commanders(self):
        result = decks_service.create_deck(
            self.conn,
            deck_format="commander",
            name="Commander Test",
            commanders=[
                {
                    "set_code": "LTC",
                    "collector_number": "284",
                    "finish": 0,
                }
            ],
        )
        self.assertEqual(result["deck"]["name"], "Commander Test")
        deck_id = result["deck"]["id"]

        rows = self.conn.execute(
            """
            SELECT section, card_name, qty FROM deck_cards
            WHERE deck_id = ?
            """,
            (deck_id,),
        ).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], "commander")
        self.assertEqual(rows[0][1], "Sol Ring")
        self.assertEqual(rows[0][2], 1)

        location = self.conn.execute(
            "SELECT label FROM storage_locations WHERE location_slug = ?",
            (f"deck:{result['deck']['slug'].lower()}",),
        ).fetchone()
        self.assertEqual(location[0], "Commander Test")

    def test_create_deck_defaults_name_to_first_commander(self):
        result = decks_service.create_deck(
            self.conn,
            deck_format="commander",
            name=None,
            commanders=[
                {
                    "set_code": "LTC",
                    "collector_number": "284",
                    "finish": 0,
                }
            ],
        )
        self.assertEqual(result["deck"]["name"], "Sol Ring")

    def test_create_deck_rejects_duplicate_name(self):
        decks_service.create_deck(
            self.conn,
            deck_format="commander",
            name="Taken Name",
            commanders=[
                {
                    "set_code": "LTC",
                    "collector_number": "284",
                    "finish": 0,
                }
            ],
        )
        with self.assertRaises(decks_service.DeckError) as ctx:
            decks_service.create_deck(
                self.conn,
                deck_format="commander",
                name="Taken Name",
                commanders=[
                    {
                        "set_code": "LTC",
                        "collector_number": "284",
                        "finish": 0,
                    }
                ],
            )
        self.assertEqual(ctx.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
