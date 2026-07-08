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

from report.report_data import format_set_option_label  # noqa: E402
from util.set_catalog import (  # noqa: E402
    SETS_TABLE_SQL,
    load_catalog_set_codes,
    load_owned_set_codes,
    load_set_display_names,
    load_set_icon_uris,
    load_sets_catalog,
    prune_unowned_sets,
    sync_set_metadata,
    upsert_set_from_card,
    upsert_set_row,
)


class SetCatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.conn = sqlite3.connect(Path(self.temp_dir.name) / "test.db")
        self.conn.executescript(SETS_TABLE_SQL)
        self.cursor = self.conn.cursor()

    def tearDown(self):
        self.conn.close()
        self.temp_dir.cleanup()

    def test_upsert_set_row_stores_name(self):
        upsert_set_row(
            self.cursor,
            "LTR",
            "The Lord of the Rings: Tales of Middle-earth",
            "2023-06-09",
            "https://scryfall.com/sets/ltr",
            "2026-06-15",
        )
        self.conn.commit()
        names = load_set_display_names(self.conn)
        self.assertEqual(
            names["LTR"],
            "The Lord of the Rings: Tales of Middle-earth",
        )

    def test_upsert_set_from_card(self):
        upsert_set_from_card(
            self.cursor,
            {
                "set": "hob",
                "set_name": "The Hobbit",
                "set_uri": "https://api.scryfall.com/sets/hob",
            },
            "2026-06-15",
        )
        self.conn.commit()
        names = load_set_display_names(self.conn)
        self.assertEqual(names["HOB"], "The Hobbit")

    def test_load_sets_catalog(self):
        upsert_set_row(
            self.cursor,
            "LTR",
            "The Lord of the Rings: Tales of Middle-earth",
            "2023-06-09",
            "https://scryfall.com/sets/ltr",
            "2026-06-15",
        )
        self.conn.commit()
        catalog = load_sets_catalog(self.conn)
        self.assertEqual(catalog["LTR"]["name"], "The Lord of the Rings: Tales of Middle-earth")
        self.assertEqual(catalog["LTR"]["released_at"], "2023-06-09")
        self.assertEqual(catalog["LTR"]["scryfall_uri"], "https://scryfall.com/sets/ltr")

    def test_sync_set_metadata_stores_icon_svg_uri(self):
        payload = {
            "code": "hob",
            "name": "The Hobbit",
            "released_at": "2026-06-13",
            "scryfall_uri": "https://scryfall.com/sets/hob",
            "icon_svg_uri": "https://svgs.scryfall.io/sets/hob.svg?1782705600",
        }
        with patch("util.set_catalog.fetch_scryfall_set", return_value=payload):
            synced = sync_set_metadata(
                self.cursor,
                "HOB",
                {"User-Agent": "test"},
                "2026-06-15",
            )
        self.conn.commit()
        self.assertTrue(synced)
        icon_uris = load_set_icon_uris(self.conn)
        self.assertEqual(
            icon_uris["HOB"],
            "https://svgs.scryfall.io/sets/hob.svg?1782705600",
        )

    def test_format_set_option_label_uses_catalog(self):
        upsert_set_row(
            self.cursor,
            "LTC",
            "Tales of Middle-earth Commander",
            None,
            None,
            "2026-06-15",
        )
        self.conn.commit()
        names = load_set_display_names(self.conn)
        self.assertEqual(
            format_set_option_label("LTC", names),
            "Tales of Middle-earth Commander (LTC)",
        )
        self.assertEqual(format_set_option_label("All", names), "All")
        self.assertEqual(format_set_option_label("XYZ", names), "XYZ")

    def test_prune_unowned_sets_keeps_only_purchased_sets(self):
        upsert_set_row(
            self.cursor,
            "LTR",
            "The Lord of the Rings: Tales of Middle-earth",
            "2023-06-09",
            None,
            "2026-06-15",
        )
        upsert_set_row(
            self.cursor,
            "LEA",
            "Limited Edition Alpha",
            "1993-08-05",
            None,
            "2026-06-15",
        )
        self.conn.executescript(
            """
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
            "INSERT INTO purchases (set_code, collector_number, purchase_value, finish) VALUES (?, ?, ?, ?)",
            ("LTR", "1", 1.0, 0),
        )
        self.conn.commit()

        removed = prune_unowned_sets(self.conn)
        self.conn.commit()
        names = load_set_display_names(self.conn)

        self.assertEqual(removed, 1)
        self.assertIn("LTR", names)
        self.assertNotIn("LEA", names)
        self.assertEqual(load_owned_set_codes(self.conn), ["LTR"])

    @patch("util.deck_tables.list_deck_sync_set_codes", return_value=["PIP"])
    def test_prune_unowned_sets_keeps_deck_sets(self, _mock_deck_sets):
        upsert_set_row(
            self.cursor,
            "LTR",
            "The Lord of the Rings: Tales of Middle-earth",
            "2023-06-09",
            None,
            "2026-06-15",
        )
        upsert_set_row(
            self.cursor,
            "PIP",
            "Fallout",
            "2024-03-08",
            None,
            "2026-06-15",
        )
        upsert_set_row(
            self.cursor,
            "LEA",
            "Limited Edition Alpha",
            "1993-08-05",
            None,
            "2026-06-15",
        )
        self.conn.executescript(
            """
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
        self.conn.commit()

        removed = prune_unowned_sets(self.conn)
        self.conn.commit()
        names = load_set_display_names(self.conn)

        self.assertEqual(removed, 2)
        self.assertIn("PIP", names)
        self.assertNotIn("LEA", names)
        self.assertNotIn("LTR", names)
        self.assertEqual(load_catalog_set_codes(self.conn), {"PIP"})


if __name__ == "__main__":
    unittest.main()
