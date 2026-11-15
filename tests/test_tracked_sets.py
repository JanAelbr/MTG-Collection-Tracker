import sqlite3
import sys
import unittest
from pathlib import Path

COLLECTION_DIR = Path(__file__).resolve().parents[1] / "server-backend" / "collection"
if str(COLLECTION_DIR) not in sys.path:
    sys.path.insert(0, str(COLLECTION_DIR))

from util.app_tables import ensure_app_tables  # noqa: E402
from util.tracked_sets import (  # noqa: E402
    add_tracked_set,
    ensure_tracked_sets_table,
    is_set_tracked,
    list_tracked_set_codes,
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


if __name__ == "__main__":
    unittest.main()
