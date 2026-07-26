import unittest
from pathlib import Path

import runpy

runpy.run_path(str(Path(__file__).resolve().with_name("_paths.py")))

from api.services.search_service import (  # noqa: E402
    _catalog_variant_counts_for_names,
    _dedupe_ranked_by_name,
)


class SearchCheapestDedupeTests(unittest.TestCase):
    def test_dedupe_prefers_cheapest_print(self):
        ranked = [
            {
                "name": "Sol Ring",
                "setCode": "C21",
                "collectorNumber": "1",
                "artStyle": "",
                "currentValue": 5.0,
            },
            {
                "name": "Sol Ring",
                "setCode": "LTR",
                "collectorNumber": "2",
                "artStyle": "",
                "currentValue": 1.5,
            },
            {
                "name": "Sol Ring",
                "setCode": "MH2",
                "collectorNumber": "3",
                "artStyle": "",
                "currentValue": None,
            },
            {
                "name": "Cultivate",
                "setCode": "LTR",
                "collectorNumber": "10",
                "artStyle": "",
                "currentValue": 0.25,
            },
        ]
        deduped = _dedupe_ranked_by_name(ranked)
        self.assertEqual([card["name"] for card in deduped], ["Sol Ring", "Cultivate"])
        self.assertEqual(deduped[0]["setCode"], "LTR")
        self.assertEqual(deduped[0]["currentValue"], 1.5)
        self.assertEqual(deduped[1]["setCode"], "LTR")

    def test_catalog_variant_counts_for_names(self):
        import sqlite3
        import tempfile
        from pathlib import Path

        temp_dir = tempfile.TemporaryDirectory()
        try:
            conn = sqlite3.connect(Path(temp_dir.name) / "test.db")
            conn.executescript(
                """
                CREATE TABLE cards (
                    set_code TEXT,
                    collector_number TEXT,
                    name TEXT,
                    art_style TEXT
                );
                """
            )
            conn.executemany(
                "INSERT INTO cards VALUES (?, ?, ?, ?)",
                [
                    ("C21", "1", "Sol Ring", ""),
                    ("LTR", "2", "Sol Ring", ""),
                    ("LTR", "2", "Sol Ring", ""),
                    ("LTR", "10", "Cultivate", ""),
                    ("LTR", "A-11", "Sol Ring", ""),
                ],
            )
            conn.commit()
            counts = _catalog_variant_counts_for_names(conn, ["Sol Ring", "Cultivate"])
            self.assertEqual(counts["Sol Ring"], 2)
            self.assertEqual(counts["Cultivate"], 1)
            conn.close()
        finally:
            temp_dir.cleanup()


if __name__ == "__main__":
    unittest.main()
