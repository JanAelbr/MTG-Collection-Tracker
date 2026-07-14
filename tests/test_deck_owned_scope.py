import sqlite3
import tempfile
import unittest
from pathlib import Path

import runpy

runpy.run_path(str(Path(__file__).resolve().with_name("_paths.py")))

from report.deck_queries import enrich_deck_cards_df, load_deck_cards_df  # noqa: E402
from util.deck_tables import ensure_deck_tables  # noqa: E402


class DeckOwnedScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.conn = sqlite3.connect(self.db_path)
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
                color_identity TEXT,
                cmc REAL,
                mana_cost TEXT,
                is_basic_land INTEGER,
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
                market_value, market_value_foil, market_value_etched,
                has_nonfoil, has_foil, has_etched,
                colors, type_line, card_type, color_identity, cmc, mana_cost,
                is_basic_land, image_uri, cardmarket_url
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "LTC-284",
                "LTC",
                "284",
                "Sol Ring",
                None,
                2.0,
                3.0,
                None,
                1,
                1,
                0,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
            ),
        )
        self.conn.execute(
            """
            INSERT INTO decks (name, slug, purchase_price, created_at, updated_at)
            VALUES ('Sample Deck', 'sample', 0, '2026-01-01', '2026-01-01')
            """
        )
        self.conn.execute(
            """
            INSERT INTO deck_cards (
                deck_id, card_name, set_code, collector_number, finish,
                qty, owned_qty, section, sort_order, in_catalog
            ) VALUES (1, 'Sol Ring', 'LTC', '284', 0, 1, 0, 'main', 0, 1)
            """
        )
        self.conn.execute(
            """
            INSERT INTO purchases (set_code, collector_number, purchase_value, finish)
            VALUES ('LTC', '284', 1.0, 0)
            """
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        self.temp_dir.cleanup()

    def test_enrich_deck_cards_df_uses_deck_owned_qty_only(self):
        deck_df = load_deck_cards_df(self.conn)
        enriched = enrich_deck_cards_df(deck_df, self.conn)
        self.assertEqual(int(enriched.iloc[0]["owned_qty"]), 0)


if __name__ == "__main__":
    unittest.main()
