import sqlite3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "server-backend"
COLLECTION = BACKEND / "collection"
for path in (BACKEND, COLLECTION, str(ROOT / "scripts")):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)

from api.services.scan_service import (  # noqa: E402
    ScanError,
    search_card_names_for_ocr,
)


class ScanNameSearchTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(
            """
            CREATE TABLE cards (
                set_code TEXT,
                collector_number TEXT,
                name TEXT,
                art_style TEXT,
                image_uri TEXT,
                has_nonfoil INTEGER,
                has_foil INTEGER,
                has_etched INTEGER
            )
            """
        )
        rows = [
            ("MH3", "161", "Lightning Bolt", "", "https://lb.jpg", 1, 1, 0),
            ("CLB", "48", "Counterspell", "", "https://cs.jpg", 1, 0, 0),
            ("CLU", "279", "Sacred Foundry", "", "https://sf.jpg", 0, 1, 0),
            ("MH2", "10", "Sol Ring", "", "https://sr.jpg", 1, 1, 0),
            ("ONE", "1", "Bolt Bend", "", "https://bb.jpg", 1, 0, 0),
            ("SNC", "A-12", "Alchemy Dummy", "", "https://a.jpg", 1, 0, 0),
        ]
        self.conn.executemany(
            """
            INSERT INTO cards (
                set_code, collector_number, name, art_style, image_uri,
                has_nonfoil, has_foil, has_etched
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_requires_query(self):
        with self.assertRaises(ScanError):
            search_card_names_for_ocr(self.conn, query="")

    def test_ranks_ocr_name_and_returns_prints(self):
        result = search_card_names_for_ocr(self.conn, query="Lightning Bolt 1R")
        self.assertEqual(result["resolvedName"], "Lightning Bolt")
        self.assertEqual(result["prints"][0]["setCode"], "MH3")
        self.assertEqual(result["prints"][0]["collectorNumber"], "161")
        names = [row["name"] for row in result["names"]]
        self.assertIn("Lightning Bolt", names)
        self.assertNotIn("Alchemy Dummy", names)

    def test_partial_ocr_token_match(self):
        result = search_card_names_for_ocr(self.conn, query="Sacred Found")
        self.assertEqual(result["resolvedName"], "Sacred Foundry")

    def test_fuzzy_truncated_token(self):
        self.conn.execute(
            """
            INSERT INTO cards (
                set_code, collector_number, name, art_style, image_uri,
                has_nonfoil, has_foil, has_etched
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("ONE", "55", "Bloodthirsty Aerialist", "", "https://ba.jpg", 1, 0, 0),
        )
        self.conn.commit()
        result = search_card_names_for_ocr(
            self.conn,
            query=". Bloodthirsty Aerialis -",
        )
        self.assertEqual(result["resolvedName"], "Bloodthirsty Aerialist")

    def test_explicit_name_selection(self):
        result = search_card_names_for_ocr(
            self.conn,
            query="Bolt",
            name="Bolt Bend",
        )
        self.assertEqual(result["resolvedName"], "Bolt Bend")
        self.assertEqual(result["prints"][0]["setCode"], "ONE")


if __name__ == "__main__":
    unittest.main()
