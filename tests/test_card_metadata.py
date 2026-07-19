import sqlite3
import unittest

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from util.card_metadata import (  # noqa: E402
    card_image_fields,
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
    card_image_uri,
    card_image_uri_back,
    card_image_uri_for_face,
    card_power,
    card_primary_type,
    card_rarity,
    card_toughness,
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
            "oracle_text": "Draw a card.",
            "mana_cost": "{2}{U}",
            "cmc": 3.0,
            "power": "2",
            "toughness": "3",
            "rarity": "rare",
        }
        api_meta = card_metadata_api(row)
        self.assertEqual(api_meta["colors"], ["B"])
        self.assertEqual(api_meta["typeLine"], "Creature — Human Wizard")
        self.assertEqual(api_meta["cardType"], "creature")
        self.assertEqual(api_meta["cardTypes"], ["creature"])
        self.assertEqual(api_meta["oracleText"], "Draw a card.")
        self.assertEqual(api_meta["manaCost"], "{2}{U}")
        self.assertEqual(api_meta["cmc"], 3.0)
        self.assertEqual(api_meta["power"], "2")
        self.assertEqual(api_meta["toughness"], "3")
        self.assertEqual(api_meta["rarity"], "rare")
        meta = card_metadata_snake(row)
        self.assertEqual(meta["colors"], ["B"])
        self.assertEqual(meta["type_line"], "Creature — Human Wizard")
        self.assertEqual(meta["card_type"], "creature")
        self.assertEqual(meta["card_types"], ["creature"])
        self.assertFalse(meta["is_basic_land"])

    def test_scryfall_card_detail_extractors(self):
        creature = {
            "power": "4",
            "toughness": "4",
            "rarity": "Mythic",
        }
        self.assertEqual(card_power(creature), "4")
        self.assertEqual(card_toughness(creature), "4")
        self.assertEqual(card_rarity(creature), "mythic")

        double_faced = {
            "card_faces": [
                {"power": "2", "toughness": "1"},
                {"power": "3", "toughness": "3"},
            ],
        }
        self.assertEqual(card_power(double_faced), "2")
        self.assertEqual(card_toughness(double_faced), "1")

    def test_card_image_fields(self):
        row = {
            "image_uri": "https://example.com/front.jpg",
            "image_uri_back": "https://example.com/back.jpg",
        }
        self.assertEqual(
            card_image_fields(row),
            {
                "imageUri": "https://example.com/front.jpg",
                "imageUriBack": "https://example.com/back.jpg",
            },
        )

    def test_card_image_fields_from_sqlite_row(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute(
            "CREATE TABLE cards (image_uri TEXT, image_uri_back TEXT)"
        )
        conn.execute(
            "INSERT INTO cards VALUES (?, ?)",
            ("https://example.com/front.jpg", "https://example.com/back.jpg"),
        )
        row = conn.execute("SELECT image_uri, image_uri_back FROM cards").fetchone()
        conn.close()
        self.assertEqual(
            card_image_fields(row),
            {
                "imageUri": "https://example.com/front.jpg",
                "imageUriBack": "https://example.com/back.jpg",
            },
        )

    def test_card_image_uri_for_double_faced_card(self):
        single_faced = {
            "image_uris": {"normal": "https://example.com/front.jpg"},
        }
        self.assertEqual(card_image_uri(single_faced), "https://example.com/front.jpg")
        self.assertIsNone(card_image_uri_back(single_faced))

        double_faced = {
            "card_faces": [
                {"image_uris": {"normal": "https://example.com/day.jpg"}},
                {"image_uris": {"normal": "https://example.com/night.jpg"}},
            ],
        }
        self.assertEqual(card_image_uri_for_face(double_faced, 0), "https://example.com/day.jpg")
        self.assertEqual(card_image_uri_for_face(double_faced, 1), "https://example.com/night.jpg")
        self.assertEqual(card_image_uri(double_faced), "https://example.com/day.jpg")
        self.assertEqual(card_image_uri_back(double_faced), "https://example.com/night.jpg")

        adventure = {
            "image_uris": {"normal": "https://example.com/adventure.jpg"},
            "card_faces": [
                {"name": "Creature Face"},
                {"name": "Adventure Face"},
            ],
        }
        self.assertEqual(card_image_uri(adventure), "https://example.com/adventure.jpg")
        self.assertIsNone(card_image_uri_back(adventure))


if __name__ == "__main__":
    unittest.main()
