import unittest
from pathlib import Path

import runpy

runpy.run_path(str(Path(__file__).resolve().with_name("_paths.py")))

from api.services.search_service import (  # noqa: E402
    _card_matches_keyword_terms,
    parse_keyword_search_terms,
)


class KeywordSearchTests(unittest.TestCase):
    def test_parse_keyword_terms(self):
        self.assertEqual(parse_keyword_search_terms("trample, haste"), ["trample", "haste"])
        self.assertEqual(parse_keyword_search_terms("first strike"), ["first strike"])
        self.assertEqual(parse_keyword_search_terms("  Flying , flying "), ["flying"])

    def test_keyword_word_boundary(self):
        card = {"oracleText": "Flying, vigilance\nWhenever this creature attacks, draw a card."}
        self.assertTrue(_card_matches_keyword_terms(card, ["flying"]))
        self.assertTrue(_card_matches_keyword_terms(card, ["vigilance"]))
        self.assertFalse(_card_matches_keyword_terms(card, ["haste"]))
        self.assertTrue(_card_matches_keyword_terms(card, ["flying", "vigilance"]))
        self.assertFalse(_card_matches_keyword_terms(card, ["flying", "trample"]))

    def test_multiword_keyword(self):
        card = {"oracleText": "First strike\nWhen this creature dies, create a Food token."}
        self.assertTrue(_card_matches_keyword_terms(card, ["first strike"]))
        self.assertFalse(_card_matches_keyword_terms(card, ["double strike"]))


if __name__ == "__main__":
    unittest.main()
