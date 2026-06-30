import math
import sys
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from report.serialize_helpers import (  # noqa: E402
    deck_card_display_name,
    sanitize_json_payload,
    str_or_empty,
)


class SerializeHelperTests(unittest.TestCase):
    def test_str_or_empty_handles_nan(self):
        self.assertEqual(str_or_empty(float("nan")), "")
        self.assertEqual(str_or_empty(None), "")
        self.assertEqual(str_or_empty("  Sol Ring  "), "Sol Ring")

    def test_deck_card_display_name_prefers_catalog_then_csv(self):
        row = pd.Series(
            {
                "catalog_name": float("nan"),
                "card_name": "MB1 #136",
                "set_code": "MB1",
                "collector_number": "136",
            }
        )
        self.assertEqual(deck_card_display_name(row), "MB1 #136")

    def test_deck_card_display_name_falls_back_to_print(self):
        row = pd.Series(
            {
                "catalog_name": float("nan"),
                "card_name": float("nan"),
                "set_code": "PLIST",
                "collector_number": "71",
            }
        )
        self.assertEqual(deck_card_display_name(row), "PLIST #71")

    def test_sanitize_json_payload_replaces_nan_with_null(self):
        payload = {"catalog_name": float("nan"), "qty": 1, "nested": [float("inf")]}
        sanitized = sanitize_json_payload(payload)
        self.assertIsNone(sanitized["catalog_name"])
        self.assertEqual(sanitized["qty"], 1)
        self.assertIsNone(sanitized["nested"][0])


if __name__ == "__main__":
    unittest.main()
