"""Test helpers for the multi-profile storage layout.

``SingleDatabaseMixin`` serves every table from one seeded SQLite file (the
pre-profile layout most tests seed). ``ProfileStorageTestCase`` boots a real
``app.db`` + ``catalog.db`` + ``profiles/`` tree in a temp dir.
"""

import runpy
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

runpy.run_path(str(Path(__file__).resolve().with_name("_paths.py")))

from lib.db import use_single_database, use_storage_root  # noqa: E402
from lib.profile_context import PROFILE_HEADER  # noqa: E402


def single_database(path: Path):
    """Context manager: all connections (catalog and profile) open ``path``."""
    return use_single_database(Path(path))


class ProfileStorageTestCase(unittest.TestCase):
    """Fresh multi-profile storage root per test, without network access."""

    def setUp(self):
        super().setUp()
        self._temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self._temp_dir.name)
        self._stack = ExitStack()
        self.layout = self._stack.enter_context(use_storage_root(self.root))
        self._stack.enter_context(patch("util.schema._enrich_sets_from_scryfall", lambda conn: None))
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        self._stack.close()
        self._temp_dir.cleanup()

    def bootstrap(self) -> list[str]:
        from util.storage_layout import bootstrap_storage

        return bootstrap_storage()

    def client(self):
        from fastapi.testclient import TestClient

        from api.main import app

        return TestClient(app)

    @staticmethod
    def profile_headers(profile_id: str) -> dict[str, str]:
        return {PROFILE_HEADER: profile_id}
