import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from util.db_migrate import (  # noqa: E402
    backfill_basic_land_flags,
    ensure_card_columns,
    mark_complete_catalog_sets,
)
from util.price_sync import (  # noqa: E402
    count_cards_missing_power_metadata,
    set_catalog_is_complete,
    sync_set_catalog,
)
from util.set_catalog import ensure_sets_columns, ensure_sets_table  # noqa: E402


class CatalogCompletenessTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.conn = sqlite3.connect(Path(self.temp_dir.name) / "test.db")
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
                image_uri TEXT,
                cardmarket_url TEXT,
                cardmarket_url_foil TEXT,
                colors TEXT,
                type_line TEXT,
                card_type TEXT,
                color_identity TEXT,
                oracle_text TEXT,
                mana_cost TEXT,
                cmc REAL,
                legalities TEXT,
                is_basic_land INTEGER,
                scryfall_id TEXT
            );
            """
        )
        ensure_sets_table(self.conn)
        ensure_sets_columns(self.conn)
        ensure_card_columns(self.conn)
        self.cursor = self.conn.cursor()

    def tearDown(self):
        self.conn.close()
        self.temp_dir.cleanup()

    def test_lands_do_not_count_as_missing_power_metadata(self):
        self.cursor.executemany(
            """
            INSERT INTO cards (
                id, set_code, collector_number, name, type_line, card_type,
                mana_cost, cmc, is_basic_land
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("40K-312", "40K", "312", "Plains", "Basic Land — Plains", "land", None, 0, 1),
                ("40K-249", "40K", "249", "Sol Ring", "Artifact", "artifact", "{1}", 1, 0),
            ],
        )
        self.conn.commit()
        self.assertEqual(count_cards_missing_power_metadata(self.cursor, "40K"), 0)

    def test_mark_complete_catalog_sets_stamps_synced_sets(self):
        self.cursor.executemany(
            """
            INSERT INTO cards (
                id, set_code, collector_number, name, type_line, card_type,
                mana_cost, cmc, is_basic_land
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("40K-312", "40K", "312", "Plains", "Basic Land — Plains", "land", None, 0, 1),
                ("40K-249", "40K", "249", "Sol Ring", "Artifact", "artifact", "{1}", 1, 0),
            ],
        )
        self.conn.commit()
        backfill_basic_land_flags(self.conn)
        marked = mark_complete_catalog_sets(self.conn)
        self.conn.commit()
        self.assertEqual(marked, 1)
        self.assertTrue(set_catalog_is_complete(self.cursor, "40K"))

    def test_sync_set_catalog_skips_complete_local_catalog(self):
        self.cursor.executemany(
            """
            INSERT INTO cards (
                id, set_code, collector_number, name, type_line, card_type,
                mana_cost, cmc, is_basic_land
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("40K-249", "40K", "249", "Sol Ring", "Artifact", "artifact", "{1}", 1, 0),
            ],
        )
        self.cursor.execute(
            """
            INSERT INTO sets (set_code, name, released_at, scryfall_uri, icon_svg_uri, updated_at, catalog_synced_at)
            VALUES ('40K', '40K', NULL, NULL, NULL, '2026-07-12', '2026-07-12')
            """
        )
        self.conn.commit()

        with patch("util.price_sync.fetch_scryfall_page") as fetch_mock:
            count = sync_set_catalog(self.cursor, "40k", "2026-07-12", force_scryfall=False)

        self.assertEqual(count, 1)
        fetch_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
