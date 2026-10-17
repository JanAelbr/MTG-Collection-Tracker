import runpy
import sqlite3
from pathlib import Path

runpy.run_path(str(Path(__file__).resolve().with_name("_paths.py")))

from tests._app_fixture import ProfileStorageTestCase  # noqa: E402
from lib.db import connect_catalog, connect_profile, table_schema  # noqa: E402
from util.profile_registry import list_profiles  # noqa: E402


def _seed_catalog_card(set_code: str = "LTR", number: str = "1", name: str = "Frodo") -> None:
    conn = connect_catalog()
    try:
        conn.execute(
            """
            INSERT INTO sets (set_code, name, updated_at)
            VALUES (?, ?, '2026-01-01')
            ON CONFLICT(set_code) DO NOTHING
            """,
            (set_code, f"{set_code} set"),
        )
        conn.execute(
            """
            INSERT INTO cards (id, set_code, collector_number, name, has_nonfoil, has_foil, market_value)
            VALUES (?, ?, ?, ?, 1, 1, 2.5)
            """,
            (f"{set_code}-{number}", set_code, number, name),
        )
        conn.commit()
    finally:
        conn.close()


def _own(profile_id: str, set_code: str = "LTR", number: str = "1") -> None:
    conn = connect_profile(profile_id)
    try:
        conn.execute(
            "INSERT INTO purchases (set_code, collector_number, finish, purchase_value) VALUES (?, ?, 0, 1)",
            (set_code, number),
        )
        conn.commit()
    finally:
        conn.close()


class ProfileApiTests(ProfileStorageTestCase):
    def setUp(self):
        super().setUp()
        self.default_id = self.bootstrap()[0]
        self.api = self.client()

    def test_fresh_install_creates_default_profile(self):
        payload = self.api.get("/api/profiles").json()
        self.assertEqual(len(payload["profiles"]), 1)
        self.assertEqual(payload["defaultProfileId"], self.default_id)
        self.assertTrue(self.layout.profile_db(self.default_id).is_file())
        self.assertTrue(self.layout.catalog_db.is_file())

    def test_create_rename_and_delete_profile(self):
        created = self.api.post("/api/profiles", json={"name": "Trade binder", "color": "teal"})
        self.assertEqual(created.status_code, 201, created.text)
        profile_id = created.json()["id"]
        self.assertEqual(created.json()["avatar"], "TB")

        duplicate_name = self.api.post("/api/profiles", json={"name": "trade BINDER"})
        self.assertEqual(duplicate_name.status_code, 400)

        renamed = self.api.patch(f"/api/profiles/{profile_id}", json={"name": "Trades"})
        self.assertEqual(renamed.json()["name"], "Trades")

        deleted = self.api.delete(f"/api/profiles/{profile_id}")
        self.assertEqual(deleted.status_code, 200, deleted.text)
        self.assertFalse(self.layout.profile_dir(profile_id).exists())
        self.assertTrue(any(self.layout.trash_dir.iterdir()))

    def test_last_profile_cannot_be_deleted(self):
        response = self.api.delete(f"/api/profiles/{self.default_id}")
        self.assertEqual(response.status_code, 409)

    def test_unknown_profile_header_returns_404(self):
        response = self.api.get("/api/settings", headers=self.profile_headers("f" * 32))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"]["code"], "profile_not_found")

    def test_profiles_are_isolated(self):
        _seed_catalog_card()
        other_id = self.api.post("/api/profiles", json={"name": "Second"}).json()["id"]
        _own(self.default_id)

        def owned(profile_id: str) -> int:
            conn = connect_profile(profile_id)
            try:
                return conn.execute("SELECT COUNT(*) FROM purchases").fetchone()[0]
            finally:
                conn.close()

        self.assertEqual(owned(self.default_id), 1)
        self.assertEqual(owned(other_id), 0)

        self.api.patch(
            "/api/settings",
            json={"pageSize": 50},
            headers=self.profile_headers(other_id),
        )
        default_settings = self.api.get("/api/settings", headers=self.profile_headers(self.default_id)).json()
        other_settings = self.api.get("/api/settings", headers=self.profile_headers(other_id)).json()
        self.assertEqual(other_settings["pageSize"], 50)
        self.assertNotEqual(default_settings["pageSize"], 50)

    def test_duplicate_copies_profile_state(self):
        _seed_catalog_card()
        _own(self.default_id)
        copy = self.api.post(
            "/api/profiles",
            json={"name": "Copy", "copyFrom": self.default_id},
        ).json()
        self.assertEqual(copy["stats"]["ownedPrints"], 1)

    def test_export_and_import_as_new_profile(self):
        _seed_catalog_card()
        _own(self.default_id)
        exported = self.api.get(f"/api/profiles/{self.default_id}/export")
        self.assertEqual(exported.status_code, 200)
        self.assertIn("my-collection", exported.headers["content-disposition"])

        imported = self.api.post(
            "/api/profiles/import",
            files={"file": ("backup.mtgbackup.zip", exported.content, "application/zip")},
        )
        self.assertEqual(imported.status_code, 201, imported.text)
        profile = imported.json()["profile"]
        self.assertEqual(profile["name"], "My collection (2)")
        self.assertEqual(profile["stats"]["ownedPrints"], 1)
        self.assertEqual(len(list_profiles()), 2)

    def test_profile_connection_has_no_shadow_catalog_tables(self):
        conn = connect_profile(self.default_id)
        try:
            self.assertEqual(table_schema(conn, "cards"), "catalog")
            self.assertEqual(table_schema(conn, "art_style_rules"), "catalog")
            self.assertEqual(table_schema(conn, "purchases"), "main")
            main_tables = {
                row[0] for row in conn.execute("SELECT name FROM main.sqlite_master WHERE type = 'table'")
            }
        finally:
            conn.close()
        self.assertNotIn("cards", main_tables)
        self.assertNotIn("sets", main_tables)


