import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "server-backend"
COLLECTION = BACKEND / "collection"
for path in (BACKEND, COLLECTION, str(ROOT / "scripts")):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)

from api.services.scan_service import (  # noqa: E402
    ScanError,
    ingest_scan,
    titles_likely_match,
)


def _row(name, collector_number, *, image="https://example/card.jpg", nf=1, foil=0, etched=0):
    return (name, image, collector_number, nf, foil, etched)


class ScanIngestTests(unittest.TestCase):
    def setUp(self):
        self.conn = MagicMock()

    def _mock_prints(self, rows, *, by_number=None):
        """List-set uses fetchall; number lookup uses fetchone."""
        self.conn.execute.return_value.fetchall.return_value = list(rows)
        self.conn.execute.return_value.fetchone.return_value = by_number

    def test_alchemy_rejected(self):
        with self.assertRaises(ScanError) as ctx:
            ingest_scan(self.conn, set_code="SNC", collector_number="A-12", finish=0)
        self.assertEqual(ctx.exception.status_code, 400)

    @patch("api.services.scan_service._ensure_set_catalog", return_value=True)
    @patch("api.services.scan_service.ensure_card_columns")
    def test_missing_card_after_sync_raises_404(self, _ensure_cols, ensure_catalog):
        self.conn.execute.return_value.fetchall.return_value = []
        self.conn.execute.return_value.fetchone.return_value = None
        with self.assertRaises(ScanError) as ctx:
            ingest_scan(self.conn, set_code="XXX", collector_number="1", finish=0)
        self.assertEqual(ctx.exception.status_code, 404)
        ensure_catalog.assert_called_once_with(self.conn, "XXX")

    @patch("api.services.scan_service.get_copy_state")
    @patch("api.services.scan_service.adjust_copy_count")
    @patch("api.services.scan_service.ensure_card_columns")
    def test_foil_only_clamps_finish(self, _ensure, adjust, get_state):
        row = _row("Sacred Foundry", "279", nf=0, foil=1)
        self._mock_prints([row], by_number=row)
        adjust.return_value = {
            "ownedCount": 1,
            "copies": [{"instanceId": 42}],
        }
        get_state.return_value = {"ownedCount": 1}
        result = ingest_scan(
            self.conn,
            set_code="clu",
            collector_number="279",
            finish=0,
        )
        self.assertEqual(result["finish"], 1)
        self.assertEqual(result["instanceId"], 42)
        self.assertEqual(result["name"], "Sacred Foundry")
        self.assertFalse(result["setImported"])
        self.assertEqual(result["resolveMethod"], "number")
        adjust.assert_called_once()
        kwargs = adjust.call_args.kwargs
        self.assertEqual(kwargs["finish"], 1)
        self.assertEqual(kwargs["delta"], 1)

    @patch("api.services.scan_service.get_copy_state")
    @patch("api.services.scan_service.adjust_copy_count")
    @patch("api.services.scan_service._ensure_set_catalog", return_value=True)
    @patch("api.services.scan_service.ensure_card_columns")
    def test_auto_imports_missing_set_then_adds_copy(
        self,
        _ensure_cols,
        ensure_catalog,
        adjust,
        get_state,
    ):
        found = _row("Lightning Bolt", "161", foil=1)
        cursor = self.conn.execute.return_value
        cursor.fetchall.side_effect = [[], [found]]
        cursor.fetchone.return_value = found
        adjust.return_value = {
            "ownedCount": 1,
            "copies": [{"instanceId": 7}],
        }
        get_state.return_value = {"ownedCount": 1}

        result = ingest_scan(
            self.conn,
            set_code="mh3",
            collector_number="161",
            finish=0,
        )

        ensure_catalog.assert_called_once_with(self.conn, "MH3")
        self.assertTrue(result["setImported"])
        self.assertEqual(result["name"], "Lightning Bolt")
        self.assertEqual(result["instanceId"], 7)
        adjust.assert_called_once()

    @patch("api.services.scan_service.bump_cache_epoch")
    @patch("api.services.scan_service.import_set_catalog_from_scryfall", return_value=12)
    @patch("api.services.scan_service.add_tracked_set")
    @patch("api.services.scan_service.is_set_tracked", return_value=False)
    def test_ensure_set_catalog_tracks_and_imports(
        self,
        _tracked,
        add_tracked,
        import_catalog,
        _bump,
    ):
        from api.services.scan_service import _ensure_set_catalog

        conn = MagicMock()
        self.assertTrue(_ensure_set_catalog(conn, "mh3"))
        add_tracked.assert_called_once()
        import_catalog.assert_called_once()
        conn.commit.assert_called_once()

    def test_titles_likely_match(self):
        self.assertTrue(titles_likely_match("LIGHTNING BOLT", "Lightning Bolt"))
        self.assertTrue(titles_likely_match("", "Lightning Bolt"))
        self.assertFalse(titles_likely_match("Counterspell", "Lightning Bolt"))
        self.assertTrue(titles_likely_match("Lightning Bolt 1R", "Lightning Bolt"))

    def test_strip_trailing_mana_cost(self):
        from api.services.scan_service import strip_trailing_mana_cost, normalize_card_title

        self.assertEqual(strip_trailing_mana_cost("Lightning Bolt 1R"), "Lightning Bolt")
        self.assertEqual(strip_trailing_mana_cost("Counterspell UU"), "Counterspell")
        self.assertEqual(normalize_card_title("Sol Ring 1"), "SOL RING")
        self.assertEqual(
            normalize_card_title(". Bloodthirsty Aerialis -"),
            "BLOODTHIRSTY AERIALIS",
        )

    def test_fuzzy_ocr_title_match(self):
        from api.services.scan_service import name_match_score, titles_likely_match

        self.assertTrue(
            titles_likely_match(". Bloodthirsty Aerialis -", "Bloodthirsty Aerialist")
        )
        self.assertGreater(
            name_match_score(". Bloodthirsty Aerialis -", "Bloodthirsty Aerialist"),
            0.75,
        )

    @patch("api.services.scan_service.get_copy_state")
    @patch("api.services.scan_service.adjust_copy_count")
    @patch("api.services.scan_service.ensure_card_columns")
    def test_name_hint_mismatch_rejects(self, _ensure, adjust, get_state):
        row = _row("Sacred Foundry", "279", nf=0, foil=1)
        self._mock_prints([row], by_number=row)
        with self.assertRaises(ScanError) as ctx:
            ingest_scan(
                self.conn,
                set_code="clu",
                collector_number="279",
                finish=1,
                name_hint="Counterspell",
            )
        self.assertEqual(ctx.exception.status_code, 409)
        adjust.assert_not_called()

    @patch("api.services.scan_service.get_copy_state")
    @patch("api.services.scan_service.adjust_copy_count")
    @patch("api.services.scan_service.ensure_card_columns")
    def test_name_hint_match_allows(self, _ensure, adjust, get_state):
        row = _row("Sacred Foundry", "279", nf=0, foil=1)
        self._mock_prints([row], by_number=row)
        adjust.return_value = {"ownedCount": 1, "copies": [{"instanceId": 9}]}
        get_state.return_value = {"ownedCount": 1}
        result = ingest_scan(
            self.conn,
            set_code="clu",
            collector_number="279",
            finish=1,
            name_hint="Sacred Foundry",
        )
        self.assertEqual(result["instanceId"], 9)
        self.assertEqual(result["resolveMethod"], "name+number")

    @patch("api.services.scan_service.get_copy_state")
    @patch("api.services.scan_service.adjust_copy_count")
    @patch("api.services.scan_service.ensure_card_columns")
    def test_name_and_set_without_number(self, _ensure, adjust, get_state):
        rows = [
            _row("Lightning Bolt", "161", foil=1),
            _row("Counterspell", "48"),
        ]
        self._mock_prints(rows, by_number=None)
        adjust.return_value = {"ownedCount": 1, "copies": [{"instanceId": 3}]}
        get_state.return_value = {"ownedCount": 1}
        result = ingest_scan(
            self.conn,
            set_code="mh3",
            collector_number=None,
            finish=0,
            name_hint="Lightning Bolt",
        )
        self.assertEqual(result["name"], "Lightning Bolt")
        self.assertEqual(result["collectorNumber"], "161")
        self.assertEqual(result["resolveMethod"], "name")
        adjust.assert_called_once()
        self.assertEqual(adjust.call_args.kwargs["collector_number"], "161")

    @patch("api.services.scan_service.ensure_card_columns")
    def test_ambiguous_name_without_number_raises(self, _ensure):
        rows = [
            _row("Lightning Bolt", "1"),
            _row("Lightning Strike", "2"),
        ]
        self._mock_prints(rows, by_number=None)
        with self.assertRaises(ScanError) as ctx:
            ingest_scan(
                self.conn,
                set_code="mh3",
                collector_number=None,
                finish=0,
                name_hint="Lightning",
            )
        self.assertEqual(ctx.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
