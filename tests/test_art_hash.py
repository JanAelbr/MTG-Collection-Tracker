import sqlite3
import sys
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "server-backend"
COLLECTION = BACKEND / "collection"
for path in (BACKEND, COLLECTION, str(ROOT / "scripts")):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)

from util.art_hash import (  # noqa: E402
    ahash_from_image,
    ahash_from_luma,
    hamming_distance,
    hash_match_score,
    sample_art_luma,
    search_prints_by_art_hash,
)


class ArtHashTests(unittest.TestCase):
    def test_ahash_stable_for_solid_color(self):
        image = Image.new("RGB", (200, 280), (220, 40, 40))
        digest = ahash_from_image(image)
        self.assertEqual(len(digest), 16)
        self.assertEqual(digest, ahash_from_image(image))

    def test_different_patterns_differ(self):
        left = Image.new("RGB", (200, 280), (0, 0, 0))
        right = Image.new("RGB", (200, 280), (0, 0, 0))
        for x in range(20, 100):
            for y in range(40, 160):
                left.putpixel((x, y), (255, 255, 255))
        for x in range(100, 180):
            for y in range(40, 160):
                right.putpixel((x, y), (255, 255, 255))
        self.assertGreater(
            hamming_distance(ahash_from_image(left), ahash_from_image(right)),
            0,
        )

    def test_luma_roundtrip_matches_js_packing(self):
        # All above mean except first pixel pattern
        lumas = [0] + [255] * 63
        digest = ahash_from_luma(lumas)
        self.assertEqual(digest, f"{(1 << 63) - 1:016x}")

    def test_search_ranks_exact_hash(self):
        conn = sqlite3.connect(":memory:")
        conn.execute(
            """
            CREATE TABLE cards (
                set_code TEXT,
                collector_number TEXT,
                name TEXT,
                art_style TEXT,
                image_uri TEXT,
                has_nonfoil INTEGER,
                has_foil INTEGER,
                has_etched INTEGER,
                art_ahash TEXT
            )
            """
        )
        target = ahash_from_image(Image.new("RGB", (120, 168), (30, 180, 60)))
        other = ahash_from_image(Image.new("RGB", (120, 168), (180, 30, 60)))
        conn.executemany(
            """
            INSERT INTO cards VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("ONE", "1", "Green Card", "", "https://g.jpg", 1, 0, 0, target),
                ("ONE", "2", "Red Card", "", "https://r.jpg", 1, 0, 0, other),
            ],
        )
        conn.commit()
        result = search_prints_by_art_hash(conn, target, limit=5, build_missing=False)
        self.assertEqual(result["prints"][0]["name"], "Green Card")
        self.assertEqual(result["prints"][0]["artDistance"], 0)
        self.assertGreater(hash_match_score(0), hash_match_score(8))
        conn.close()


if __name__ == "__main__":
    unittest.main()