class PriceSyncScopeTests(ProfileStorageTestCase):
    def test_scope_unions_every_profile(self):
        from api.services.price_sync_service import resolve_price_sync_scope, scope_price_moves_to_profile

        default_id = self.bootstrap()[0]
        second = self.client().post("/api/profiles", json={"name": "Second", "color": "rose"}).json()
        catalog = connect_catalog()
        try:
            catalog.execute(
                "INSERT INTO sets (set_code, name, updated_at) VALUES ('LTR', 'LOTR', '2026-01-01')"
            )
            catalog.execute(
                "INSERT INTO sets (set_code, name, updated_at) VALUES ('MH3', 'MH3', '2026-01-01')"
            )
            catalog.commit()
        finally:
            catalog.close()
        first = connect_profile(default_id)
        try:
            first.execute(
                "INSERT INTO user_settings (key, value) VALUES ('favorite_sets', ?)",
                ('["LTR"]',),
            )
            first.commit()
        finally:
            first.close()
        other = connect_profile(second["id"])
        try:
            other.execute(
                "INSERT INTO purchases (set_code, collector_number, finish, purchase_value) VALUES ('MH3', '1', 0, 1)"
            )
            other.commit()
            scan, full = resolve_price_sync_scope(other)
            movers, cards = scope_price_moves_to_profile(
                other,
                None,
                [{
                    "setCode": "LTR",
                    "collectorNumber": "1",
                    "finishId": 0,
                    "delta": 1,
                    "percent": 10,
                }, {
                    "setCode": "MH3",
                    "collectorNumber": "1",
                    "finishId": 0,
                    "delta": 2,
                    "percent": 20,
                }],
            )
        finally:
            other.close()
        self.assertIn("LTR", scan)
        self.assertIn("MH3", scan)
        self.assertEqual(full, {"LTR"})
        self.assertEqual([card["setCode"] for card in cards], ["MH3"])
        self.assertTrue(movers["absolute"]["risers"])


class LegacyMigrationTests(ProfileStorageTestCase):
    def _seed_legacy(self) -> None:
        from util.schema import ensure_database_schema

        conn = sqlite3.connect(self.layout.legacy_db)
        conn.row_factory = sqlite3.Row
        try:
            ensure_database_schema(conn)
            conn.execute(
                "INSERT INTO cards (id, set_code, collector_number, name) VALUES ('x', 'LTR', '1', 'Frodo')"
            )
            conn.execute(
                "INSERT INTO purchases (set_code, collector_number, finish, purchase_value) VALUES ('LTR', '1', 0, 3)"
            )
            conn.execute(
                "INSERT OR REPLACE INTO user_settings (key, value) VALUES ('price_sync_checked_date', '2026-10-01')"
            )
            conn.commit()
        finally:
            conn.close()

    def test_legacy_database_is_split(self):
        self._seed_legacy()
        profile_ids = self.bootstrap()
        self.assertEqual(len(profile_ids), 1)
        self.assertFalse(self.layout.legacy_db.exists())
        self.assertTrue(any(self.layout.backups_dir.glob("collection-pre-profiles-*.db")))

        catalog = sqlite3.connect(self.layout.catalog_db)
        try:
            catalog_tables = {r[0] for r in catalog.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            meta = catalog.execute(
                "SELECT value FROM catalog_meta WHERE key = 'price_sync_checked_date'"
            ).fetchone()
        finally:
            catalog.close()
        self.assertIn("cards", catalog_tables)
        self.assertNotIn("purchases", catalog_tables)
        self.assertEqual(meta[0], "2026-10-01")

        conn = connect_profile(profile_ids[0])
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM purchases").fetchone()[0], 1)
            self.assertEqual(table_schema(conn, "cards"), "catalog")
            leaked = conn.execute(
                "SELECT COUNT(*) FROM user_settings WHERE key = 'price_sync_checked_date'"
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(leaked, 0)

    def test_migration_is_not_repeated(self):
        self._seed_legacy()
        first = self.bootstrap()
        second = self.bootstrap()
        self.assertEqual(first, second)
