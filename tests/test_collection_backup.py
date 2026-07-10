import io
import json
import sqlite3
import zipfile
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from util.collection_backup import (  # noqa: E402
    build_collection_payload,
    export_collection_zip,
    import_collection_zip,
    preview_backup,
)
from util.schema import ensure_database_schema  # noqa: E402


class CollectionBackupTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        ensure_database_schema(self.conn)
        self._seed_sample_data()
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        self.temp_dir.cleanup()

    def _seed_sample_data(self):
        self.conn.execute(
            """
            INSERT INTO purchases (set_code, collector_number, finish, purchase_value)
            VALUES ('LTR', '1', 0, 2.5)
            """
        )
        self.conn.execute(
            """
            INSERT INTO decks (name, slug, purchase_price, created_at, updated_at)
            VALUES ('Sample Deck', 'sample-deck', 25.0, '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')
            """
        )
        deck_id = self.conn.execute("SELECT deck_id FROM decks").fetchone()[0]
        self.conn.execute(
            """
            INSERT INTO deck_cards (
                deck_id, card_name, set_code, collector_number, finish,
                qty, owned_qty, section, sort_order, in_catalog
            ) VALUES (?, 'Card One', 'LTR', '2', 0, 1, 1, 'main', 0, 1)
            """,
            (deck_id,),
        )
        self.conn.execute(
            """
            INSERT INTO storage_locations (
                location_slug, label, location_type, sort_order, is_system
            ) VALUES ('storage:box-a', 'Box A', 'storage', 950, 0)
            """
        )
        self.conn.execute(
            """
            INSERT INTO card_instances (
                set_code, collector_number, finish, location_slug, purchase_value
            ) VALUES ('LTR', '1', 0, 'storage:box-a', 2.5)
            """
        )
        self.conn.execute(
            """
            INSERT INTO user_settings (key, value)
            VALUES ('page_size', '50')
            """
        )

    def test_export_and_replace_import_round_trip(self):
        archive = export_collection_zip(self.conn)

        replace_conn = sqlite3.connect(":memory:")
        replace_conn.row_factory = sqlite3.Row
        ensure_database_schema(replace_conn)
        result = import_collection_zip(replace_conn, archive, mode="replace")
        replace_conn.commit()

        self.assertEqual(result["mode"], "replace")
        self.assertEqual(result["summary"]["purchases"], 1)
        self.assertEqual(result["summary"]["decks"], 1)
        self.assertEqual(replace_conn.execute("SELECT COUNT(*) FROM purchases").fetchone()[0], 1)
        self.assertEqual(replace_conn.execute("SELECT COUNT(*) FROM deck_cards").fetchone()[0], 1)
        self.assertEqual(replace_conn.execute("SELECT COUNT(*) FROM card_instances").fetchone()[0], 1)
        self.assertEqual(
            replace_conn.execute(
                "SELECT value FROM user_settings WHERE key = 'page_size'",
            ).fetchone()[0],
            "50",
        )

    def test_merge_import_combines_purchases_and_instances(self):
        archive = export_collection_zip(self.conn)

        merge_path = Path(self.temp_dir.name) / "merge.db"
        merge_conn = sqlite3.connect(merge_path)
        merge_conn.row_factory = sqlite3.Row
        ensure_database_schema(merge_conn)
        merge_conn.execute(
            """
            INSERT INTO storage_locations (
                location_slug, label, location_type, sort_order, is_system
            ) VALUES ('storage:box-a', 'Box A', 'storage', 950, 0)
            """
        )
        merge_conn.execute(
            """
            INSERT INTO purchases (set_code, collector_number, finish, purchase_value)
            VALUES ('LTR', '3', 0, 1.0)
            """
        )
        merge_conn.execute(
            """
            INSERT INTO card_instances (
                set_code, collector_number, finish, location_slug, purchase_value
            ) VALUES ('LTR', '3', 0, 'storage:box-a', 1.0)
            """
        )
        merge_conn.commit()

        import_collection_zip(merge_conn, archive, mode="merge")
        merge_conn.commit()

        self.assertEqual(merge_conn.execute("SELECT COUNT(*) FROM purchases").fetchone()[0], 2)
        self.assertEqual(merge_conn.execute("SELECT COUNT(*) FROM card_instances").fetchone()[0], 2)
        merge_conn.close()

    def test_merge_same_export_is_noop(self):
        archive = export_collection_zip(self.conn)
        before = {
            "purchases": self.conn.execute("SELECT COUNT(*) FROM purchases").fetchone()[0],
            "decks": self.conn.execute("SELECT COUNT(*) FROM decks").fetchone()[0],
            "deck_cards": self.conn.execute("SELECT COUNT(*) FROM deck_cards").fetchone()[0],
            "instances": self.conn.execute("SELECT COUNT(*) FROM card_instances").fetchone()[0],
            "purchase_value": self.conn.execute(
                "SELECT purchase_value FROM purchases WHERE set_code = 'LTR' AND collector_number = '1'",
            ).fetchone()[0],
        }

        import_collection_zip(self.conn, archive, mode="merge")
        self.conn.commit()

        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM purchases").fetchone()[0],
            before["purchases"],
        )
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM decks").fetchone()[0],
            before["decks"],
        )
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM deck_cards").fetchone()[0],
            before["deck_cards"],
        )
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM card_instances").fetchone()[0],
            before["instances"],
        )
        self.assertEqual(
            self.conn.execute(
                "SELECT purchase_value FROM purchases WHERE set_code = 'LTR' AND collector_number = '1'",
            ).fetchone()[0],
            before["purchase_value"],
        )

    def test_preview_backup_returns_summary(self):
        archive = export_collection_zip(self.conn)
        preview = preview_backup(archive)
        self.assertEqual(preview["summary"]["purchases"], 1)
        self.assertIn("LTR", preview["summary"]["setsReferenced"])

    def test_export_includes_art_style_rules_from_database(self):
        archive = export_collection_zip(self.conn)
        with zipfile.ZipFile(io.BytesIO(archive)) as exported:
            names = set(exported.namelist())
            self.assertIn("art_styles/ltr.json", names)
            rules = json.loads(exported.read("art_styles/ltr.json").decode("utf-8"))
            self.assertTrue(any(rule.get("name") == "01. Main Set" for rule in rules))

    def test_build_collection_payload_uses_camel_case(self):
        payload = build_collection_payload(self.conn)
        self.assertEqual(payload["purchases"][0]["setCode"], "LTR")
        self.assertEqual(payload["deckCards"][0]["deckSlug"], "sample-deck")


if __name__ == "__main__":
    unittest.main()
