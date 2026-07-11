import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "server-backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from api.services import backup_service  # noqa: E402
from util.schema import ensure_database_schema  # noqa: E402
from util.tracked_sets import add_tracked_set, list_tracked_set_codes  # noqa: E402


class BackupCatalogSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        ensure_database_schema(self.conn)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        self.temp_dir.cleanup()

    @patch("api.services.backup_service.import_set_catalog_from_scryfall", return_value=42)
    def test_sync_catalogs_registers_and_imports_missing_sets(self, mock_import):
        result = backup_service.sync_catalogs_for_sets(self.conn, ["LTR", "NCC"])

        self.assertEqual(result["synced"], ["LTR", "NCC"])
        self.assertEqual(result["skipped"], [])
        self.assertEqual(result["errors"], [])
        self.assertEqual(sorted(list_tracked_set_codes(self.conn)), ["LTR", "NCC"])
        self.assertEqual(mock_import.call_count, 2)

    @patch("api.services.backup_service.import_set_catalog_from_scryfall", return_value=10)
    def test_sync_catalogs_skips_existing_tracked_catalog(self, mock_import):
        add_tracked_set(self.conn, "LTR")
        self.conn.execute(
            """
            INSERT INTO cards (id, set_code, collector_number, name)
            VALUES ('LTR-1', 'LTR', '1', 'Sample')
            """
        )
        self.conn.commit()

        result = backup_service.sync_catalogs_for_sets(self.conn, ["LTR", "NCC"])

        self.assertEqual(result["synced"], ["NCC"])
        self.assertEqual(result["skipped"], ["LTR"])
        self.assertEqual(mock_import.call_count, 1)


if __name__ == "__main__":
    unittest.main()
