import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from lib.config import DATA_DIR, normalize_set_code, purchase_csv_path  # noqa: E402
from util.db_migrate import (  # noqa: E402
    consolidate_set_code_aliases,
    ensure_set_code_aliases,
    migrate_deprecated_set_csv_files,
)


class SetCodeAliasTests(unittest.TestCase):
    def test_normalize_set_code_maps_plist_to_plst(self):
        self.assertEqual(normalize_set_code("plist"), "PLST")
        self.assertEqual(normalize_set_code("PLST"), "PLST")
        self.assertEqual(normalize_set_code("ltr"), "LTR")

    def test_purchase_csv_path_uses_canonical_code(self):
        self.assertEqual(purchase_csv_path("PLIST").name, "plst.csv")

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

    def test_migrate_deprecated_set_csv_files_merges_alias_csv(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            alias_path = data_dir / "plist.csv"
            canonical_path = data_dir / "plst.csv"
            alias_path.write_text("card_number,purchase_value,finish\n71,0,0\n", encoding="utf-8")
            canonical_path.write_text("card_number,purchase_value,finish\nWTH-53,0,0\n", encoding="utf-8")

            original_data_dir = DATA_DIR
            try:
                import lib.config as config_module
                import util.db_migrate as migrate_module

                config_module.DATA_DIR = data_dir
                migrate_module.DATA_DIR = data_dir
                migrate_deprecated_set_csv_files()
            finally:
                config_module.DATA_DIR = original_data_dir
                migrate_module.DATA_DIR = original_data_dir

            self.assertFalse(alias_path.exists())
            contents = canonical_path.read_text(encoding="utf-8")
            self.assertIn("WTH-53", contents)
            self.assertIn("71", contents)


if __name__ == "__main__":
    unittest.main()
