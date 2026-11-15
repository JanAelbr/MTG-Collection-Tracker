import sys
import unittest
from pathlib import Path

COLLECTION_DIR = Path(__file__).resolve().parents[1] / "server-backend" / "collection"
if str(COLLECTION_DIR) not in sys.path:
    sys.path.insert(0, str(COLLECTION_DIR))

from lib.config import normalize_set_code  # noqa: E402


class SetCodeAliasTests(unittest.TestCase):
    def test_normalize_set_code_maps_plist_to_plst(self):
        self.assertEqual(normalize_set_code("plist"), "PLST")
        self.assertEqual(normalize_set_code("PLST"), "PLST")
        self.assertEqual(normalize_set_code("ltr"), "LTR")


if __name__ == "__main__":
    unittest.main()
