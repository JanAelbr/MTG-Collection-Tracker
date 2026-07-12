import unittest

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from util.card_metadata import (  # noqa: E402
    card_metadata_api,
    card_metadata_snake,
    card_types_from_type_line,
    encode_card_colors,
    parse_card_colors,
    primary_card_type,
)
from util.scryfall_card import (  # noqa: E402
    card_colors,
    card_colors_json,
    card_primary_type,
    card_type_line,
)


class CardMetadataTests(unittest.TestCase):
    def test_card_colors_from_scryfall(self):
        card = {
            "colors": ["U", "R"],
            "type_line": "Instant",
        }
        self.assertEqual(card_colors(card), ["U", "R"])
        self.assertEqual(card_colors_json(card), '["U","R"]')
        self.assertEqual(card_primary_type(card), "instant")

    def test_card_colors_from_double_faced_card(self):
        card = {
            "colors": [],
            "card_faces": [
                {"colors": ["G"], "type_line": "Creature — Elf"},
                {"colors": ["G"], "type_line": "Enchantment — Aura"},
            ],
        }
        self.assertEqual(card_colors(card), ["G"])
        self.assertEqual(
            card_type_line({
                "card_faces": [
                    {"type_line": "Creature — Elf"},
                    {"type_line": "Enchantment — Aura"},
                ],
            }),
            "Creature — Elf // Enchantment — Aura",
        )

    def test_parse_card_colors_from_json(self):
        self.assertEqual(parse_card_colors('["W","U"]'), ["W", "U"])

    def test_parse_card_colors_from_list(self):
        self.assertEqual(parse_card_colors(["U", "R"]), ["U", "R"])

    def test_card_metadata_api_accepts_parsed_colors(self):
        row = {
            "colors": ["G", "U"],
            "type_line": "Instant",
            "card_type": "instant",
        }
        self.assertEqual(card_metadata_api(row)["colors"], ["U", "G"])

    def test_card_types_from_type_line(self):
        self.assertEqual(
            card_types_from_type_line("Legendary Artifact Creature — Golem"),
            ["artifact", "creature"],
        )
        self.assertEqual(primary_card_type("Basic Land — Forest"), "land")
        self.assertEqual(primary_card_type("Artifact Creature — Construct"), "creature")
        self.assertEqual(primary_card_type("Land Creature — Forest Dryad"), "land")

    def test_card_metadata_snake_handles_nan_basic_land(self):
        import pandas as pd

        row = pd.Series({
            "colors": '["G"]',
            "type_line": "Creature — Elf",
            "card_type": "creature",
            "is_basic_land": float("nan"),
            "cmc": float("nan"),
        })
        meta = card_metadata_snake(row)
        self.assertFalse(meta["is_basic_land"])
        self.assertEqual(meta["cmc"], 0.0)

    def test_card_metadata_api_fields(self):
        row = {
            "colors": '["B"]',
            "type_line": "Creature — Human Wizard",
            "card_type": "creature",
        }
        api_meta = card_metadata_api(row)
        self.assertEqual(api_meta["colors"], ["B"])
        self.assertEqual(api_meta["typeLine"], "Creature — Human Wizard")
        self.assertEqual(api_meta["cardType"], "creature")
        self.assertEqual(api_meta["cardTypes"], ["creature"])
        meta = card_metadata_snake(row)
        self.assertEqual(meta["colors"], ["B"])
        self.assertEqual(meta["type_line"], "Creature — Human Wizard")
        self.assertEqual(meta["card_type"], "creature")
        self.assertEqual(meta["card_types"], ["creature"])
        self.assertFalse(meta["is_basic_land"])


if __name__ == "__main__":
    unittest.main()
