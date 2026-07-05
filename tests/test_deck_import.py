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

from lib.deck_csv import DeckEntry, list_deck_sync_set_codes  # noqa: E402
from lib.deck_loader import import_deck_file, resolve_deck_row  # noqa: E402
from report.deck_queries import enrich_deck_cards_df  # noqa: E402
from report.deck_stats_data import compute_deck_stats_page, load_deck_stats_client_payload  # noqa: E402
from util.deck_tables import ensure_deck_tables  # noqa: E402


class DeckImportTests(unittest.TestCase):
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
            CREATE TABLE card_instances (
                instance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                set_code TEXT NOT NULL,
                collector_number TEXT NOT NULL,
                finish INTEGER NOT NULL,
                location_slug TEXT NOT NULL DEFAULT 'storage:general'
            );
            """
        )
        self.conn.execute(
            """
            INSERT INTO cards (
                id, set_code, collector_number, name, art_style,
                market_value, market_value_foil, market_value_etched, has_nonfoil, has_foil, has_etched,
                image_uri, cardmarket_url
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("LTC-284", "LTC", "284", "Sol Ring", "01. New cards", 2.0, 3.0, None, 1, 1, 0, None, None),
        )
        self.conn.commit()
        self.cursor = self.conn.cursor()

        self.deck_file = Path(self.temp_dir.name) / "sample.csv"
        self.deck_file.write_text(
            "set_code;collector_number;foil;qty;owned;section\n"
            "LTC;284;0;1;1;main\n"
            "XXX;999;0;2;0;main\n",
            encoding="utf-8",
        )
        self.deck_entry = DeckEntry(
            name="Sample Deck",
            purchase_price=None,
            path=self.deck_file,
            slug="sample",
        )

    def tearDown(self):
        self.conn.close()
        self.temp_dir.cleanup()

    def test_import_deck_file_stores_owned_qty_from_csv(self):
        deck_id, _, _ = import_deck_file(self.cursor, self.deck_entry)
        self.conn.commit()
        rows = self.cursor.execute(
            """
            SELECT set_code, collector_number, qty, owned_qty
            FROM deck_cards
            WHERE deck_id = ?
            ORDER BY set_code
            """,
            (deck_id,),
        ).fetchall()
        self.assertEqual(rows, [("LTC", "284", 1, 1), ("XXX", "999", 2, 0)])

    def test_read_deck_card_rows_defaults_owned_to_one(self):
        deck_file = Path(self.temp_dir.name) / "legacy.csv"
        deck_file.write_text(
            "set_code;collector_number;foil;qty;section\n"
            "LTC;284;0;1;main\n",
            encoding="utf-8",
        )
        from lib.deck_csv import read_deck_card_rows  # noqa: PLC0415

        rows = read_deck_card_rows(deck_file)
        self.assertEqual(rows[0]["owned_qty"], 1)

    def test_import_deck_file_tracks_catalog_matches(self):
        deck_id, card_count, tracked_count = import_deck_file(self.cursor, self.deck_entry)
        self.conn.commit()
        self.assertEqual(card_count, 2)
        self.assertEqual(tracked_count, 1)
        row = self.cursor.execute(
            """
            SELECT set_code, collector_number, in_catalog
            FROM deck_cards
            WHERE deck_id = ? AND card_name = 'Sol Ring'
            """,
            (deck_id,),
        ).fetchone()
        self.assertEqual(row, ("LTC", "284", 1))

    def test_import_deck_file_preserves_print_when_not_in_catalog(self):
        deck_id, card_count, tracked_count = import_deck_file(self.cursor, self.deck_entry)
        self.conn.commit()
        self.assertEqual(card_count, 2)
        self.assertEqual(tracked_count, 1)
        row = self.cursor.execute(
            """
            SELECT set_code, collector_number, card_name, in_catalog
            FROM deck_cards
            WHERE deck_id = ? AND set_code = 'XXX'
            """,
            (deck_id,),
        ).fetchone()
        self.assertEqual(row, ("XXX", "999", "XXX #999", 0))

    def test_resolve_deck_row_keeps_explicit_print_without_catalog_match(self):
        resolved = resolve_deck_row(
            self.cursor,
            {
                "set_code": "PLST",
                "collector_number": "WTH-53",
                "foil": 0,
                "qty": 1,
                "section": "main",
                "sort_order": 0,
            },
        )
        self.assertEqual(resolved["set_code"], "PLST")
        self.assertEqual(resolved["collector_number"], "WTH-53")
        self.assertEqual(resolved["in_catalog"], 0)
        self.assertEqual(resolved["card_name"], "PLST #WTH-53")

    def test_list_deck_sync_set_codes_reads_explicit_prints(self):
        deck_file = Path(self.temp_dir.name) / "sync_sets.csv"
        deck_file.write_text(
            "set_code;collector_number;foil;qty;owned;section\n"
            "ECC;150;0;1;1;main\n"
            "EOC;45;0;1;1;main\n",
            encoding="utf-8",
        )
        deck_entry = DeckEntry(
            name="Sample",
            purchase_price=None,
            path=deck_file,
            slug="sync_sets",
        )
        with patch("lib.deck_csv.load_deck_entries", return_value=[deck_entry]):
            self.assertEqual(list_deck_sync_set_codes(), ["ECC", "EOC"])

    def test_enrich_deck_cards_uses_collection_owned_counts(self):
        import pandas as pd

        self.conn.executemany(
            """
            INSERT INTO card_instances (set_code, collector_number, finish, location_slug)
            VALUES (?, ?, ?, ?)
            """,
            [("LTC", "284", 0, "storage:general")] * 4,
        )
        self.conn.commit()

        deck_df = pd.DataFrame(
            [
                {
                    "deck_id": 1,
                    "deck_name": "Sample",
                    "deck_slug": "sample",
                    "deck_purchase_price": None,
                    "card_name": "Sol Ring",
                    "set_code": "LTC",
                    "collector_number": "284",
                    "finish": 0,
                    "qty": 4,
                    "owned_qty": 0,
                    "section": "main",
                    "in_catalog": 1,
                    "sort_order": 0,
                    "catalog_name": "Sol Ring",
                    "art_style": "Main",
                    "market_value": 2.0,
                    "market_value_foil": 3.0,
                    "market_value_etched": None,
                    "image_uri": None,
                    "cardmarket_url": None,
                    "colors": "[]",
                    "type_line": "Artifact",
                    "card_type": "artifact",
                    "purchase_value": None,
                }
            ]
        )

        enriched = enrich_deck_cards_df(deck_df, self.conn)
        self.assertEqual(int(enriched.iloc[0]["owned_qty"]), 4)


if __name__ == "__main__":
    unittest.main()
