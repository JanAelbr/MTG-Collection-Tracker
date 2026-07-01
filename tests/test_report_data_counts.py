import sqlite3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from report.report_data import load_catalog_count_by_set, load_owned_count_by_set  # noqa: E402
from util.app_tables import ensure_app_tables  # noqa: E402
from util.storage_tables import ensure_storage_tables  # noqa: E402


class ReportDataCountTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.executescript(
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
        ensure_storage_tables(self.conn)
        ensure_app_tables(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_owned_count_uses_unique_collector_numbers(self):
        self.conn.executemany(
            "INSERT INTO purchases (set_code, collector_number, purchase_value, finish) VALUES (?, ?, 1.0, ?)",
            [
                ("LTR", "1", 0),
                ("LTR", "1", 1),
                ("LTR", "2", 0),
            ],
        )
        self.conn.commit()

        counts = load_owned_count_by_set(self.conn)

        self.assertEqual(counts["LTR"], 2)

    def test_owned_count_ignores_duplicate_copies_in_instances(self):
        self.conn.execute(
            "INSERT INTO purchases (set_code, collector_number, purchase_value, finish) VALUES ('LTR', '1', 1.0, 0)"
        )
        for _ in range(2):
            self.conn.execute(
                """
                INSERT INTO card_instances (set_code, collector_number, finish, location_slug)
                VALUES ('LTR', '1', 0, 'storage:general')
                """
            )
        self.conn.commit()

        counts = load_owned_count_by_set(self.conn)

        self.assertEqual(counts["LTR"], 1)

    def test_catalog_count_uses_unique_collector_numbers(self):
        self.conn.executemany(
            "INSERT INTO cards (set_code, collector_number, name, art_style) VALUES (?, ?, ?, '')",
            [
                ("LTR", "1", "Card A"),
                ("LTR", "1", "Card A duplicate"),
                ("LTR", "2", "Card B"),
            ],
        )
        self.conn.commit()

        counts = load_catalog_count_by_set(self.conn)

        self.assertEqual(counts["LTR"], 2)


if __name__ == "__main__":
    unittest.main()
