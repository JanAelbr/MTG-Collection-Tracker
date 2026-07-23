import unittest

runpy_path = __import__("pathlib").Path(__file__).resolve().with_name("_paths.py")
__import__("runpy").run_path(str(runpy_path))

from util.favorites import (  # noqa: E402
    favorite_art_style_key,
    favorite_card_key,
    normalize_favorite_art_styles,
    normalize_favorite_cards,
)


class FavoriteNormalizeTests(unittest.TestCase):
    def test_normalize_favorite_cards_dedupes_and_normalizes(self):
        result = normalize_favorite_cards([
            {"setCode": "ltr", "collectorNumber": "1", "finish": 1},
            {"set_code": "LTR", "collector_number": "1", "finish": "foil"},
            {"setCode": "LTR", "collectorNumber": "2", "finish": 0},
            {"setCode": "", "collectorNumber": "3", "finish": 0},
            "bad",
        ])
        self.assertEqual(
            result,
            [
                {"setCode": "LTR", "collectorNumber": "1", "finish": 1},
                {"setCode": "LTR", "collectorNumber": "2", "finish": 0},
            ],
        )
        self.assertEqual(favorite_card_key("ltr", "1", 1), "LTR|1|1")

    def test_normalize_favorite_art_styles(self):
        result = normalize_favorite_art_styles([
            {"setCode": "ltr", "artStyle": " Borderless "},
            {"set_code": "LTR", "art_style": "Borderless"},
            {"setCode": "MB2", "artStyle": ""},
            {"setCode": "MB2", "artStyle": "Showcase"},
        ])
        self.assertEqual(
            result,
            [
                {"setCode": "LTR", "artStyle": "Borderless"},
                {"setCode": "MB2", "artStyle": "Showcase"},
            ],
        )
        self.assertEqual(favorite_art_style_key("mb2", "Showcase"), "MB2|Showcase")


if __name__ == "__main__":
    unittest.main()
