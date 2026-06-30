import sqlite3
import tempfile
import unittest
from pathlib import Path

import runpy
import sys
from pathlib import Path

runpy.run_path(str(Path(__file__).resolve().with_name("_paths.py")))

from api.services import decks_service  # noqa: E402
from lib.deck_csv import DeckEntry  # noqa: E402
from lib.deck_loader import import_deck_file  # noqa: E402
from util.app_tables import ensure_app_tables  # noqa: E402
from util.deck_tables import ensure_deck_tables  # noqa: E402
from util.storage_tables import ensure_storage_tables  # noqa: E402


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
        self.conn.commit()

        deck_file = Path(self.temp_dir.name) / "sample.csv"
        deck_file.write_text(
            "set_code;collector_number;foil;qty;owned;section\n"
            "LTC;284;0;1;1;commander\n",
            encoding="utf-8",
        )
        import_deck_file(
            self.conn.cursor(),
            DeckEntry(name="Sample Deck", purchase_price=30.0, path=deck_file, slug="sample"),
        )
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


if __name__ == "__main__":
    unittest.main()
