import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server-backend"))

from util.db_migrate import list_top_set_codes_by_collection_size  # noqa: E402


class TopSetCodesTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.conn = sqlite3.connect(Path(self.temp_dir.name) / "test.db")
        self.conn.executescript(
            """
            CREATE TABLE purchases (
                purchase_id INTEGER PRIMARY KEY AUTOINCREMENT,
                set_code TEXT NOT NULL,
                collector_number TEXT NOT NULL,
                purchase_value REAL NOT NULL DEFAULT 0,
                finish INTEGER NOT NULL CHECK (finish IN (0, 1, 2))
            );
            CREATE TABLE tracked_sets (
                set_code TEXT PRIMARY KEY,
                created_at TEXT NOT NULL
            );
            """
        )

    def tearDown(self):
        self.conn.close()
        self.temp_dir.cleanup()

    def test_orders_by_owned_count_and_fills_from_tracked_sets(self):
        self.conn.executemany(
            "INSERT INTO purchases (set_code, collector_number, finish) VALUES (?, ?, ?)",
            [
                ("LTR", "1", 0),
                ("LTR", "2", 0),
                ("LTR", "3", 0),
                ("MKM", "1", 0),
                ("DSK", "1", 0),
            ],
        )
        self.conn.executemany(
            "INSERT INTO tracked_sets (set_code, created_at) VALUES (?, ?)",
            [("BLB", "2026-01-01"), ("OTJ", "2026-01-01")],
        )
        self.conn.commit()

        codes = list_top_set_codes_by_collection_size(self.conn, limit=5)
        self.assertEqual(codes[:3], ["LTR", "DSK", "MKM"])
        self.assertEqual(len(codes), 5)
        self.assertIn("BLB", codes)
        self.assertIn("OTJ", codes)


if __name__ == "__main__":
    unittest.main()
