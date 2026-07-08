import sqlite3
import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
COLLECTION_DIR = Path(__file__).resolve().parents[1] / "server-backend" / "collection"
for _path in (str(COLLECTION_DIR), str(SCRIPTS_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from lib.config import normalize_set_code  # noqa: E402
from util.db_migrate import consolidate_set_code_aliases  # noqa: E402


class SetCodeAliasTests(unittest.TestCase):
    def test_normalize_set_code_maps_plist_to_plst(self):
        self.assertEqual(normalize_set_code("plist"), "PLST")
        self.assertEqual(normalize_set_code("PLST"), "PLST")
        self.assertEqual(normalize_set_code("ltr"), "LTR")

    def test_consolidate_set_code_aliases_merges_rows(self):
        conn = sqlite3.connect(":memory:")
        conn.executescript(
            """
            CREATE TABLE purchases (
                purchase_id INTEGER PRIMARY KEY AUTOINCREMENT,
                set_code TEXT NOT NULL,
                collector_number TEXT NOT NULL,
                purchase_value REAL NOT NULL DEFAULT 0,
                finish INTEGER NOT NULL,
                UNIQUE (set_code, collector_number, finish)
            );
            CREATE TABLE cards (
                id TEXT PRIMARY KEY,
                set_code TEXT NOT NULL,
                collector_number TEXT NOT NULL,
                name TEXT NOT NULL
            );
            CREATE TABLE card_instances (
                instance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                set_code TEXT NOT NULL,
                collector_number TEXT NOT NULL,
                finish INTEGER NOT NULL,
                location_slug TEXT,
                purchase_value REAL
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
                in_catalog INTEGER NOT NULL DEFAULT 0
            );
            """
        )
        conn.execute(
            "INSERT INTO purchases (set_code, collector_number, purchase_value, finish) VALUES ('PLIST', '71', 0, 0)"
        )
        conn.execute(
            "INSERT INTO purchases (set_code, collector_number, purchase_value, finish) VALUES ('PLST', 'WTH-53', 0, 0)"
        )
        conn.execute(
            "INSERT INTO cards (id, set_code, collector_number, name) VALUES ('PLIST-71', 'PLIST', '71', 'Test')"
        )
        conn.execute(
            "INSERT INTO card_instances (set_code, collector_number, finish, location_slug, purchase_value) "
            "VALUES ('PLIST', '71', 0, 'storage:general', 0)"
        )
        conn.execute(
            "INSERT INTO deck_cards (deck_id, card_name, set_code, collector_number, finish) "
            "VALUES (1, 'PLIST #71', 'PLIST', '71', 0)"
        )

        consolidate_set_code_aliases(conn)
        conn.commit()

        self.assertEqual(
            conn.execute("SELECT set_code, collector_number FROM purchases ORDER BY collector_number").fetchall(),
            [("PLST", "71"), ("PLST", "WTH-53")],
        )
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM cards WHERE set_code = 'PLIST'").fetchone()[0], 0)
        self.assertEqual(conn.execute("SELECT set_code FROM card_instances").fetchone()[0], "PLST")
        self.assertEqual(conn.execute("SELECT card_name, set_code FROM deck_cards").fetchone(), ("PLST #71", "PLST"))


if __name__ == "__main__":
    unittest.main()
