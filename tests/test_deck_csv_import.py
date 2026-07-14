import sqlite3
import tempfile
import unittest
from pathlib import Path

import runpy

runpy.run_path(str(Path(__file__).resolve().with_name("_paths.py")))

from api.services import decks_service  # noqa: E402
from util.app_tables import ensure_app_tables  # noqa: E402
from util.deck_csv_import import build_csv_import_plan, parse_deck_csv  # noqa: E402
from util.deck_tables import ensure_deck_tables  # noqa: E402
from util.storage_tables import ensure_storage_tables, seed_storage_locations  # noqa: E402


class DeckCsvImportTests(unittest.TestCase):
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
            """
        )
        self.conn.execute(
            """
            INSERT INTO cards (
                id, set_code, collector_number, name, art_style,
                market_value, market_value_foil, market_value_etched,
                has_nonfoil, has_foil, has_etched,
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
            INSERT INTO decks (name, slug, purchase_price, created_at, updated_at)
            VALUES ('Sample Deck', 'sample', 30.0, '2026-01-01', '2026-01-01')
            """
        )
        self.conn.execute(
            """
            INSERT INTO deck_cards (
                deck_id, card_name, set_code, collector_number, finish,
                qty, owned_qty, section, sort_order, in_catalog
            ) VALUES (1, 'Sol Ring', 'LTC', '284', 0, 2, 0, 'main', 0, 1)
            """
        )
        ensure_app_tables(self.conn)
        seed_storage_locations(self.conn)
        self.conn.commit()
        self.deck_id = 1

    def tearDown(self):
        self.conn.close()
        self.temp_dir.cleanup()

    def test_parse_deck_csv_supports_comments_and_negative_lines(self):
        entries, errors = parse_deck_csv(
            """
            # comment
            LTC;284;0;1
            -LTC;284;0
            """
        )
        self.assertEqual(errors, [])
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["qty"], 1)
        self.assertEqual(entries[1]["qty"], -1)

    def test_parse_deck_csv_allows_missing_or_empty_finish(self):
        entries, errors = parse_deck_csv(
            """
            LTC;284
            LTC;284;
            LTC;284;;3
            LTC;284;4
            """
        )
        self.assertEqual(errors, [])
        self.assertEqual(len(entries), 4)
        self.assertEqual(entries[0]["finish_raw"], "")
        self.assertEqual(entries[1]["finish_raw"], "")
        self.assertEqual(entries[2]["finish_raw"], "")
        self.assertEqual(entries[2]["qty"], 3)
        self.assertEqual(entries[3]["finish_raw"], "")
        self.assertEqual(entries[3]["qty"], 4)

    def test_preview_null_finish_defaults_to_nonfoil(self):
        plan = build_csv_import_plan(
            self.conn,
            deck_id=self.deck_id,
            csv="LTC;284",
            mode="set",
            section="main",
        )
        self.assertTrue(plan["valid"])
        self.assertEqual(plan["changes"][0]["finish"], 0)

    def test_preview_merge_adds_and_removes_copies(self):
        plan = build_csv_import_plan(
            self.conn,
            deck_id=self.deck_id,
            csv="LTC;284;0;2\n-LTC;284;0",
            mode="merge",
            section="main",
        )
        self.assertTrue(plan["valid"])
        self.assertEqual(len(plan["changes"]), 1)
        self.assertEqual(plan["changes"][0]["action"], "update")
        self.assertEqual(plan["changes"][0]["currentQty"], 2)
        self.assertEqual(plan["changes"][0]["newQty"], 3)

    def test_preview_replace_removes_unlisted_cards(self):
        plan = build_csv_import_plan(
            self.conn,
            deck_id=self.deck_id,
            csv="",
            mode="replace",
            section="main",
        )
        self.assertTrue(plan["valid"])
        self.assertEqual(len(plan["changes"]), 1)
        self.assertEqual(plan["changes"][0]["action"], "remove")

    def test_apply_csv_import_updates_deck(self):
        preview = decks_service.preview_deck_csv_import(
            self.conn,
            deck_id=str(self.deck_id),
            csv="LTC;284;0;4",
            mode="set",
            section="main",
        )
        self.assertTrue(preview["canApply"])
        result = decks_service.apply_deck_csv_import(
            self.conn,
            deck_id=str(self.deck_id),
            csv="LTC;284;0;4",
            mode="set",
            section="main",
        )
        self.assertEqual(result["applied"]["update"], 1)
        row = self.conn.execute(
            "SELECT qty FROM deck_cards WHERE deck_id = 1 AND section = 'main'"
        ).fetchone()
        self.assertEqual(row[0], 4)


if __name__ == "__main__":
    unittest.main()
