import sqlite3
import tempfile
import unittest
from pathlib import Path

import runpy

runpy.run_path(str(Path(__file__).resolve().with_name("_paths.py")))

from api.services.search_service import (  # noqa: E402
    _type_line_subtypes,
    list_search_facets,
)


class TypeLineSubtypeTests(unittest.TestCase):
    def test_basic_creature_types(self):
        self.assertEqual(
            _type_line_subtypes("Creature — Elf Druid"),
            ["Elf", "Druid"],
        )

    def test_dfc_and_hyphen_variants(self):
        self.assertEqual(
            _type_line_subtypes("Creature — Human Wizard // Creature – Spirit"),
            ["Human", "Wizard", "Spirit"],
        )


class SearchFacetsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.conn = sqlite3.connect(Path(self.temp_dir.name) / "test.db")
        self.conn.executescript(
            """
            CREATE TABLE cards (
                set_code TEXT NOT NULL,
                collector_number TEXT NOT NULL,
                name TEXT NOT NULL,
                type_line TEXT,
                oracle_text TEXT,
                art_style TEXT
            );
            """
        )
        self.conn.executemany(
            """
            INSERT INTO cards (set_code, collector_number, name, type_line, oracle_text, art_style)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                ("LTR", "1", "Llanowar Elves", "Creature — Elf Druid", "Flying\n{T}: Add {G}.", None),
                ("LTR", "2", "Bolt", "Instant", "Lightning Bolt deals 3 damage to any target.", None),
                ("LTR", "3", "Trampler", "Creature — Beast", "Trample, haste", None),
                ("LTR", "A-4", "Alchemy Elf", "Creature — Elf", "Flying", None),
            ],
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        self.temp_dir.cleanup()

    def test_list_search_facets(self):
        facets = list_search_facets(self.conn)
        self.assertEqual(facets["creatureTypes"], ["Beast", "Druid", "Elf"])
        self.assertIn("Flying", facets["keywords"])
        self.assertIn("Trample", facets["keywords"])
        self.assertIn("Haste", facets["keywords"])
        self.assertNotIn("Vigilance", facets["keywords"])


if __name__ == "__main__":
    unittest.main()
