import sqlite3
import tempfile
import unittest
from pathlib import Path

import pandas as pd
import runpy

runpy.run_path(str(Path(__file__).resolve().with_name("_paths.py")))

from api.services.deck_generation_service import generate_deck_proposal  # noqa: E402
from api.services.deck_power_service import (  # noqa: E402
    _cards_from_deck_df,
    _deck_needs_metadata_backfill,
    assess_deck_power,
)
from util.card_metadata import (  # noqa: E402
    card_matches_color_identity,
    is_commander_format_legal,
    is_legendary_commander_candidate,
)
from util.card_role_seed import card_has_role, card_roles, load_card_role_seed  # noqa: E402
from util.commander_rules import card_is_legal_for_deck, validate_commander_deck  # noqa: E402
from util.deck_tables import ensure_deck_tables  # noqa: E402
from util.storage_tables import ensure_storage_tables, seed_storage_locations  # noqa: E402
from util.tracked_sets import ensure_tracked_sets_ready  # noqa: E402


class DeckBuilderUnitTests(unittest.TestCase):
    def test_seed_loads(self):
        seed = load_card_role_seed()
        self.assertGreater(len(seed), 50)
        self.assertIn("ramp", card_roles("Sol Ring"))
        self.assertTrue(card_has_role("Demonic Tutor", "tutor"))

    def test_color_identity_subset(self):
        self.assertTrue(card_matches_color_identity(["U", "B"], ["U", "B", "R"]))
        self.assertFalse(card_matches_color_identity(["U", "R"], ["U", "B"]))

    def test_commander_legality(self):
        self.assertTrue(is_commander_format_legal({"commander": "legal"}))
        self.assertFalse(is_commander_format_legal({"commander": "banned"}))

    def test_legendary_commander_candidate(self):
        self.assertTrue(
            is_legendary_commander_candidate("Legendary Creature — Human Wizard"),
        )
        self.assertFalse(is_legendary_commander_candidate("Creature — Human"))

    def test_singleton_validation(self):
        result = validate_commander_deck(
            [
                {"name": "Lightning Bolt", "section": "main", "qty": 2, "card_type": "instant"},
            ],
            commanders=[
                {
                    "name": "Niv-Mizzet",
                    "section": "commander",
                    "type_line": "Legendary Creature — Dragon Wizard",
                    "color_identity": ["U", "R"],
                },
            ],
        )
        self.assertFalse(result["valid"])
        self.assertTrue(any("Singleton" in error for error in result["errors"]))

    def test_color_identity_filter(self):
        card = {
            "name": "Counterspell",
            "color_identity": ["U"],
            "legalities": {"commander": "legal"},
        }
        self.assertTrue(card_is_legal_for_deck(card, ["U", "R"]))
        self.assertFalse(card_is_legal_for_deck(card, ["R", "G"]))

    def test_assess_power_returns_bracket_and_components(self):
        cards = [
            {"name": "Sol Ring", "section": "main", "qty": 1, "cmc": 1, "card_type": "artifact"},
            {"name": "Rhystic Study", "section": "main", "qty": 1, "cmc": 3, "card_type": "enchantment"},
            {"name": "Cultivate", "section": "main", "qty": 1, "cmc": 3, "card_type": "sorcery"},
            {"name": "Island", "section": "main", "qty": 10, "cmc": 0, "card_type": "land", "is_basic_land": True},
        ]
        result = assess_deck_power(cards, commanders=[])
        self.assertIn("bracket", result)
        self.assertIn("components", result)
        self.assertIn("ramp", result["components"])
        self.assertGreaterEqual(result["bracket"], 1)
        self.assertEqual(result["counts"]["tutors"], 0)
        self.assertEqual(result["components"]["tutors"], 0)
        self.assertEqual(result["counts"]["fastMana"], 1)
        self.assertGreater(result["components"]["fastMana"], 0)
        self.assertEqual(result["counts"]["gameChangers"], 1)
        self.assertIn("categoryCards", result)
        self.assertEqual(result["categoryCards"]["tutors"], [])
        ramp_names = [card["cardName"] for card in result["categoryCards"]["ramp"]]
        self.assertIn("Sol Ring", ramp_names)
        self.assertIn("Sol Ring", [card["cardName"] for card in result["categoryCards"]["fastMana"]])
        self.assertEqual(result["powerSignal"], 9.0)
        self.assertEqual(result["bracket"], 2)
        self.assertTrue(any("avg cmc 2.3" in item for item in result["highlights"]))

    def test_casual_deck_without_staples_is_low_bracket(self):
        cards = [
            {"name": f"Generic Card {index}", "section": "main", "qty": 1, "cmc": 3, "card_type": "creature"}
            for index in range(60)
        ]
        result = assess_deck_power(cards, commanders=[])
        self.assertEqual(result["powerSignal"], 0.0)
        self.assertEqual(result["bracket"], 1)

    def test_power_categories_score_zero_without_staples(self):
        cards = [
            {"name": "Grizzly Bears", "section": "main", "qty": 1, "cmc": 2, "card_type": "creature"},
            {"name": "Forest", "section": "main", "qty": 10, "cmc": 0, "card_type": "land", "is_basic_land": True},
        ]
        result = assess_deck_power(cards, commanders=[])
        self.assertEqual(result["components"]["tutors"], 0)
        self.assertEqual(result["components"]["fastMana"], 0)
        self.assertEqual(result["components"]["gameChangers"], 0)
        self.assertEqual(result["components"]["comboDensity"], 0)
        self.assertEqual(result["bracket"], 1)

    def test_mana_cost_fallback_for_average_cmc(self):
        from util.card_metadata import cmc_from_mana_cost, resolve_card_cmc

        self.assertEqual(cmc_from_mana_cost("{2}{U}{U}"), 4.0)
        self.assertEqual(
            resolve_card_cmc({
                "mana_cost": "{1}{G}",
                "card_type": "sorcery",
            }),
            2.0,
        )
        cards = [
            {
                "name": "Brainstorm",
                "section": "main",
                "qty": 1,
                "mana_cost": "{U}",
                "card_type": "instant",
            },
            {
                "name": "Grizzly Bears",
                "section": "main",
                "qty": 1,
                "mana_cost": "{1}{G}",
                "card_type": "creature",
            },
        ]
        result = assess_deck_power(cards, commanders=[])
        self.assertTrue(any("avg cmc 1.5" in item for item in result["highlights"]))

    def test_deck_needs_metadata_backfill_when_cmc_missing(self):
        deck_df = pd.DataFrame([
            {
                "section": "main",
                "in_catalog": 1,
                "set_code": "40K",
                "collector_number": "249",
                "cmc": None,
                "mana_cost": None,
            },
            {
                "section": "main",
                "in_catalog": 1,
                "set_code": "40K",
                "collector_number": "1",
                "cmc": 3.0,
                "mana_cost": "{2}{W}",
            },
        ])
        self.assertTrue(_deck_needs_metadata_backfill(deck_df))

        complete_df = pd.DataFrame([
            {
                "section": "main",
                "in_catalog": 1,
                "set_code": "40K",
                "collector_number": "1",
                "cmc": 3.0,
                "mana_cost": "{2}{W}",
            },
        ])
        self.assertFalse(_deck_needs_metadata_backfill(complete_df))

    def test_basic_land_does_not_trigger_metadata_backfill(self):
        deck_df = pd.DataFrame([
            {
                "section": "main",
                "in_catalog": 1,
                "set_code": "40K",
                "collector_number": "312",
                "cmc": 0.0,
                "mana_cost": None,
                "card_type": "land",
                "is_basic_land": 1,
            },
            {
                "section": "main",
                "in_catalog": 1,
                "set_code": "40K",
                "collector_number": "249",
                "cmc": 1.0,
                "mana_cost": "{1}",
                "card_type": "artifact",
            },
        ])
        self.assertFalse(_deck_needs_metadata_backfill(deck_df))

    def test_cards_from_deck_df_handles_nan_basic_land(self):
        deck_df = pd.DataFrame([
            {
                "section": "main",
                "card_name": "Nekusar, the Mindrazer",
                "set_code": "VMA",
                "collector_number": "1",
                "finish": 0,
                "qty": 1,
                "cmc": 5.0,
                "mana_cost": "{3}{U}{B}{R}",
                "card_type": "creature",
                "is_basic_land": float("nan"),
                "type_line": "Legendary Creature — Zombie Wizard",
                "image_uri": "https://example.com/card.jpg",
            },
        ])
        cards, commanders = _cards_from_deck_df(deck_df)
        self.assertEqual(len(cards), 1)
        self.assertFalse(cards[0]["is_basic_land"])
        self.assertEqual(cards[0]["cmc"], 5.0)


