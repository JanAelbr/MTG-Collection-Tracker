import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from report.report_data import build_art_style_option, build_set_option  # noqa: E402
from report.set_order import SET_PICKER_BROWSER, SET_SORT_OWNED, normalize_favorite_sets, normalize_set_picker_mode, sort_set_codes  # noqa: E402


class SetOrderTests(unittest.TestCase):
    def test_sort_set_codes_puts_favorites_first_in_order(self):
        codes = ["LTR", "MB2", "2X2", "ABC"]
        favorites = ["MB2", "LTR"]
        self.assertEqual(
            sort_set_codes(codes, favorites),
            ["MB2", "LTR", "2X2", "ABC"],
        )

    def test_sort_set_codes_ignores_unknown_favorites(self):
        codes = ["LTR", "MB2"]
        self.assertEqual(sort_set_codes(codes, ["FOO", "MB2"]), ["MB2", "LTR"])

    def test_sort_set_codes_sorts_remaining_by_owned_count(self):
        codes = ["LTR", "MB2", "2X2", "ABC"]
        favorites = ["MB2", "LTR"]
        owned_counts = {"LTR": 5, "MB2": 20, "2X2": 100, "ABC": 10}
        self.assertEqual(
            sort_set_codes(codes, favorites, sort_mode=SET_SORT_OWNED, owned_counts=owned_counts),
            ["MB2", "LTR", "2X2", "ABC"],
        )

    def test_sort_set_codes_sorts_by_owned_without_favorites(self):
        codes = ["LTR", "MB2", "2X2"]
        owned_counts = {"LTR": 5, "MB2": 20, "2X2": 10}
        self.assertEqual(
            sort_set_codes(codes, sort_mode=SET_SORT_OWNED, owned_counts=owned_counts),
            ["MB2", "2X2", "LTR"],
        )

    def test_normalize_favorite_sets_deduplicates_and_uppercases(self):
        self.assertEqual(
            normalize_favorite_sets(["ltr", "LTR", " mb2 ", ""]),
            ["LTR", "MB2"],
        )

    def test_build_set_option_marks_favorites(self):
        set_names = {"LTR": "Lord of the Rings", "MB2": "Mystery Booster 2"}
        all_option = build_set_option("All", set_names, ["LTR"])
        ltr_option = build_set_option("LTR", set_names, ["LTR"])
        mb2_option = build_set_option("MB2", set_names, ["LTR"])

        self.assertEqual(all_option["label"], "All sets")
        self.assertFalse(all_option["favorite"])
        self.assertTrue(ltr_option["favorite"])
        self.assertFalse(mb2_option["favorite"])

    def test_build_set_option_includes_counts(self):
        set_names = {"LTR": "Lord of the Rings"}
        option = build_set_option("LTR", set_names, [], owned_count=12, catalog_count=400)
        self.assertEqual(option["ownedCount"], 12)
        self.assertEqual(option["catalogCount"], 400)

    def test_build_art_style_option_includes_counts(self):
        option = build_art_style_option("Borderless", owned_count=3, catalog_count=12)
        self.assertEqual(option["artStyle"], "Borderless")
        self.assertEqual(option["ownedCount"], 3)
        self.assertEqual(option["catalogCount"], 12)

    def test_build_set_option_includes_icon_uri(self):
        set_names = {"LTR": "Lord of the Rings"}
        option = build_set_option("LTR", set_names, [])
        self.assertEqual(option["iconUri"], "https://svgs.scryfall.io/sets/ltr.svg")

    def test_build_set_option_prefers_stored_icon_uri(self):
        set_names = {"HOB": "The Hobbit"}
        icon_uri = "https://svgs.scryfall.io/sets/hob.svg?1782705600"
        option = build_set_option("HOB", set_names, [], icon_uri=icon_uri)
        self.assertEqual(option["iconUri"], icon_uri)

    def test_normalize_set_picker_mode(self):
        self.assertEqual(normalize_set_picker_mode("browser"), SET_PICKER_BROWSER)
        self.assertEqual(normalize_set_picker_mode("invalid"), "dropdown")


if __name__ == "__main__":
    unittest.main()
