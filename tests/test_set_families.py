import sqlite3
import tempfile
import unittest
from pathlib import Path

import runpy
import sys

runpy.run_path(str(Path(__file__).resolve().with_name("_paths.py")))

from util.set_catalog import SETS_TABLE_SQL, ensure_sets_columns, upsert_set_row  # noqa: E402
from util.set_families import (  # noqa: E402
    build_family_index,
    effective_family_root,
    family_members_for_root,
    resolve_set_codes_for_scope,
)


class SetFamiliesTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.conn = sqlite3.connect(Path(self.temp_dir.name) / "test.db")
        self.conn.executescript(SETS_TABLE_SQL)
        ensure_sets_columns(self.conn)
        self.cursor = self.conn.cursor()

    def tearDown(self):
        self.conn.close()
        self.temp_dir.cleanup()

    def _seed(self, code, *, set_type=None, parent=None, name=None):
        upsert_set_row(
            self.cursor,
            code,
            name or code,
            None,
            None,
            "2026-07-23",
            set_type=set_type,
            parent_set_code=parent,
        )

    def test_ltr_family_clusters_commander_and_tokens(self):
        self._seed("LTR", set_type="draft_innovation")
        self._seed("LTC", set_type="commander", parent="LTR")
        self._seed("TLTR", set_type="token", parent="LTR")
        self._seed("WHO", set_type="commander")
        self.conn.commit()

        from util.set_families import load_set_relations

        relations = load_set_relations(self.conn)
        known = {"LTR", "LTC", "TLTR", "WHO"}
        families = build_family_index(known, relations)

        self.assertEqual(families["LTR"], ["LTR", "LTC", "TLTR"])
        self.assertEqual(families["WHO"], ["WHO"])
        self.assertEqual(effective_family_root("LTC", relations, known), "LTR")
        self.assertEqual(
            family_members_for_root("LTR", known, relations),
            ["LTR", "LTC", "TLTR"],
        )

    def test_orphan_child_is_singleton_when_parent_missing(self):
        self._seed("LTC", set_type="commander", parent="LTR")
        self.conn.commit()

        from util.set_families import load_set_relations

        relations = load_set_relations(self.conn)
        known = {"LTC"}
        self.assertEqual(effective_family_root("LTC", relations, known), "LTC")
        self.assertEqual(family_members_for_root("LTC", known, relations), ["LTC"])

    def test_resolve_set_codes_family_expands(self):
        self._seed("LTR", set_type="draft_innovation")
        self._seed("LTC", set_type="commander", parent="LTR")
        self._seed("TLTR", set_type="token", parent="LTR")
        self.conn.executescript(
            """
            CREATE TABLE cards (
                set_code TEXT,
                collector_number TEXT,
                name TEXT
            );
            CREATE TABLE tracked_sets (
                set_code TEXT PRIMARY KEY,
                created_at TEXT NOT NULL
            );
            """
        )
        for code in ("LTR", "LTC", "TLTR"):
            self.conn.execute(
                "INSERT INTO tracked_sets (set_code, created_at) VALUES (?, ?)",
                (code, "2026-07-23"),
            )
            self.conn.execute(
                "INSERT INTO cards (set_code, collector_number, name) VALUES (?, ?, ?)",
                (code, "1", code),
            )
        self.conn.commit()

        self.assertEqual(
            resolve_set_codes_for_scope(self.conn, set_code="LTR", family=False),
            ["LTR"],
        )
        self.assertEqual(
            resolve_set_codes_for_scope(self.conn, set_code="LTR", family=True),
            ["LTR", "LTC", "TLTR"],
        )
        self.assertEqual(
            resolve_set_codes_for_scope(self.conn, set_code="LTC", family=True),
            ["LTR", "LTC", "TLTR"],
        )

    def test_scryfall_family_members_uses_parent_links(self):
        from util.set_families import scryfall_family_members

        payloads = [
            {"code": "ltr", "set_type": "draft_innovation"},
            {"code": "ltc", "set_type": "commander", "parent_set_code": "ltr"},
            {"code": "tltr", "set_type": "token", "parent_set_code": "ltr"},
            {"code": "who", "set_type": "commander"},
        ]
        self.assertEqual(
            scryfall_family_members("LTC", payloads),
            ["LTR", "LTC", "TLTR"],
        )
        self.assertEqual(scryfall_family_members("WHO", payloads), ["WHO"])


if __name__ == "__main__":
    unittest.main()
