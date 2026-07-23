"""Average-hash fingerprints for MTG card art matching (OCR-free scan)."""

from __future__ import annotations

import sqlite3
from io import BytesIO

import requests
from PIL import Image

from util.alchemy_cards import exclude_alchemy_art_style_sql, exclude_alchemy_sql
from util.db_migrate import ensure_card_columns

ART_BOX = {"x": 0.08, "y": 0.12, "width": 0.84, "height": 0.42}
ART_HASH_SIZE = 8
HASH_BUILD_BATCH = 48
AUTO_MAX_DISTANCE = 12
AUTO_MIN_GAP = 4


def sample_art_luma(image: Image.Image, *, size: int = ART_HASH_SIZE) -> list[int]:
    """Sample the art box into a size×size luma grid (matches the frontend sampler)."""
    rgb = image.convert("RGB")
    width, height = rgb.size
    src_x = max(0, int(width * ART_BOX["x"]))
    src_y = max(0, int(height * ART_BOX["y"]))
    src_w = max(1, int(width * ART_BOX["width"]))
    src_h = max(1, int(height * ART_BOX["height"]))
    pixels = rgb.load()
    out: list[int] = []
    for y in range(size):
        for x in range(size):
            px = src_x + min(src_w - 1, int(((x + 0.5) / size) * src_w))
            py = src_y + min(src_h - 1, int(((y + 0.5) / size) * src_h))
            r, g, b = pixels[px, py]
            out.append(int(round(r * 0.299 + g * 0.587 + b * 0.114)))
    return out


def ahash_from_luma(lumas: list[int]) -> str:
    if not lumas:
        return ""
    mean = sum(lumas) / len(lumas)
    value = 0
    for index, luma in enumerate(lumas):
        if luma >= mean:
            value |= 1 << (len(lumas) - 1 - index)
    width = max(16, (len(lumas) + 3) // 4)
    return f"{value:0{width}x}"


def ahash_from_image(image: Image.Image) -> str:
    return ahash_from_luma(sample_art_luma(image))


def ahash_from_image_bytes(data: bytes) -> str:
    with Image.open(BytesIO(data)) as image:
        return ahash_from_image(image)


def hamming_distance(left: str, right: str) -> int:
    a = str(left or "").strip().lower()
    b = str(right or "").strip().lower()
    if not a or not b:
        return 64
    try:
        av = int(a, 16)
        bv = int(b, 16)
    except ValueError:
        return 64
    return (av ^ bv).bit_count()


def hash_match_score(distance: int, *, bits: int = 64) -> float:
    return max(0.0, min(1.0, 1.0 - (float(distance) / float(bits))))


def fetch_image_bytes(url: str, *, timeout: float = 8.0) -> bytes | None:
    text = str(url or "").strip()
    if not text:
        return None
    try:
        response = requests.get(
            text,
            timeout=timeout,
            headers={"User-Agent": "lotr-collection-scan/1.0"},
        )
        if response.status_code != 200 or not response.content:
            return None
        return response.content
    except requests.RequestException:
        return None


def fill_missing_art_hashes(conn: sqlite3.Connection, *, limit: int = HASH_BUILD_BATCH) -> int:
    """Download previews and store art_ahash for cards that still need one."""
    ensure_card_columns(conn)
    rows = conn.execute(
        f"""
        SELECT set_code, collector_number, COALESCE(art_style, ''), image_uri
        FROM cards
        WHERE (art_ahash IS NULL OR art_ahash = '')
          AND image_uri IS NOT NULL
          AND TRIM(image_uri) != ''
          AND {exclude_alchemy_sql()}
          AND {exclude_alchemy_art_style_sql()}
        ORDER BY set_code, CAST(collector_number AS INTEGER)
        LIMIT ?
        """,
        (max(1, min(int(limit), 200)),),
    ).fetchall()
    filled = 0
    for set_code, collector_number, art_style, image_uri in rows:
        data = fetch_image_bytes(image_uri)
        if not data:
            continue
        try:
            digest = ahash_from_image_bytes(data)
        except Exception:
            continue
        if not digest:
            continue
        conn.execute(
            """
            UPDATE cards
            SET art_ahash = ?
            WHERE set_code = ?
              AND collector_number = ?
              AND COALESCE(art_style, '') = ?
            """,
            (digest, set_code, collector_number, art_style or ""),
        )
        filled += 1
    if filled:
        conn.commit()
    return filled


def art_hash_coverage(conn: sqlite3.Connection) -> dict:
    ensure_card_columns(conn)
    total = conn.execute(
        f"""
        SELECT COUNT(*)
        FROM cards
        WHERE image_uri IS NOT NULL AND TRIM(image_uri) != ''
          AND {exclude_alchemy_sql()}
          AND {exclude_alchemy_art_style_sql()}
        """
    ).fetchone()[0]
    hashed = conn.execute(
        f"""
        SELECT COUNT(*)
        FROM cards
        WHERE art_ahash IS NOT NULL AND TRIM(art_ahash) != ''
          AND {exclude_alchemy_sql()}
          AND {exclude_alchemy_art_style_sql()}
        """
    ).fetchone()[0]
    return {
        "totalWithImages": int(total or 0),
        "hashed": int(hashed or 0),
        "coverage": (float(hashed) / float(total)) if total else 0.0,
    }


def search_prints_by_art_hash(
    conn: sqlite3.Connection,
    probe_ahash: str,
    *,
    limit: int = 12,
    build_missing: bool = True,
) -> dict:
    """Rank catalog prints by Hamming distance to a probe art aHash."""
    ensure_card_columns(conn)
    probe = str(probe_ahash or "").strip().lower()
    if len(probe) < 8:
        raise ValueError("artHash is required")

    built = 0
    coverage = art_hash_coverage(conn)
    if build_missing and coverage["hashed"] < max(20, int(coverage["totalWithImages"] * 0.15)):
        built = fill_missing_art_hashes(conn, limit=HASH_BUILD_BATCH)
        coverage = art_hash_coverage(conn)

    rows = conn.execute(
        f"""
        SELECT
            set_code,
            collector_number,
            name,
            COALESCE(art_style, ''),
            COALESCE(image_uri, ''),
            COALESCE(has_nonfoil, 0),
            COALESCE(has_foil, 0),
            COALESCE(has_etched, 0),
            art_ahash
        FROM cards
        WHERE art_ahash IS NOT NULL
          AND TRIM(art_ahash) != ''
          AND {exclude_alchemy_sql()}
          AND {exclude_alchemy_art_style_sql()}
        """
    ).fetchall()

    scored: list[tuple[int, tuple]] = []
    for row in rows:
        distance = hamming_distance(probe, row[8])
        scored.append((distance, row))
    scored.sort(key=lambda item: (item[0], str(item[1][0]), str(item[1][1])))

    safe_limit = max(1, min(int(limit or 12), 40))
    prints = []
    for distance, row in scored[:safe_limit]:
        prints.append(
            {
                "setCode": row[0],
                "collectorNumber": str(row[1]),
                "name": row[2],
                "artStyle": row[3] or "",
                "imageUri": row[4] or "",
                "hasNonfoil": bool(row[5]),
                "hasFoil": bool(row[6]),
                "hasEtched": bool(row[7]),
                "artDistance": distance,
                "artScore": round(hash_match_score(distance), 4),
            }
        )

    return {
        "prints": prints,
        "totalCompared": len(rows),
        "hashesBuilt": built,
        "coverage": coverage,
        "probeHash": probe,
    }
