import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import lib.config as config  # noqa: E402


class DbPathTests(unittest.TestCase):
    def test_resolve_db_path_migrates_legacy_database(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            app_dir = temp_root / "appdata"
            legacy_db = temp_root / "collection.db"
            legacy_db.write_bytes(b"sqlite")
            legacy_journal = temp_root / "collection.db-journal"
            legacy_journal.write_bytes(b"journal")

            with patch.object(config, "LEGACY_DB_PATH", legacy_db):
                db_path = config.resolve_db_path(app_dir)

            self.assertEqual(db_path, app_dir / "collection.db")
            self.assertTrue(db_path.is_file())
            self.assertFalse(legacy_db.exists())
            self.assertTrue((app_dir / "collection.db-journal").is_file())


if __name__ == "__main__":
    unittest.main()
