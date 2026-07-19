import unittest
from pathlib import Path

import runpy

runpy.run_path(str(Path(__file__).resolve().with_name("_paths.py")))

from util.card_role_infer import infer_card_roles  # noqa: E402
from util.card_role_seed import (  # noqa: E402
    card_bracket_weight,
    card_roles,
    card_roles_for,
)


class CardRoleInferTests(unittest.TestCase):
    def test_cultivate_is_ramp_not_tutor(self):
        card = {
            "name": "Cultivate",
            "type_line": "Sorcery",
            "oracle_text": (
                "Search your library for up to two basic land cards, reveal those cards, "
                "put one onto the battlefield tapped and the other into your hand, then shuffle."
            ),
        }
        roles = set(infer_card_roles(card))
        self.assertIn("ramp", roles)
        self.assertNotIn("tutor", roles)

    def test_sol_ring_is_ramp(self):
        card = {
            "name": "Sol Ring",
            "type_line": "Artifact",
            "oracle_text": "{T}: Add {C}{C}.",
        }
        self.assertIn("ramp", infer_card_roles(card))

    def test_demonic_tutor_is_tutor(self):
        card = {
            "name": "Demonic Tutor",
            "type_line": "Sorcery",
            "oracle_text": "Search your library for a card, put that card into your hand, then shuffle.",
        }
        self.assertIn("tutor", infer_card_roles(card))

    def test_draw_effects(self):
        rhystic = {
            "name": "Rhystic Study",
            "type_line": "Enchantment",
            "oracle_text": (
                "Whenever an opponent casts a spell, you may draw a card unless that "
                "player pays {1}."
            ),
        }
        whisper = {
            "name": "Night's Whisper",
            "type_line": "Sorcery",
            "oracle_text": "You draw two cards and you lose 2 life.",
        }
        self.assertIn("draw", infer_card_roles(rhystic))
        self.assertIn("draw", infer_card_roles(whisper))

    def test_removal_and_counterspell(self):
        swords = {
            "name": "Swords to Plowshares",
            "type_line": "Instant",
            "oracle_text": "Exile target creature. Its controller gains life equal to its power.",
        }
        counter = {
            "name": "Counterspell",
            "type_line": "Instant",
            "oracle_text": "Counter target spell.",
        }
        swords_roles = set(infer_card_roles(swords))
        counter_roles = set(infer_card_roles(counter))
        self.assertIn("removal", swords_roles)
        self.assertIn("interaction", swords_roles)
        self.assertIn("protection", counter_roles)
        self.assertIn("interaction", counter_roles)

    def test_extra_turn_and_mld(self):
        time_warp = {
            "name": "Time Warp",
            "type_line": "Sorcery",
            "oracle_text": "Target player takes an extra turn after this one.",
        }
        armageddon = {
            "name": "Armageddon",
            "type_line": "Sorcery",
            "oracle_text": "Destroy all lands.",
        }
        self.assertIn("extra_turn", infer_card_roles(time_warp))
        self.assertIn("mass_land_destruction", infer_card_roles(armageddon))
        self.assertNotIn("removal", infer_card_roles(armageddon))

    def test_bojuka_bog_land_and_graveyard_hate(self):
        card = {
            "name": "Bojuka Bog",
            "type_line": "Land",
            "oracle_text": (
                "Bojuka Bog enters tapped.\n"
                "{T}: Add {B}.\n"
                "When Bojuka Bog enters, exile all cards from target player's graveyard."
            ),
        }
        roles = set(infer_card_roles(card))
        self.assertIn("land", roles)
        self.assertIn("graveyard_hate", roles)
        self.assertNotIn("ramp", roles)

    def test_seed_merges_fast_mana_and_weight(self):
        card = {
            "name": "Sol Ring",
            "type_line": "Artifact",
            "oracle_text": "{T}: Add {C}{C}.",
        }
        roles = set(card_roles_for(card))
        self.assertIn("ramp", roles)
        self.assertIn("fast_mana", roles)
        self.assertEqual(card_bracket_weight("Sol Ring"), 4)

    def test_suppress_removes_inferred_role(self):
        from unittest.mock import patch

        from util import card_role_seed as seed_mod

        card = {
            "name": "Fake Draw",
            "type_line": "Sorcery",
            "oracle_text": "Draw two cards.",
        }
        fake_seed = {
            "Fake Draw": {"roles": [], "suppress": ["draw"], "bracketWeight": 1},
        }
        with patch.object(seed_mod, "load_card_role_seed", return_value=fake_seed):
            self.assertNotIn("draw", card_roles_for(card))

    def test_name_only_lookup_is_seed_only(self):
        self.assertIn("fast_mana", card_roles("Sol Ring"))
        self.assertNotIn("ramp", card_roles("Sol Ring"))


if __name__ == "__main__":
    unittest.main()
