import sqlite3
import tempfile
import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from util.card_finishes import (  # noqa: E402
    FINISH_ETCHED,
    FINISH_FOIL,
    FINISH_NONFOIL,
    card_finish_flags,
    finish_available,
    finish_has_pricing,
    infer_finish_for_print,
    normalize_finish,
    parse_finish_from_row,
)
from util.cardmarket_prices import price_from_guide_entry  # noqa: E402
from util.db_migrate import ensure_card_columns  # noqa: E402
from util.finish_migration import ensure_finish_migration  # noqa: E402


class CardFinishesTests(unittest.TestCase):
    def test_card_finish_flags_parses_etched(self):
        flags = card_finish_flags({"finishes": ["etched"]})
        self.assertEqual(flags, (0, 0, 1))

    def test_card_finish_flags_parses_all_three(self):
        flags = card_finish_flags({"finishes": ["nonfoil", "foil", "etched"]})
        self.assertEqual(flags, (1, 1, 1))

    def test_normalize_finish_aliases(self):
        self.assertEqual(normalize_finish("etched"), FINISH_ETCHED)
        self.assertEqual(normalize_finish("foil"), FINISH_FOIL)
        self.assertEqual(normalize_finish("1"), FINISH_FOIL)

    def test_parse_finish_from_row_prefers_finish_column(self):
        self.assertEqual(
            parse_finish_from_row({"finish": "etched", "foil": "1"}),
            FINISH_ETCHED,
        )

    def test_infer_finish_for_print_maps_foil_to_etched(self):
        self.assertEqual(
            infer_finish_for_print(
                FINISH_FOIL,
                has_nonfoil=0,
                has_foil=0,
                has_etched=1,
            ),
            FINISH_ETCHED,
        )

    def test_finish_available_respects_has_flags(self):
        row = {
            "has_nonfoil": 0,
            "has_foil": 1,
            "has_etched": 0,
            "market_value": 5.0,
            "market_value_foil": 7.0,
            "market_value_etched": None,
        }
        self.assertTrue(finish_available(row, FINISH_NONFOIL))
        self.assertTrue(finish_available(row, FINISH_FOIL))
        self.assertFalse(finish_available(row, FINISH_ETCHED))

    def test_finish_available_requires_price_not_catalog_flag(self):
        row = {
            "has_foil": 1,
            "market_value_foil": None,
        }
        self.assertFalse(finish_available(row, FINISH_FOIL))

    def test_finish_has_pricing_uses_guide_prices(self):
        row = {"market_value": None, "market_value_foil": None}
        guide = {"foil": {"trend": 4.5}}
        self.assertTrue(finish_has_pricing(row, FINISH_FOIL, guide))
        self.assertFalse(finish_has_pricing(row, FINISH_NONFOIL, guide))

    def test_price_from_guide_entry_uses_nonfoil_keys_for_etched(self):
        entry = {"trend": 2.42, "trend-foil": 5.54}
        self.assertEqual(price_from_guide_entry(entry, FINISH_ETCHED), 2.42)


class FinishMigrationTests(unittest.TestCase):
    def test_migrates_foil_column_to_finish(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            conn = sqlite3.connect(db_path)
            try:
                conn.executescript(
                    """
                    CREATE TABLE cards (
                        set_code TEXT,
                        collector_number TEXT,
                        has_nonfoil INTEGER,
                        has_foil INTEGER,
                        has_etched INTEGER,
                        market_value REAL,
                        market_value_foil REAL,
                        market_value_etched REAL
                    );
                    INSERT INTO cards VALUES ('CMR', '518', 0, 0, 1, NULL, NULL, NULL);
                    CREATE TABLE purchases (
                        purchase_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        set_code TEXT,
                        collector_number TEXT,
                        foil INTEGER NOT NULL,
                        purchase_value REAL NOT NULL DEFAULT 0
                    );
                    INSERT INTO purchases (set_code, collector_number, foil, purchase_value)
                    VALUES ('CMR', '518', 1, 3.5);
                    """
                )
                ensure_card_columns(conn)
                conn.commit()
                columns = {
                    row[1]
                    for row in conn.execute("PRAGMA table_info(purchases)").fetchall()
                }
                self.assertIn("finish", columns)
                self.assertNotIn("foil", columns)
                finish = conn.execute(
                    "SELECT finish FROM purchases WHERE set_code = 'CMR'"
                ).fetchone()[0]
                self.assertEqual(finish, FINISH_ETCHED)
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
