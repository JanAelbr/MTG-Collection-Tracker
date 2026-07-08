import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
COLLECTION_DIR = Path(__file__).resolve().parents[1] / "server-backend" / "collection"
for _path in (str(COLLECTION_DIR), str(SCRIPTS_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from util.app_tables import ensure_app_tables  # noqa: E402
from util.tracked_sets import (  # noqa: E402
    MIGRATION_SETTING_KEY,
    add_tracked_set,
    ensure_tracked_sets_table,
    is_set_tracked,
    list_tracked_set_codes,
    migrate_tracked_set_alias,
    migrate_tracked_sets_from_csv_once,
    remove_tracked_set,
)


class TrackedSetsTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        ensure_app_tables(self.conn)
        ensure_tracked_sets_table(self.conn)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_add_remove_and_lookup(self):
        add_tracked_set(self.conn, "ltr")
        self.conn.commit()

        self.assertTrue(is_set_tracked(self.conn, "ltr"))
        self.assertTrue(is_set_tracked(self.conn, "LTR"))
        self.assertEqual(list_tracked_set_codes(self.conn), ["LTR"])

        self.assertTrue(remove_tracked_set(self.conn, "LTR"))
        self.conn.commit()
        self.assertFalse(is_set_tracked(self.conn, "LTR"))
        self.assertFalse(remove_tracked_set(self.conn, "LTR"))

    def test_migration_runs_once_from_csv_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            ltr_csv = data_dir / "ltr.csv"
            mb2_csv = data_dir / "mb2.csv"
            ltr_csv.write_text("card_number,purchase_value,finish\n", encoding="utf-8")
            mb2_csv.write_text("card_number,purchase_value,finish\n", encoding="utf-8")

            with patch("util.tracked_sets._list_legacy_set_csv_files", return_value=[ltr_csv, mb2_csv]):
                inserted = migrate_tracked_sets_from_csv_once(self.conn)
            self.conn.commit()

            self.assertEqual(inserted, 2)
            self.assertEqual(list_tracked_set_codes(self.conn), ["LTR", "MB2"])
            row = self.conn.execute(
                "SELECT value FROM user_settings WHERE key = ?",
                (MIGRATION_SETTING_KEY,),
            ).fetchone()
            self.assertEqual(row[0], "1")

            with patch("util.tracked_sets._list_legacy_set_csv_files") as mock_csv:
                second_inserted = migrate_tracked_sets_from_csv_once(self.conn)
                mock_csv.assert_not_called()

            self.assertEqual(second_inserted, 0)

    def test_migrate_tracked_set_alias_moves_row(self):
        ensure_tracked_sets_table(self.conn)
        self.conn.execute(
            "INSERT INTO tracked_sets (set_code, created_at) VALUES ('PLIST', '2026-01-01T00:00:00+00:00')"
        )
        self.conn.commit()

        migrate_tracked_set_alias(self.conn, "PLIST", "PLST")
        self.conn.commit()

        self.assertEqual(list_tracked_set_codes(self.conn), ["PLST"])
        row = self.conn.execute(
            "SELECT COUNT(*) FROM tracked_sets WHERE set_code = 'PLIST'"
        ).fetchone()
        self.assertEqual(row[0], 0)


if __name__ == "__main__":
    unittest.main()
