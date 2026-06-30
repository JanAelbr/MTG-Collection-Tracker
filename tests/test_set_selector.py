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

from report.set_selector_data import (  # noqa: E402
    build_set_selector_entries,
    format_set_selector_label,
)
from util.set_catalog import SETS_TABLE_SQL  # noqa: E402


class SetSelectorTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.conn = sqlite3.connect(Path(self.temp_dir.name) / "test.db")
        self.conn.executescript(SETS_TABLE_SQL)
        self.conn.executemany(
            """
            INSERT INTO sets (set_code, name, released_at, scryfall_uri, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                ("LTR", "The Lord of the Rings: Tales of Middle-earth", "2023-06-09", None, "2026-06-15"),
                ("LTC", "Tales of Middle-earth Commander", "2023-06-23", None, "2026-06-15"),
                ("PIP", "Fallout", "2024-03-08", None, "2026-06-15"),
                ("ECC", "Lorwyn Eclipsed Commander", "2026-01-23", None, "2026-06-15"),
                ("LEA", "Limited Edition Alpha", "1993-08-05", None, "2026-06-15"),
            ],
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
        self.conn.executemany(
            "INSERT INTO purchases (set_code, collector_number, purchase_value, finish) VALUES (?, ?, ?, ?)",
            [
                ("LTR", "1", 1.0, 0),
                ("LTR", "2", 1.0, 0),
                ("LTR", "3", 1.0, 1),
                ("LTC", "10", 2.0, 0),
            ],
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        self.temp_dir.cleanup()

    def test_format_set_selector_label_includes_owned_count(self):
        self.assertEqual(
            format_set_selector_label("LTR", "The Lord of the Rings: Tales of Middle-earth", 3),
            "The Lord of the Rings: Tales of Middle-earth (LTR) · 3",
        )

    @patch("report.set_selector_data.list_deck_sync_set_codes", return_value=["PIP", "ECC", "LTR"])
    def test_build_set_selector_entries_includes_owned_and_deck_sets(self, _mock_deck_sets):
        entries = build_set_selector_entries(self.conn, include_all=True)
        labels = [entry.label for entry in entries]
        values = [entry.value for entry in entries]

        self.assertEqual(values[0], "All")
        self.assertEqual(values[1], "LTR")
        self.assertEqual(values[2], "LTC")
        self.assertTrue(any(entry.separator for entry in entries))
        separator_index = next(i for i, entry in enumerate(entries) if entry.separator)
        self.assertEqual(set(values[separator_index + 1:]), {"PIP", "ECC"})
        self.assertIn("· 3", labels[1])
        self.assertIn("· 1", labels[2])
        self.assertIn("Fallout (PIP)", labels)


if __name__ == "__main__":
    unittest.main()
