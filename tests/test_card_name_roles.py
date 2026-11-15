import sqlite3
import tempfile
import unittest
from pathlib import Path

import runpy

runpy.run_path(str(Path(__file__).resolve().with_name("_paths.py")))

from util.app_tables import ensure_app_tables  # noqa: E402
from util.card_name_roles import (  # noqa: E402
    ensure_card_name_roles_table,
    load_card_name_roles_map,
    refresh_card_name_roles_for_card,
    roles_for_card_name,
    upsert_card_name_roles,
)


class CardNameRolesTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        ensure_app_tables(self.conn)
        ensure_card_name_roles_table(self.conn)
        self.conn.executescript(
            """
            CREATE TABLE cards (
                set_code TEXT,
                collector_number TEXT,
                name TEXT,
                type_line TEXT,
                oracle_text TEXT,
                card_type TEXT
            );
            """
        )

    def tearDown(self):
        self.conn.close()
        self.temp_dir.cleanup()

    def test_upsert_and_load_by_name(self):
        roles = upsert_card_name_roles(
            self.conn,
            "Sol Ring",
            card={
                "name": "Sol Ring",
                "type_line": "Artifact",
                "oracle_text": "{T}: Add {C}{C}.",
            },
        )
        self.conn.commit()
        self.assertIn("ramp", roles)
        self.assertEqual(roles_for_card_name(self.conn, "sol ring"), roles)
        mapping = load_card_name_roles_map(self.conn)
        self.assertEqual(mapping["Sol Ring"], roles)
        self.assertEqual(mapping["sol ring"], roles)

    def test_refresh_writes_roles_for_each_name(self):
        self.conn.executemany(
            """
            INSERT INTO cards (set_code, collector_number, name, type_line, oracle_text, card_type)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                ("LTR", "1", "Cultivate", "Sorcery",
                 "Search your library for up to two basic land cards, reveal those cards, "
                 "put one onto the battlefield tapped and the other into your hand, then shuffle.",
                 "sorcery"),
                ("C21", "2", "Cultivate", "Sorcery",
                 "Search your library for up to two basic land cards, reveal those cards, "
                 "put one onto the battlefield tapped and the other into your hand, then shuffle.",
                 "sorcery"),
                ("MH2", "3", "Lightning Bolt", "Instant",
                 "Lightning Bolt deals 3 damage to any target.", "instant"),
            ],
        )
        self.conn.commit()

        for name, type_line, oracle_text, card_type in (
            ("Cultivate", "Sorcery",
             "Search your library for up to two basic land cards, reveal those cards, "
             "put one onto the battlefield tapped and the other into your hand, then shuffle.",
             "sorcery"),
            ("Lightning Bolt", "Instant", "Lightning Bolt deals 3 damage to any target.", "instant"),
        ):
            refresh_card_name_roles_for_card(self.conn, {
                "name": name,
                "type_line": type_line,
                "oracle_text": oracle_text,
                "card_type": card_type,
            })
        self.conn.commit()
        self.assertIn("ramp", roles_for_card_name(self.conn, "Cultivate"))
        self.assertIn("removal", roles_for_card_name(self.conn, "Lightning Bolt"))
