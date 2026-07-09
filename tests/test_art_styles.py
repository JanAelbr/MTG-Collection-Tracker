import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from lib.art_styles import (  # noqa: E402
    DEFAULT_ART_STYLE_NAME,
    ensure_art_style_rules_file,
    get_art_style,
    save_art_style_rules,
    validate_art_style_rules,
)


class ArtStyleTests(unittest.TestCase):
    def test_40k_borderless_commander(self):
        self.assertEqual(get_art_style("40k", "1"), "01. Borderless commanders")

    def test_40k_surge_foil_matches_numeric_range(self):
        self.assertEqual(get_art_style("40k", "249"), "04. Reprints")
        self.assertEqual(get_art_style("40k", "249★"), "04. Reprints")

    def test_snc_alchemy_promo_prefix(self):
        self.assertEqual(get_art_style("snc", "A-6"), "06. Alchemy promos")
        self.assertEqual(get_art_style("snc", "6"), "01. Main set")

    def test_ltr_release_promo_and_serialized_poster(self):
        self.assertEqual(get_art_style("ltr", "0"), "00. Release promo")
        self.assertEqual(get_art_style("ltr", "731"), "14. Borderless poster")
        self.assertEqual(get_art_style("ltr", "731z"), "14z. Borderless poster: serialized")
        self.assertEqual(get_art_style("ltr", "A-246"), "17. Alchemy promos")

    def test_clb_main_and_commander_sections(self):
        self.assertEqual(get_art_style("clb", "100"), "01. Main set")
        self.assertEqual(get_art_style("clb", "400"), "02. Extended art")
        self.assertEqual(get_art_style("clb", "640"), "03. Commander deck cards")
        self.assertEqual(get_art_style("clb", "900"), "04. Commander deck lands")

    def test_missing_rules_file_defaults_to_all(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        art_styles_dir = Path(temp_dir.name) / "art_styles"
        art_styles_dir.mkdir()

        with (
            patch("lib.art_styles.ART_STYLES_DIR", art_styles_dir),
            patch("lib.config.ART_STYLES_DIR", art_styles_dir),
        ):
            ensure_art_style_rules_file("abc")
            rules_path = art_styles_dir / "abc.json"
            self.assertTrue(rules_path.is_file())
            self.assertEqual(get_art_style("abc", "1"), DEFAULT_ART_STYLE_NAME)
            self.assertEqual(get_art_style("abc", "promo"), DEFAULT_ART_STYLE_NAME)
            self.assertEqual(get_art_style("abc", "A-1"), DEFAULT_ART_STYLE_NAME)

    def test_save_and_normalize_rules(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        art_styles_dir = Path(temp_dir.name) / "art_styles"
        art_styles_dir.mkdir()

        with (
            patch("lib.art_styles.ART_STYLES_DIR", art_styles_dir),
            patch("lib.config.ART_STYLES_DIR", art_styles_dir),
        ):
            saved = save_art_style_rules(
                "ltr",
                [
                    {"name": "Main set", "firstNumber": 1, "lastNumber": 10},
                    {"name": "Alchemy", "prefix": "A-"},
                ],
            )
            self.assertEqual(len(saved), 2)
            self.assertEqual(get_art_style("ltr", "5"), "Main set")
            self.assertEqual(get_art_style("ltr", "A-5"), "Alchemy")

    def test_validate_rules_rejects_empty_name(self):
        errors = validate_art_style_rules([{"firstNumber": 1, "lastNumber": 2}])
        self.assertTrue(errors)

    def test_mh3_main_and_booster_fun_sections(self):
        self.assertEqual(get_art_style("mh3", "100"), "01. Main set")
        self.assertEqual(get_art_style("mh3", "280"), "02. Bonus sheet")
        self.assertEqual(get_art_style("mh3", "305"), "03. Full-art Eldrazi basics")
        self.assertEqual(get_art_style("mh3", "330"), "05. Frame break")
        self.assertEqual(get_art_style("mh3", "400"), "09. Retro frame")
        self.assertEqual(get_art_style("mh3", "450"), "11. Extended art")
        self.assertEqual(get_art_style("mh3", "510"), "16. Ripple foil")

    def test_mh3_serialized_eldrazi_titans(self):
        self.assertEqual(get_art_style("mh3", "382"), "08. Borderless concept Eldrazi")
        self.assertEqual(get_art_style("mh3", "382z"), "08z. Borderless concept Eldrazi: serialized")

    def test_2x2_main_borderless_etched_and_promos(self):
        self.assertEqual(get_art_style("2x2", "79"), "01. Main set")
        self.assertEqual(get_art_style("2x2", "332"), "01. Main set")
        self.assertEqual(get_art_style("2x2", "333"), "02. Borderless planeswalkers")
        self.assertEqual(get_art_style("2x2", "335"), "03. Borderless")
        self.assertEqual(get_art_style("2x2", "412"), "03. Borderless")
        self.assertEqual(get_art_style("2x2", "413"), "04. Foil etched")
        self.assertEqual(get_art_style("2x2", "572"), "04. Foil etched")
        self.assertEqual(get_art_style("2x2", "573"), "05. Textured foil")
        self.assertEqual(get_art_style("2x2", "578"), "06. Promos")

    def test_tdm_main_showcases_and_promos(self):
        self.assertEqual(get_art_style("tdm", "100"), "01. Main set")
        self.assertEqual(get_art_style("tdm", "291"), "01. Main set")
        self.assertEqual(get_art_style("tdm", "292"), "02. Draconic showcases")
        self.assertEqual(get_art_style("tdm", "327"), "03. Borderless clan showcases")
        self.assertEqual(get_art_style("tdm", "377"), "04. Reversible dragons")
        self.assertEqual(get_art_style("tdm", "383"), "05. Borderless alternate art")
        self.assertEqual(get_art_style("tdm", "399"), "06. Ghostfire showcases")
        self.assertEqual(get_art_style("tdm", "409"), "07. Halo foil ghostfire")
        self.assertEqual(get_art_style("tdm", "419"), "08. Serialized headliner")
        self.assertEqual(get_art_style("tdm", "420"), "09. Promo pack")
        self.assertEqual(get_art_style("tdm", "425"), "10. Bundle promo")
        self.assertEqual(get_art_style("tdm", "426"), "11. Buy-a-Box")
        self.assertEqual(get_art_style("tdm", "A-103"), "12. Alchemy promos")


if __name__ == "__main__":
    unittest.main()
