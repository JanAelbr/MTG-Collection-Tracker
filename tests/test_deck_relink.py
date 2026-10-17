import sqlite3
import unittest

import runpy
from pathlib import Path

runpy.run_path(str(Path(__file__).resolve().with_name("_paths.py")))

from util.deck_helpers import relink_unresolved_deck_cards  # noqa: E402


class DeckRelinkTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(
            """
            CREATE TABLE cards (
                set_code TEXT,
                collector_number TEXT,
                name TEXT,
                has_nonfoil INTEGER,
                has_foil INTEGER,
                has_etched INTEGER
            );
            CREATE TABLE decks (
                deck_id INTEGER PRIMARY KEY,
                name TEXT
            );
            CREATE TABLE deck_cards (
                deck_card_id INTEGER PRIMARY KEY AUTOINCREMENT,
                deck_id INTEGER NOT NULL,
                card_name TEXT NOT NULL,
                set_code TEXT,
                collector_number TEXT,
                finish INTEGER NOT NULL DEFAULT 0,
                qty INTEGER NOT NULL DEFAULT 1,
                owned_qty INTEGER NOT NULL DEFAULT 0,
                section TEXT NOT NULL DEFAULT 'main',
                sort_order INTEGER NOT NULL DEFAULT 0,
                in_catalog INTEGER NOT NULL DEFAULT 0,
                UNIQUE (deck_id, set_code, collector_number, finish, section)
            );
            """
        )
        self.conn.execute("INSERT INTO decks (deck_id, name) VALUES (1, 'Sample')")

    def tearDown(self):
        self.conn.close()

    def _add_card(self, set_code, number, name):
        self.conn.execute(
            """
            INSERT INTO cards (set_code, collector_number, name, has_nonfoil, has_foil, has_etched)
            VALUES (?, ?, ?, 1, 1, 0)
            """,
            (set_code, number, name),
        )

    def _add_deck_card(self, name, set_code, number, *, qty=1, in_catalog=0, section="main"):
        self.conn.execute(
            """
            INSERT INTO deck_cards (
                deck_id, card_name, set_code, collector_number, finish, qty,
                in_catalog, section
            ) VALUES (1, ?, ?, ?, 0, ?, ?, ?)
            """,
            (name, set_code, number, qty, in_catalog, section),
        )

    def test_refresh_rewrites_placeholder_names_and_keeps_real_names(self):
        self._add_card("LTR", "1", "Sol Ring")
        self._add_deck_card("LTR #1", "LTR", "1")
        self._add_deck_card("My Sol Ring", "LTR", "1", section="sideboard")

        updated = relink_unresolved_deck_cards(self.conn, ["ltr"])

        rows = self.conn.execute(
            "SELECT card_name, in_catalog, section FROM deck_cards ORDER BY section"
        ).fetchall()
        self.assertEqual(updated, 2)
        self.assertEqual(rows[0]["card_name"], "Sol Ring")
        self.assertEqual(rows[0]["in_catalog"], 1)
        self.assertEqual(rows[1]["card_name"], "My Sol Ring")
        self.assertEqual(rows[1]["in_catalog"], 1)

    def test_refresh_retargets_missing_list_slot_to_source_set(self):
        self._add_card("BLB", "127", "Brambleguard Captain")
        self._add_card("PLST", "C17-37", "Fractured Identity")
        self._add_deck_card("PLST #BLB-127", "PLST", "BLB-127")
        self._add_deck_card("PLST #C17-37", "PLST", "C17-37")

        relink_unresolved_deck_cards(self.conn, ["BLB"])

        rows = {
            row["collector_number"]: row
            for row in self.conn.execute(
                "SELECT set_code, collector_number, card_name, in_catalog FROM deck_cards"
            )
        }
        self.assertEqual(rows["127"]["set_code"], "BLB")
        self.assertEqual(rows["127"]["card_name"], "Brambleguard Captain")
        self.assertEqual(rows["C17-37"]["set_code"], "PLST")
        self.assertEqual(rows["C17-37"]["card_name"], "Fractured Identity")
        self.assertEqual(rows["C17-37"]["in_catalog"], 1)

    def test_refresh_of_list_set_uses_source_printing_when_slot_is_missing(self):
        self._add_card("BLB", "127", "Brambleguard Captain")
        self._add_deck_card("PLST #BLB-127", "PLST", "BLB-127")
        self._add_deck_card("Brambleguard Captain", "BLB", "127", qty=1, in_catalog=1)

        relink_unresolved_deck_cards(self.conn, ["PLST"])

        rows = self.conn.execute(
            "SELECT set_code, collector_number, qty, card_name FROM deck_cards"
        ).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["set_code"], "BLB")
        self.assertEqual(rows[0]["collector_number"], "127")
        self.assertEqual(rows[0]["qty"], 2)
        self.assertEqual(rows[0]["card_name"], "Brambleguard Captain")

    def test_refresh_links_unique_named_card_in_the_new_set(self):
        self._add_card("LTC", "284", "Sol Ring")
        self._add_card("LTR", "1", "Sol Ring")
        self._add_deck_card("Sol Ring", "", "")

        updated = relink_unresolved_deck_cards(self.conn, ["LTC", "LTR"])

        self.assertEqual(updated, 0)
        row = self.conn.execute(
            "SELECT set_code, collector_number FROM deck_cards"
        ).fetchone()
        self.assertEqual(row["set_code"], "")

    def test_refresh_links_a_name_when_the_new_set_has_one_printing(self):
        self._add_card("LTC", "284", "Sol Ring")
        self._add_deck_card("Sol Ring", "", "")

        relink_unresolved_deck_cards(self.conn, ["LTC"])

        row = self.conn.execute(
            "SELECT set_code, collector_number, card_name, in_catalog FROM deck_cards"
        ).fetchone()
        self.assertEqual(row["set_code"], "LTC")
        self.assertEqual(row["collector_number"], "284")
        self.assertEqual(row["card_name"], "Sol Ring")
        self.assertEqual(row["in_catalog"], 1)


if __name__ == "__main__":
    unittest.main()
