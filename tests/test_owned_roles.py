import sqlite3
import tempfile
import unittest
from pathlib import Path

import runpy

runpy.run_path(str(Path(__file__).resolve().with_name("_paths.py")))

from api.services.search_service import (  # noqa: E402
    _rank_search_pool,
    list_owned_role_counts,
    normalize_search_sort,
)
from util.card_name_roles import ensure_card_name_roles_table, serialize_roles  # noqa: E402


class SearchRaritySortTests(unittest.TestCase):
    def test_normalize_includes_rarity(self):
        self.assertEqual(normalize_search_sort("rarity"), "rarity")
        self.assertEqual(normalize_search_sort("power"), "power")
        self.assertEqual(normalize_search_sort("nope"), "newest")

    def test_rank_search_pool_by_rarity(self):
        pool = [
            {"name": "Mythic", "rarity": "mythic", "setCode": "A", "collectorNumber": "1"},
            {"name": "Common", "rarity": "common", "setCode": "A", "collectorNumber": "2"},
            {"name": "Rare", "rarity": "rare", "setCode": "A", "collectorNumber": "3"},
        ]
        ranked = _rank_search_pool(
            pool,
            sort="rarity",
            sort_dir="asc",
            release_dates={},
        )
        self.assertEqual([card["name"] for card in ranked], ["Common", "Rare", "Mythic"])

        ranked_desc = _rank_search_pool(
            pool,
            sort="rarity",
            sort_dir="desc",
            release_dates={},
        )
        self.assertEqual(
            [card["name"] for card in ranked_desc],
            ["Mythic", "Rare", "Common"],
        )

    def test_rank_search_pool_by_power(self):
        pool = [
            {"name": "Small", "power": "1", "setCode": "A", "collectorNumber": "1"},
            {"name": "Big", "power": "5", "setCode": "A", "collectorNumber": "2"},
            {"name": "Star", "power": "*", "setCode": "A", "collectorNumber": "3"},
        ]
        ranked = _rank_search_pool(
            pool,
            sort="power",
            sort_dir="desc",
            release_dates={},
        )
        self.assertEqual([card["name"] for card in ranked], ["Big", "Small", "Star"])


class OwnedRoleCountsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.conn = sqlite3.connect(Path(self.temp_dir.name) / "test.db")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(
            """
            CREATE TABLE cards (
                set_code TEXT NOT NULL,
                collector_number TEXT NOT NULL,
                name TEXT NOT NULL,
                art_style TEXT,
                has_nonfoil INTEGER,
                has_foil INTEGER,
                has_etched INTEGER
            );
            CREATE TABLE purchases (
                purchase_id INTEGER PRIMARY KEY AUTOINCREMENT,
                set_code TEXT NOT NULL,
                collector_number TEXT NOT NULL,
                purchase_value REAL NOT NULL DEFAULT 0,
                finish INTEGER NOT NULL DEFAULT 0
            );
            """
        )
        ensure_card_name_roles_table(self.conn)
        self.conn.execute(
            """
            INSERT INTO cards (set_code, collector_number, name, art_style, has_nonfoil, has_foil, has_etched)
            VALUES
                ('LTR', '1', 'Sol Ring', NULL, 1, 0, 0),
                ('LTR', '2', 'Cultivate', NULL, 1, 0, 0),
                ('LTR', '3', 'Counterspell', NULL, 1, 0, 0),
                ('LTR', '4', 'Unowned Ramp', NULL, 1, 0, 0)
            """
        )
        self.conn.execute(
            """
            INSERT INTO purchases (set_code, collector_number, purchase_value, finish)
            VALUES
                ('LTR', '1', 1.0, 0),
                ('LTR', '2', 1.0, 0),
                ('LTR', '3', 1.0, 0)
            """
        )
        self.conn.executemany(
            """
            INSERT INTO card_name_roles (name, roles, updated_at)
            VALUES (?, ?, '2026-01-01')
            """,
            [
                ("Sol Ring", serialize_roles(["ramp", "fast_mana"])),
                ("Cultivate", serialize_roles(["ramp"])),
                ("Counterspell", serialize_roles(["counterspell", "interaction"])),
                ("Unowned Ramp", serialize_roles(["ramp"])),
            ],
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        self.temp_dir.cleanup()

    def test_list_owned_role_counts(self):
        payload = list_owned_role_counts(self.conn)
        by_id = {row["id"]: row["count"] for row in payload["roles"]}
        self.assertEqual(by_id["ramp"], 2)  # Sol Ring + Cultivate; not Unowned Ramp
        self.assertEqual(by_id["fast_mana"], 1)
        self.assertEqual(by_id["counterspell"], 1)
        self.assertEqual(by_id["interaction"], 1)
        self.assertEqual(by_id["draw"], 0)
        self.assertIn("removal", by_id)

    def test_list_owned_role_counts_storage_filter(self):
        self.conn.executescript(
            """
            CREATE TABLE storage_locations (
                location_slug TEXT PRIMARY KEY,
                label TEXT,
                location_type TEXT
            );
            CREATE TABLE card_instances (
                instance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                set_code TEXT NOT NULL,
                collector_number TEXT NOT NULL,
                finish INTEGER NOT NULL DEFAULT 0,
                location_slug TEXT NOT NULL,
                purchase_value REAL
            );
            INSERT INTO storage_locations (location_slug, label, location_type)
            VALUES ('storage:general', 'General', 'storage'),
                   ('binder:a', 'Binder A', 'binder');
            INSERT INTO card_instances (set_code, collector_number, finish, location_slug, purchase_value)
            VALUES ('LTR', '1', 0, 'storage:general', 1),
                   ('LTR', '2', 0, 'binder:a', 1),
                   ('LTR', '3', 0, 'storage:general', 1);
            """
        )
        self.conn.commit()

        binder_only = list_owned_role_counts(
            self.conn,
            storage_filters=["binder:a"],
        )
        by_id = {row["id"]: row["count"] for row in binder_only["roles"]}
        self.assertEqual(by_id["ramp"], 1)  # Cultivate only
        self.assertEqual(by_id["fast_mana"], 0)
        self.assertEqual(by_id["counterspell"], 0)


if __name__ == "__main__":
    unittest.main()
