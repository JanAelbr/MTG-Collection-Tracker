"""Tests for commander theme profiling and synergy scoring."""

import unittest
from pathlib import Path

import runpy

runpy.run_path(str(Path(__file__).resolve().with_name("_paths.py")))

from util.commander_themes import (  # noqa: E402
    build_commander_theme_profile,
    card_theme_hits,
    synergy_score_for_slot,
    theme_density,
)


class CommanderThemeTests(unittest.TestCase):
    def test_tribal_elf_profile(self):
        profile = build_commander_theme_profile(
            [
                {
                    "name": "Lathril, Blade of the Elves",
                    "typeLine": "Legendary Creature — Elf Noble",
                    "oracleText": (
                        "Menace. Whenever Lathril deals combat damage, create that many 1/1 "
                        "green Elf Warrior creature tokens. {2}{G/B}, tap X untapped Elves: "
                        "each opponent loses X life."
                    ),
                }
            ]
        )
        tribal_ids = {row["id"] for row in profile["tribal"]}
        self.assertIn("elf", tribal_ids)
        primary_ids = {row["id"] for row in profile["primary"]}
        self.assertTrue("tokens" in primary_ids or "tribal:elf" in primary_ids)
        self.assertTrue(any(need.startswith("token") or need.startswith("tribal") for need in profile["needs"]))

    def test_on_theme_beats_off_theme_in_synergy_slot(self):
        profile = build_commander_theme_profile(
            [
                {
                    "name": "Elf Lord",
                    "typeLine": "Legendary Creature — Elf Warrior",
                    "oracleText": "Other Elves you control get +1/+1. Create a 1/1 Elf token.",
                }
            ]
        )
        elf = {
            "name": "Elvish Mystic",
            "typeLine": "Creature — Elf Druid",
            "oracleText": "{T}: Add {G}.",
            "cardType": "creature",
        }
        bolt = {
            "name": "Lightning Bolt",
            "typeLine": "Instant",
            "oracleText": "Lightning Bolt deals 3 damage to any target.",
            "cardType": "instant",
        }
        elf_score = synergy_score_for_slot(elf, profile, slot="synergy")
        bolt_score = synergy_score_for_slot(bolt, profile, slot="synergy")
        self.assertGreater(elf_score, bolt_score)
        self.assertFalse(card_theme_hits(elf, profile)["offTheme"])

    def test_theme_density(self):
        profile = build_commander_theme_profile(
            [
                {
                    "name": "Zombie King",
                    "typeLine": "Legendary Creature — Zombie",
                    "oracleText": "Whenever a Zombie dies, create a 2/2 black Zombie token.",
                }
            ]
        )
        cards = [
            {
                "name": "Walking Corpse",
                "typeLine": "Creature — Zombie",
                "oracleText": "",
                "cardType": "creature",
                "qty": 1,
            },
            {
                "name": "Shock",
                "typeLine": "Instant",
                "oracleText": "Shock deals 2 damage to any target.",
                "cardType": "instant",
                "qty": 1,
            },
        ]
        density = theme_density(cards, profile)
        self.assertGreater(density, 0)
        self.assertLessEqual(density, 1)


if __name__ == "__main__":
    unittest.main()
