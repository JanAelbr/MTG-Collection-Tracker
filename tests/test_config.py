import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import lib.config as config  # noqa: E402


class DbPathTests(unittest.TestCase):
    def test_resolve_db_path_uses_app_data_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            app_dir = Path(temp_dir) / "MtgCollectionTracker"
            db_path = config.resolve_db_path(app_dir)

            self.assertEqual(db_path, app_dir / "collection.db")
            self.assertTrue(app_dir.is_dir())


if __name__ == "__main__":
    unittest.main()
