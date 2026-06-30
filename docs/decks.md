# Commander deck lists

Deck tracking lives under `data/decks/`. Deck CSVs define **which print** of each card is in a list; purchase import marks those prints as **owned** in the database.

---

## Manifest (`data/decks/decks.csv`)

One row per deck. Semicolon delimiter.

```csv
deck_name;purchase_price;csv_location
Nekusar;50.0;nekusar.csv
Riders of Rohan;50.0;riders_of_rohan.csv
```

| Column | Description |
|--------|-------------|
| `deck_name` | Display name in reports |
| `purchase_price` | Total EUR paid for the precon (optional). Split across cards during purchase import |
| `csv_location` | Filename inside `data/decks/` |

The slug used in the database is derived from the CSV filename (without extension).

---

## Card list format (`data/decks/{slug}.csv`)

```csv
set_code;collector_number;foil;qty;owned;section
C13;1;0;1;1;commander
C13;42;0;1;1;main
C13;295;0;7;1;main
NCC;2;0;1;0;commander
SNC;217;0;1;1;main
```

| Column | Description |
|--------|-------------|
| `set_code` | Scryfall set code for the printing in the product (e.g. `C13`, `NCC`, `SNC`, `CLB`) |
| `collector_number` | Collector number in that set |
| `foil` | `0` = non-foil, `1` = foil |
| `qty` | Number of copies in the deck list |
| `owned` | Number of copies you own for this deck (0 to `qty`; defaults to `1` when omitted) |
| `section` | `commander`, `main`, or `sideboard` (case-insensitive) |

Rows are sorted by set code, then numeric collector number. Card names are resolved from the catalog at import time — do not add a `name` column.

### Same card name, different printings

A deck may contain multiple rows for the same card name (e.g. two different **Forest** printings). Rows are unique by `(set_code, collector_number, foil, section)`, not by name.

### Catalog matching

During deck import, each row is matched against the `cards` table. If the set has not been synced yet, the row is stored but `in_catalog = 0` and reports cannot price it.

Run `python scripts/update_prices.py` to fetch any set codes referenced in deck CSVs that are not yet in the local catalog. Prices come from the Cardmarket price guide on the next price update.

---

## Ownership vs deck import

These are separate steps:

| Step | Script | What it does |
|------|--------|--------------|
| Deck list | `deck_import.py` or `deck_sync.py` | Loads prints into `deck_cards` |
| Collection | `sync_collection.py` | Deck import + purchase CSV generation + purchase import (recommended) |
| Owned | `purchase_import.py` | Regenerates per-set purchase CSVs from decks, then rebuilds `purchases` from `data/{set}.csv` |

`sync_collection.py` runs deck import, then purchase import. Purchase import first writes deck ownership into `data/{set_code}.csv` files (merging with any manual rows already in those files), then loads all purchase CSVs into `purchases`.

`generate_report.py` reads the database only — it does not import CSVs or call Scryfall.

A card's owned count in deck reports comes from the `owned` column in the deck CSV (defaults to `1`). Set `owned` to `0` for cards you do not have. Purchase import writes matching rows into `data/{set_code}.csv` and then into `purchases`; decks with a `purchase_price` in the manifest have that total allocated across cards during CSV generation.

---

## Typical workflow

Three separate steps — collection, prices, reports:

```bash
python scripts/sync_collection.py
python scripts/update_prices.py
python scripts/generate_report.py --no-browser
```

**After editing deck or purchase CSVs:**

```bash
python scripts/sync_collection.py
python scripts/update_prices.py
python scripts/generate_report.py --no-browser
```

**Reports only (database unchanged):**

```bash
python scripts/generate_report.py --no-browser
```

**Single deck list change:**

```bash
python scripts/deck_sync.py sedris
python scripts/purchase_import.py
python scripts/generate_report.py --no-browser
```

---

## Building precon CSVs from official lists

For commander precons, use Scryfall prints from the **product set**, not random reprints from sets already in your collection.

| Script | Purpose |
|--------|---------|
| `build_catalog_decks.py` | Builds nine catalog precons (Sedris, Nekusar, Willowdusk, Prosper, Henzie, Arahbo, Umbris, Aminatou, Mishra) via mtg.wiki + Scryfall |
| `build_deck_csv.py` | Builds LOTR and other decks defined in `scripts/lib/precon_decklists.py` |
| `generate_precon_decklists.py` | Regenerates `precon_decklists.py` from wiki source files in `data/decks/sources/` |

After rebuilding CSVs:

```bash
python scripts/sync_collection.py
python scripts/update_prices.py
python scripts/generate_report.py --no-browser
```

Wiki sources and deck specs live in `data/decks/sources/` and `scripts/build_catalog_decks.py`. Scryfall lookups are cached in memory during a single build run to limit API traffic.

---

## Database tables

```text
decks           deck_id, name, slug, purchase_price, …
deck_cards      deck_id, set_code, collector_number, foil, qty, owned_qty, section, in_catalog, …
                UNIQUE (deck_id, set_code, collector_number, foil, section)
```

`deck_cards.card_name` is populated from the catalog for display; uniqueness is by print identity.

---

## Reports

| Report | File |
|--------|------|
| Deck lists | `reports/collection_decks.html` |
| Deck statistics | `reports/collection_deck_stats.html` |

Deck stats show owned coverage, invested value (from allocated purchase price), current value, and profit/loss per deck. Use the deck filter in the toolbar to scope ranked reports (top / risers / fallers) to cards from a selected deck.
