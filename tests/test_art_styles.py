import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from lib.art_styles import (  # noqa: E402
    DEFAULT_ART_STYLE_NAME,
    get_art_style,
    save_art_style_rules,
    validate_art_style_rules,
)
from util.schema import ensure_database_schema  # noqa: E402


class ArtStyleTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        ensure_database_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_40k_borderless_commander(self):
        self.assertEqual(get_art_style(self.conn, "40k", "1"), "01. Borderless commanders")

    def test_40k_surge_foil_matches_numeric_range(self):
        self.assertEqual(get_art_style(self.conn, "40k", "249"), "04. Reprints")
        self.assertEqual(get_art_style(self.conn, "40k", "249★"), "04. Reprints")

    def test_snc_alchemy_promo_prefix(self):
        self.assertEqual(get_art_style(self.conn, "snc", "A-6"), "06. Alchemy promos")
        self.assertEqual(get_art_style(self.conn, "snc", "6"), "01. Main set")

    def test_ltr_release_promo_and_serialized_poster(self):
        self.assertEqual(get_art_style(self.conn, "ltr", "0"), "00. Release promo")
        self.assertEqual(get_art_style(self.conn, "ltr", "731"), "14. Borderless poster")
        self.assertEqual(get_art_style(self.conn, "ltr", "731z"), "14z. Borderless poster: serialized")
        self.assertEqual(get_art_style(self.conn, "ltr", "A-246"), "17. Alchemy promos")

    def test_clb_main_and_commander_sections(self):
        self.assertEqual(get_art_style(self.conn, "clb", "100"), "01. Main set")
        self.assertEqual(get_art_style(self.conn, "clb", "400"), "03. Rulebook Art")
        self.assertEqual(get_art_style(self.conn, "clb", "620"), "07. Borderless Commander Exclusives")
        self.assertEqual(get_art_style(self.conn, "clb", "650"), "08. Commander decks")
        self.assertEqual(get_art_style(self.conn, "clb", "900"), "09. Commander deck reprints")

    def test_missing_rules_defaults_to_all(self):
        self.assertEqual(get_art_style(self.conn, "abc", "1"), DEFAULT_ART_STYLE_NAME)
        self.assertEqual(get_art_style(self.conn, "abc", "promo"), DEFAULT_ART_STYLE_NAME)
        self.assertEqual(get_art_style(self.conn, "abc", "A-1"), DEFAULT_ART_STYLE_NAME)

    def test_save_and_normalize_rules(self):
        saved = save_art_style_rules(
            self.conn,
            "ltr",
            [
                {"name": "Main set", "firstNumber": 1, "lastNumber": 10},
                {"name": "Alchemy", "prefix": "A-"},
            ],
        )
        self.assertEqual(len(saved), 2)
        self.assertEqual(get_art_style(self.conn, "ltr", "5"), "Main set")
        self.assertEqual(get_art_style(self.conn, "ltr", "A-5"), "Alchemy")

    def test_validate_rules_rejects_empty_name(self):
        errors = validate_art_style_rules([{"firstNumber": 1, "lastNumber": 2}])
        self.assertTrue(errors)

    def test_mh3_main_and_booster_fun_sections(self):
        self.assertEqual(get_art_style(self.conn, "mh3", "100"), "01. Main set")
        self.assertEqual(get_art_style(self.conn, "mh3", "280"), "02. Bonus sheet")
        self.assertEqual(get_art_style(self.conn, "mh3", "305"), "03. Full-art Eldrazi basics")
        self.assertEqual(get_art_style(self.conn, "mh3", "330"), "05. Frame break")
        self.assertEqual(get_art_style(self.conn, "mh3", "400"), "09. Retro frame")
        self.assertEqual(get_art_style(self.conn, "mh3", "450"), "11. Extended art")
        self.assertEqual(get_art_style(self.conn, "mh3", "510"), "16. Ripple foil")

    def test_mh3_serialized_eldrazi_titans(self):
        self.assertEqual(get_art_style(self.conn, "mh3", "382"), "08. Borderless concept Eldrazi")
        self.assertEqual(get_art_style(self.conn, "mh3", "382z"), "08z. Borderless concept Eldrazi: serialized")

    def test_2x2_main_borderless_etched_and_promos(self):
        self.assertEqual(get_art_style(self.conn, "2x2", "79"), "01. Main set")
        self.assertEqual(get_art_style(self.conn, "2x2", "332"), "01. Main set")
        self.assertEqual(get_art_style(self.conn, "2x2", "333"), "02. Borderless planeswalkers")
        self.assertEqual(get_art_style(self.conn, "2x2", "335"), "03. Borderless")
        self.assertEqual(get_art_style(self.conn, "2x2", "412"), "03. Borderless")
        self.assertEqual(get_art_style(self.conn, "2x2", "413"), "04. Foil etched")
        self.assertEqual(get_art_style(self.conn, "2x2", "572"), "04. Foil etched")
        self.assertEqual(get_art_style(self.conn, "2x2", "573"), "05. Textured foil")
        self.assertEqual(get_art_style(self.conn, "2x2", "578"), "06. Promos")

    def test_tdm_main_showcases_and_promos(self):
        self.assertEqual(get_art_style(self.conn, "tdm", "100"), "01. Main set")
        self.assertEqual(get_art_style(self.conn, "tdm", "291"), "01. Main set")
        self.assertEqual(get_art_style(self.conn, "tdm", "292"), "02. Draconic showcases")
        self.assertEqual(get_art_style(self.conn, "tdm", "327"), "03. Borderless clan showcases")
        self.assertEqual(get_art_style(self.conn, "tdm", "377"), "04. Reversible dragons")
        self.assertEqual(get_art_style(self.conn, "tdm", "383"), "05. Borderless alternate art")
        self.assertEqual(get_art_style(self.conn, "tdm", "399"), "06. Ghostfire showcases")
        self.assertEqual(get_art_style(self.conn, "tdm", "409"), "07. Halo foil ghostfire")
        self.assertEqual(get_art_style(self.conn, "tdm", "419"), "08. Serialized headliner")
        self.assertEqual(get_art_style(self.conn, "tdm", "420"), "09. Promo pack")
        self.assertEqual(get_art_style(self.conn, "tdm", "425"), "10. Bundle promo")
        self.assertEqual(get_art_style(self.conn, "tdm", "426"), "11. Buy-a-Box")
        self.assertEqual(get_art_style(self.conn, "tdm", "A-103"), "12. Alchemy promos")

    def test_afr_main_showcases_and_promos(self):
        self.assertEqual(get_art_style(self.conn, "afr", "100"), "01. Main set")
        self.assertEqual(get_art_style(self.conn, "afr", "281"), "01. Main set")
        self.assertEqual(get_art_style(self.conn, "afr", "282"), "02. Borderless planeswalkers")
        self.assertEqual(get_art_style(self.conn, "afr", "287"), "03. Borderless dragons")
        self.assertEqual(get_art_style(self.conn, "afr", "298"), "03. Borderless dragons")
        self.assertEqual(get_art_style(self.conn, "afr", "299"), "04. Showcase")
        self.assertEqual(get_art_style(self.conn, "afr", "358"), "04. Showcase")
        self.assertEqual(get_art_style(self.conn, "afr", "359"), "05. Extended art")
        self.assertEqual(get_art_style(self.conn, "afr", "396"), "06. Buy-a-Box")
        self.assertEqual(get_art_style(self.conn, "afr", "397"), "07. Bundle promo")
        self.assertEqual(get_art_style(self.conn, "afr", "402"), "08. Promo pack")
        self.assertEqual(get_art_style(self.conn, "afr", "A-87"), "09. Alchemy promos")


if __name__ == "__main__":
    unittest.main()
