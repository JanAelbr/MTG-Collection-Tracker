import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from report.report_data import (  # noqa: E402
    build_art_style_options_for_set,
    load_catalog_count_by_set,
    load_owned_count_by_set,
)
from util.set_completion import (  # noqa: E402
    completion_collector_key,
    is_serialized_collector_number,
)


class SetCompletionTests(unittest.TestCase):
    def test_serialized_suffix_is_detected(self):
        self.assertTrue(is_serialized_collector_number("731z"))
        self.assertFalse(is_serialized_collector_number("731"))

    def test_completion_key_uses_absolute_number(self):
        self.assertEqual(completion_collector_key("14"), "14")
        self.assertEqual(completion_collector_key("014"), "14")
        self.assertEqual(completion_collector_key("WTH-53"), "53")
        self.assertIsNone(completion_collector_key("731z"))

    def test_catalog_count_excludes_serialized_and_collapses_numeric_variants(self):
        import sqlite3

        conn = sqlite3.connect(":memory:")
        conn.execute(
            "CREATE TABLE cards (set_code TEXT, collector_number TEXT, name TEXT, art_style TEXT)"
        )
        conn.executemany(
            "INSERT INTO cards (set_code, collector_number, name, art_style) VALUES (?, ?, ?, ?)",
            [
                ("LTR", "14", "A", "Main"),
                ("LTR", "014", "A alt", "Main"),
                ("LTR", "731", "B", "Main"),
                ("LTR", "731z", "Serialized", "Serialized"),
            ],
        )
        conn.commit()

        counts = load_catalog_count_by_set(conn)

        self.assertEqual(counts["LTR"], 2)

    def test_owned_count_ignores_serialized_copies(self):
        import sqlite3

        conn = sqlite3.connect(":memory:")
        conn.executescript(
            """
            CREATE TABLE cards (
                set_code TEXT,
                collector_number TEXT,
                name TEXT,
                art_style TEXT
            );
            CREATE TABLE purchases (
                set_code TEXT NOT NULL,
                collector_number TEXT NOT NULL,
                purchase_value REAL NOT NULL DEFAULT 0,
                finish INTEGER NOT NULL
            );
            """
        )
        conn.executemany(
            "INSERT INTO purchases (set_code, collector_number, purchase_value, finish) VALUES (?, ?, 0, 0)",
            [
                ("LTR", "731"),
                ("LTR", "731z"),
            ],
        )
        conn.commit()

        counts = load_owned_count_by_set(conn)

        self.assertEqual(counts["LTR"], 1)

    def test_art_style_counts_exclude_serialized(self):
        import sqlite3

        conn = sqlite3.connect(":memory:")
        conn.executescript(
            """
            CREATE TABLE cards (
                set_code TEXT,
                collector_number TEXT,
                name TEXT,
                art_style TEXT
            );
            CREATE TABLE purchases (
                set_code TEXT NOT NULL,
                collector_number TEXT NOT NULL,
                purchase_value REAL NOT NULL DEFAULT 0,
                finish INTEGER NOT NULL
            );
            """
        )
        conn.executemany(
            "INSERT INTO cards (set_code, collector_number, name, art_style) VALUES (?, ?, ?, ?)",
            [
                ("LTR", "1", "A", "Main"),
                ("LTR", "731z", "Serialized", "Serialized"),
            ],
        )
        conn.executemany(
            "INSERT INTO purchases (set_code, collector_number, purchase_value, finish) VALUES (?, ?, 0, 0)",
            [("LTR", "1")],
        )
        conn.commit()

        options = build_art_style_options_for_set(conn, "LTR")
        by_style = {option["artStyle"]: option for option in options}

        self.assertEqual(by_style["Main"]["catalogCount"], 1)
        self.assertEqual(by_style["Main"]["ownedCount"], 1)
        self.assertNotIn("Serialized", by_style)


if __name__ == "__main__":
    unittest.main()