class DeckBuilderIntegrationTests(unittest.TestCase):
    def _seed_card(self, set_code, collector_number, name, **fields):
        self.conn.execute(
            """
            INSERT INTO cards (
                id, set_code, collector_number, name, art_style,
                market_value, market_value_foil, market_value_etched,
                has_nonfoil, has_foil, has_etched, image_uri, cardmarket_url,
                colors, type_line, card_type, color_identity, oracle_text,
                mana_cost, cmc, legalities, is_basic_land
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 0, 0, NULL, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"{set_code}-{collector_number}",
                set_code,
                collector_number,
                name,
                None,
                fields.get("market_value"),
                None,
                None,
                fields.get("colors", "[]"),
                fields.get("type_line", ""),
                fields.get("card_type", ""),
                fields.get("color_identity", "[]"),
                fields.get("oracle_text", ""),
                fields.get("mana_cost", ""),
                fields.get("cmc", 0),
                fields.get("legalities", '{"commander":"legal"}'),
                fields.get("is_basic_land", 0),
            ),
        )

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        ensure_storage_tables(self.conn)
        ensure_deck_tables(self.conn)
        ensure_tracked_sets_ready(self.conn)
        seed_storage_locations(self.conn)
        self.conn.executescript(
            """
            CREATE TABLE cards (
                id TEXT PRIMARY KEY,
                set_code TEXT NOT NULL,
                collector_number TEXT NOT NULL,
                name TEXT NOT NULL,
                art_style TEXT,
                market_value REAL,
                market_value_foil REAL,
                market_value_etched REAL,
                has_nonfoil INTEGER,
                has_foil INTEGER,
                has_etched INTEGER,
                image_uri TEXT,
                cardmarket_url TEXT,
                colors TEXT,
                type_line TEXT,
                card_type TEXT,
                color_identity TEXT,
                oracle_text TEXT,
                mana_cost TEXT,
                cmc REAL,
                legalities TEXT,
                is_basic_land INTEGER
            );
            """
        )
        self._seed_card(
            "LTR", "1", "Aragorn, King of Gondor",
            type_line="Legendary Creature — Human Noble",
            color_identity='["W","R","G"]',
            oracle_text="Vigilance. Whenever you attack, create a Human Soldier token.",
            cmc=5,
            card_type="creature",
        )
        self._seed_card(
            "LTR", "2", "Sol Ring",
            type_line="Artifact",
            color_identity="[]",
            oracle_text="{T}: Add {C}{C}.",
            cmc=1,
            card_type="artifact",
            market_value=2.0,
        )
        self._seed_card(
            "LTR", "3", "Cultivate",
            type_line="Sorcery",
            color_identity='["G"]',
            oracle_text="Search your library for up to two basic land cards.",
            cmc=3,
            card_type="sorcery",
            market_value=1.0,
        )
        self._seed_card(
            "LTR", "4", "Forest",
            type_line="Basic Land — Forest",
            color_identity='["G"]',
            cmc=0,
            card_type="land",
            is_basic_land=1,
        )
        self.conn.execute(
            "INSERT INTO tracked_sets (set_code, created_at) VALUES ('LTR', '2026-01-01T00:00:00Z')",
        )
        self.conn.execute(
            """
            INSERT INTO card_instances (set_code, collector_number, finish, location_slug, purchase_value)
            VALUES ('LTR', '1', 0, 'storage:general', 5),
                   ('LTR', '2', 0, 'storage:general', 2),
                   ('LTR', '3', 0, 'storage:general', 1)
            """,
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        self.temp_dir.cleanup()

    def test_generate_deck_prefers_owned_cards(self):
        proposal = generate_deck_proposal(
            self.conn,
            commanders=[{"setCode": "LTR", "collectorNumber": "1", "finish": 0}],
            location_slugs=["storage:general"],
            land_count=36,
        )
        names = {card["name"] for card in proposal["cards"]}
        self.assertIn("Sol Ring", names)
        self.assertIn("Cultivate", names)
        self.assertGreaterEqual(proposal["stats"]["ownedCount"], 2)
        self.assertEqual(proposal["stats"]["basicLandCount"], 36)
        self.assertGreaterEqual(proposal["stats"]["totalCards"], 36)
        owned_cards = [card for card in proposal["cards"] if not card.get("suggested")]
        self.assertTrue(any(card["name"] == "Sol Ring" for card in owned_cards))

    def test_generate_deck_assumes_infinite_basic_lands(self):
        proposal = generate_deck_proposal(
            self.conn,
            commanders=[{"setCode": "LTR", "collectorNumber": "1", "finish": 0}],
            location_slugs=["storage:general"],
            land_count=38,
        )
        basics = [card for card in proposal["cards"] if card.get("infiniteBasic")]
        self.assertTrue(basics)
        self.assertEqual(
            sum(int(card.get("qty") or 1) for card in basics),
            38,
        )
        self.assertTrue(all(not card.get("suggested") for card in basics))
        self.assertTrue(all(card.get("isBasicLand") for card in basics))
        self.assertEqual(proposal["stats"]["basicLandCount"], 38)
        self.assertGreaterEqual(proposal["stats"]["totalCards"], 38)
        self.assertNotIn("Forest", {card["name"] for card in proposal["cards"] if card.get("suggested")})


if __name__ == "__main__":
    unittest.main()
