import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import runpy

runpy.run_path(str(Path(__file__).resolve().with_name("_paths.py")))

from api.services import decks_service  # noqa: E402
from util.app_tables import ensure_app_tables  # noqa: E402
from util.deck_tables import ensure_deck_tables  # noqa: E402
from util.storage_tables import ensure_storage_tables, seed_storage_locations  # noqa: E402


class DeckUnpricedMetadataRefreshTests(unittest.TestCase):
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
                color_identity TEXT,
                cmc REAL,
                mana_cost TEXT,
                is_basic_land INTEGER,
                image_uri TEXT,
                cardmarket_url TEXT,
                cardmarket_url_foil TEXT
            );
            CREATE TABLE sets (
                set_code TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                released_at TEXT,
                scryfall_uri TEXT,
                updated_at TEXT NOT NULL
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
        self.conn.execute(
            """
            INSERT INTO cards (
                id, set_code, collector_number, name, art_style,
                market_value, market_value_foil, market_value_etched,
                has_nonfoil, has_foil, has_etched,
                colors, type_line, card_type, color_identity, cmc, mana_cost,
                is_basic_land, image_uri, cardmarket_url, cardmarket_url_foil
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "LTC-284",
                "LTC",
                "284",
                "Sol Ring",
                None,
                None,
                None,
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
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        self.temp_dir.cleanup()

    @patch("util.scryfall_catalog_sync.import_set_catalog_from_scryfall", return_value=120)
    def test_refresh_deck_unpriced_metadata_syncs_affected_sets(self, mock_import):
        result = decks_service.refresh_deck_unpriced_metadata(self.conn, deck_id="1")
        self.assertEqual(result["setCodes"], ["LTC"])
        self.assertEqual(result["synced"], [{"setCode": "LTC", "catalogCount": 120}])
        self.assertEqual(result["errors"], [])
        mock_import.assert_called_once_with(self.conn, "LTC")

    def test_deck_stats_price_joined_catalog_when_in_catalog_flag_stale(self):
        self.conn.execute("UPDATE deck_cards SET in_catalog = 0")
        self.conn.execute(
            "UPDATE cards SET market_value = 2.5 WHERE id = 'LTC-284'"
        )
        self.conn.commit()

        stats = decks_service.load_deck_stats(self.conn, deck_id="1")

        self.assertEqual(stats["stats"]["unknownCount"], 0)
        self.assertEqual(stats["stats"]["current"], 2.5)

    @patch("util.scryfall_catalog_sync.import_set_catalog_from_scryfall", return_value=120)
    def test_refresh_updates_stale_in_catalog_flags(self, mock_import):
        self.conn.execute("UPDATE deck_cards SET in_catalog = 0")
        self.conn.commit()

        decks_service.refresh_deck_unpriced_metadata(self.conn, deck_id="1")

        row = self.conn.execute(
            "SELECT in_catalog FROM deck_cards WHERE deck_id = 1"
        ).fetchone()
        self.assertEqual(row[0], 1)
        mock_import.assert_called_once_with(self.conn, "LTC")


if __name__ == "__main__":
    unittest.main()
