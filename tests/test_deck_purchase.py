import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from lib.deck_csv import DeckEntry  # noqa: E402
from lib.deck_purchase import allocate_deck_purchase_prices  # noqa: E402
from lib.purchase_loader import build_deck_purchase_rows  # noqa: E402
from util.deck_tables import ensure_deck_tables  # noqa: E402


class DeckPurchaseTests(unittest.TestCase):
    def test_allocate_by_market_value(self):
        lines = [
            {"qty": 1, "unit_market": 10.0},
            {"qty": 1, "unit_market": 30.0},
        ]
        prices = allocate_deck_purchase_prices(lines, 40.0)
        self.assertAlmostEqual(prices[0], 10.0)
        self.assertAlmostEqual(prices[1], 30.0)

    def test_allocate_evenly_without_market_values(self):
        lines = [
            {"qty": 1, "unit_market": None},
            {"qty": 3, "unit_market": None},
        ]
        prices = allocate_deck_purchase_prices(lines, 40.0)
        self.assertAlmostEqual(prices[0], 10.0)
        self.assertAlmostEqual(sum(prices[i] * lines[i]["qty"] for i in range(len(lines))), 40.0)

    def test_build_deck_purchase_rows_allocates_deck_price(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        db_path = Path(temp_dir.name) / "collection.db"
        decks_dir = Path(temp_dir.name) / "decks"
        decks_dir.mkdir()
        deck_csv = decks_dir / "sample.csv"
        deck_csv.write_text(
            "set_code;collector_number;foil;qty;section\n"
            "ABC;1;0;1;main\n"
            "ABC;2;0;3;main\n",
            encoding="utf-8",
        )
        deck_entry = DeckEntry(
            name="Sample Deck",
            purchase_price=40.0,
            path=deck_csv,
            slug="sample",
        )

        conn = sqlite3.connect(db_path)
        ensure_deck_tables(conn)
        conn.executescript(
            """
            CREATE TABLE cards (
                id TEXT PRIMARY KEY,
                set_code TEXT NOT NULL,
                collector_number TEXT NOT NULL,
                name TEXT NOT NULL,
                market_value REAL,
                market_value_foil REAL,
                market_value_etched REAL
            );
            """
        )
        conn.execute(
            "INSERT INTO cards VALUES ('ABC-1', 'ABC', '1', 'Expensive', 30, NULL, NULL)"
        )
        conn.execute(
            "INSERT INTO cards VALUES ('ABC-2', 'ABC', '2', 'Cheap', 10, NULL, NULL)"
        )
        conn.execute(
            """
            INSERT INTO decks (name, slug, purchase_price, created_at, updated_at)
            VALUES ('Sample Deck', 'sample', 40, '2026-01-01', '2026-01-01')
            """
        )
        conn.commit()
        cursor = conn.cursor()

        rows = build_deck_purchase_rows(cursor, deck_entry)
        conn.close()
        self.assertEqual(len(rows), 2)
        by_number = {row["collector_number"]: row["purchase_value"] for row in rows}
        self.assertAlmostEqual(by_number["1"], 20.0)
        self.assertAlmostEqual(by_number["2"], 20.0 / 3)


if __name__ == "__main__":
    unittest.main()
