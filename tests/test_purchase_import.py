import sqlite3
import sys
import tempfile
import unittest
import unittest.mock
from contextlib import ExitStack
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from lib.deck_csv import DeckEntry  # noqa: E402
from lib.purchase_csv_writer import generate_deck_purchase_csvs, read_purchase_csv_rows  # noqa: E402
from lib.purchase_loader import build_deck_purchase_rows, import_deck_purchase_file, import_purchases  # noqa: E402
from util.deck_tables import ensure_deck_tables  # noqa: E402


class DeckPurchaseImportTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name) / "data"
        self.decks_dir = self.data_dir / "decks"
        self.decks_dir.mkdir(parents=True)
        self.db_path = Path(self.temp_dir.name) / "collection.db"

        self.conn = sqlite3.connect(self.db_path)
        ensure_deck_tables(self.conn)
        self.conn.executescript(
            """
            CREATE TABLE cards (
                id TEXT PRIMARY KEY,
                set_code TEXT NOT NULL,
                collector_number TEXT NOT NULL,
                name TEXT NOT NULL
            );
            CREATE TABLE purchases (
                purchase_id INTEGER PRIMARY KEY AUTOINCREMENT,
                set_code TEXT NOT NULL,
                collector_number TEXT NOT NULL,
                purchase_value REAL NOT NULL DEFAULT 0,
                finish INTEGER NOT NULL CHECK (finish IN (0, 1, 2)),
                UNIQUE (set_code, collector_number, finish)
            );
            """
        )
        self.conn.execute(
            "INSERT INTO cards (id, set_code, collector_number, name) VALUES (?, ?, ?, ?)",
            ("PIP-4", "PIP", "4", "The Wise Mothman"),
        )
        self.conn.commit()
        self.cursor = self.conn.cursor()

        self.set_csv = self.data_dir / "ltr.csv"
        self.set_csv.write_text(
            "card_number,purchase_value,foil\n713,1.50,0\n",
            encoding="utf-8",
        )
        self.deck_csv = self.decks_dir / "wise_mothman.csv"
        self.deck_csv.write_text(
            "set_code;collector_number;foil;qty;section\n"
            "PIP;4;0;1;commander\n"
            "LTR;713;0;2;main\n",
            encoding="utf-8",
        )
        (self.decks_dir / "decks.csv").write_text(
            "deck_name;purchase_price;csv_location\n"
            "The Wise Mothman;;wise_mothman.csv\n",
            encoding="utf-8",
        )
        self.deck_entry = DeckEntry(
            name="The Wise Mothman",
            purchase_price=None,
            path=self.deck_csv,
            slug="wise_mothman",
        )

    def tearDown(self):
        self.conn.close()
        self.temp_dir.cleanup()

    def _patch_data_paths(self):
        stack = ExitStack()
        stack.enter_context(unittest.mock.patch("lib.config.DATA_DIR", self.data_dir))
        stack.enter_context(unittest.mock.patch("lib.config.DB_PATH", self.db_path))
        stack.enter_context(unittest.mock.patch("lib.purchase_loader.DB_PATH", self.db_path))
        stack.enter_context(unittest.mock.patch("lib.purchase_csv_writer.DB_PATH", self.db_path))
        stack.enter_context(unittest.mock.patch("lib.deck_csv.DECKS_DIR", self.decks_dir))
        return stack

    def test_import_deck_purchase_file_uses_explicit_prints(self):
        imported = import_deck_purchase_file(self.cursor, self.deck_entry)
        self.conn.commit()
        self.assertEqual(imported, 2)
        rows = self.cursor.execute(
            "SELECT set_code, collector_number, finish FROM purchases ORDER BY set_code, collector_number"
        ).fetchall()
        self.assertEqual(rows, [("LTR", "713", 0), ("PIP", "4", 0)])

    def test_generate_deck_purchase_csvs_preserves_manual_prices(self):
        with self._patch_data_paths():
            generate_deck_purchase_csvs()

        ltr_rows, _ = read_purchase_csv_rows(self.set_csv)
        pip_rows, _ = read_purchase_csv_rows(self.data_dir / "pip.csv")
        self.assertAlmostEqual(ltr_rows[("713", 0)]["purchase_value"], 1.5)
        self.assertEqual(pip_rows[("4", 0)]["purchase_value"], 0.0)

    def test_import_purchases_uses_generated_set_csv_files(self):
        with self._patch_data_paths():
            import_purchases()

        conn = sqlite3.connect(self.db_path)
        ltr = conn.execute(
            "SELECT purchase_value FROM purchases WHERE set_code = 'LTR' AND collector_number = '713'"
        ).fetchone()
        pip = conn.execute(
            "SELECT purchase_value FROM purchases WHERE set_code = 'PIP' AND collector_number = '4'"
        ).fetchone()
        count = conn.execute("SELECT COUNT(*) FROM purchases").fetchone()[0]
        conn.close()
        self.assertEqual(ltr[0], 1.5)
        self.assertEqual(pip[0], 0.0)
        self.assertEqual(count, 2)


if __name__ == "__main__":
    unittest.main()
