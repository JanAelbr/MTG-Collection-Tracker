import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COLLECTION = ROOT / "server-backend" / "collection"
if str(COLLECTION) not in sys.path:
    sys.path.insert(0, str(COLLECTION))

from util.price_health import card_has_price_issues, price_issues_for_card  # noqa: E402
from util.schema import ensure_database_schema  # noqa: E402


class PriceHealthTests(unittest.TestCase):
    def test_flags_missing_url_for_owned_finish(self):
        row = {
            "owned_nonfoil": True,
            "has_nonfoil": 1,
            "market_value": None,
            "cardmarket_url": None,
            "cardmarket_url_foil": None,
        }
        self.assertEqual(price_issues_for_card(row), ["missing_url:nonfoil"])
        self.assertTrue(card_has_price_issues(row))

    def test_flags_missing_price_when_url_exists(self):
        row = {
            "owned_foil": True,
            "has_foil": 1,
            "market_value_foil": None,
            "cardmarket_url": None,
            "cardmarket_url_foil": "https://www.cardmarket.com/en/Magic/Products/Singles/LTR/1",
        }
        self.assertEqual(price_issues_for_card(row), ["no_price:foil"])

    def test_ignores_unowned_finishes(self):
        row = {
            "owned_nonfoil": False,
            "has_nonfoil": 1,
            "market_value": None,
            "cardmarket_url": None,
        }
        self.assertEqual(price_issues_for_card(row), [])


class CheapestOwnedPrintingTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.conn = sqlite3.connect(Path(self.temp_dir.name) / "test.db")
        self.conn.row_factory = sqlite3.Row
        ensure_database_schema(self.conn)
        self.conn.execute(
            """
            INSERT INTO cards (
                id, set_code, collector_number, name, art_style,
                market_value, market_value_foil, has_nonfoil, has_foil, has_etched
            ) VALUES
            ('LTR-1', 'LTR', '1', 'Lightning Bolt', 'All', 2.0, 4.0, 1, 1, 0),
            ('MH3-10', 'MH3', '10', 'Lightning Bolt', 'All', 1.0, 2.0, 1, 1, 0)
            """
        )
        self.conn.execute(
            """
            INSERT INTO purchases (set_code, collector_number, finish, purchase_value)
            VALUES ('LTR', '1', 0, 1.0), ('MH3', '10', 0, 0.5)
            """
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        self.temp_dir.cleanup()

    def test_finds_cheapest_owned_printing_by_name(self):
        from util.deck_helpers import cheapest_owned_printing_by_name

        result = cheapest_owned_printing_by_name(self.conn, "Lightning Bolt")
        self.assertIsNotNone(result)
        self.assertEqual(result["set_code"], "MH3")
        self.assertEqual(result["collector_number"], "10")
        self.assertEqual(result["current_value"], 1.0)


if __name__ == "__main__":
    unittest.main()
