import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from report.report_data import load_catalog_count_by_set  # noqa: E402
from util.alchemy_cards import (  # noqa: E402
    is_alchemy_art_style,
    is_alchemy_collector_number,
    is_alchemy_scryfall_card,
)
from util.set_completion import completion_collector_key  # noqa: E402


class AlchemyCardTests(unittest.TestCase):
    def test_collector_number_prefix(self):
        self.assertTrue(is_alchemy_collector_number("A-103"))
        self.assertTrue(is_alchemy_collector_number("a-6"))
        self.assertFalse(is_alchemy_collector_number("103"))
        self.assertFalse(is_alchemy_collector_number(""))

    def test_scryfall_card_detection(self):
        self.assertTrue(
            is_alchemy_scryfall_card({"collector_number": "A-6", "promo_types": []})
        )
        self.assertTrue(
            is_alchemy_scryfall_card(
                {"collector_number": "42", "promo_types": ["alchemy"]}
            )
        )
        self.assertTrue(
            is_alchemy_scryfall_card(
                {
                    "collector_number": "42",
                    "digital": True,
                    "games": ["arena"],
                }
            )
        )
        self.assertFalse(
            is_alchemy_scryfall_card(
                {"collector_number": "42", "digital": False, "games": ["paper"]}
            )
        )

    def test_completion_key_excludes_alchemy(self):
        self.assertIsNone(completion_collector_key("A-103"))

    def test_art_style_name_detection(self):
        self.assertTrue(is_alchemy_art_style("12. Alchemy promos"))
        self.assertFalse(is_alchemy_art_style("01. Main set"))

    def test_art_style_options_hide_alchemy_sections(self):
        import sqlite3

        from report.report_data import build_art_style_options_for_set

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
                ("TDM", "1", "Paper", "01. Main set"),
                ("TDM", "A-103", "Alchemy", "12. Alchemy promos"),
            ],
        )
        conn.commit()

        options = build_art_style_options_for_set(conn, "TDM")
        styles = {option["artStyle"] for option in options}

        self.assertIn("01. Main set", styles)
        self.assertNotIn("12. Alchemy promos", styles)
        self.assertEqual(options[0]["catalogCount"], 1)

    def test_catalog_count_excludes_alchemy_rows(self):
        import sqlite3

        conn = sqlite3.connect(":memory:")
        conn.execute(
            "CREATE TABLE cards (set_code TEXT, collector_number TEXT, name TEXT, art_style TEXT)"
        )
        conn.executemany(
            "INSERT INTO cards (set_code, collector_number, name, art_style) VALUES (?, ?, ?, ?)",
            [
                ("TDM", "1", "Paper card", "Main"),
                ("TDM", "A-103", "Alchemy card", "Alchemy promos"),
            ],
        )
        conn.commit()

        counts = load_catalog_count_by_set(conn)

        self.assertEqual(counts["TDM"], 1)


if __name__ == "__main__":
    unittest.main()
