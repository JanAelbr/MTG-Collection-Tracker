"""Regenerate lib/art_style_seed.py from the current art_style_rules table in collection.db."""

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COLLECTION = ROOT / "server-backend" / "collection"
if str(COLLECTION) not in sys.path:
    sys.path.insert(0, str(COLLECTION))

from lib.config import DB_PATH  # noqa: E402

OUT = COLLECTION / "lib" / "art_style_seed.py"


def main() -> None:
    if not DB_PATH.is_file():
        raise SystemExit(f"Database not found: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute(
            "SELECT set_code, rules_json FROM art_style_rules ORDER BY set_code"
        ).fetchall()
    finally:
        conn.close()

    bundled = {
        set_code: json.loads(rules_json)
        for set_code, rules_json in rows
    }
    payload = json.dumps(bundled, indent=4, ensure_ascii=False)
    OUT.write_text(
        '"""Bundled art-style rules for sets with custom collector-number groupings."""\n\n'
        f"BUNDLED_ART_STYLE_RULES: dict[str, list] = {payload}\n",
        encoding="utf-8",
    )
    print(f"Wrote {OUT} ({OUT.stat().st_size} bytes, {len(bundled)} sets)")


if __name__ == "__main__":
    main()
