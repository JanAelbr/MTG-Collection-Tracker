import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "server-backend"))

from util.schema import ensure_database_schema  # noqa: E402
from report.deck_queries import load_deck_list  # noqa: E402


class SchemaBootstrapTests(unittest.TestCase):
    def test_ensure_database_schema_creates_decks_table(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "collection.db"
            conn = sqlite3.connect(db_path)
            conn.execute("PRAGMA foreign_keys = ON")
            ensure_database_schema(conn)
            conn.commit()
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
            self.assertIn("decks", tables)
            self.assertIn("cards", tables)
            self.assertEqual(load_deck_list(conn), [])
            conn.close()


if __name__ == "__main__":
    unittest.main()
