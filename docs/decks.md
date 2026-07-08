# Commander decks

Decks are stored in **SQLite** (`decks` and `deck_cards` tables). Create and edit them in the **Decks** section of the web app. Ownership is tracked in `purchases` when you mark cards as owned in Set Manager or Storage.

The portable format for moving collections between machines is **Settings → Backup & restore** (`.mtgbackup.zip`). See [readme.md](../readme.md).

---

## Data model

### `decks`

| Column | Description |
|--------|-------------|
| `name` | Display name (unique) |
| `slug` | URL-safe identifier (unique) |
| `purchase_price` | Optional total EUR paid for the precon |
| `format` | Deck format (default `commander`) |

### `deck_cards`

One row per printing in the deck list.

| Column | Description |
|--------|-------------|
| `set_code` | Scryfall set code for the printing |
| `collector_number` | Collector number in that set |
| `finish` | `0` non-foil, `1` foil, `2` etched |
| `qty` | Copies in the deck list |
| `owned_qty` | Copies you own for this deck slot |
| `section` | `commander`, `main`, or `sideboard` |
| `in_catalog` | `1` when the print exists in `cards` |

Rows are unique per `(deck_id, set_code, collector_number, finish, section)` — not per card name. A deck may include two different **Forest** printings as separate rows.

### Catalog matching

When you add a card, the API resolves the print against the `cards` table. If the set has not been added in Set Manager yet, the row is stored with `in_catalog = 0` until you register that set and run a price/catalog sync.

Set codes referenced by deck cards are included in price-update set discovery (`util/deck_tables.list_deck_sync_set_codes`).

---

## Ownership

Deck reports use `purchases` for owned value and ROI. Mark cards as owned in **Set Manager** or assign copies in **Storage**. The `owned_qty` column on `deck_cards` tracks how many deck slots you consider filled from your collection.

Deck `purchase_price` is stored on the deck row for aggregate invested/ROI figures in deck stats.

---

## Typical workflow

**New install**

1. Start the app (`scripts/dev_app.ps1` or `scripts/run_app.ps1`) — the database is created on first API start
2. Add sets in **Set Manager**, create decks in **Decks**, mark ownership

**Moving to another machine**

1. **Settings → Export collection** (backup ZIP)
2. Install the app on the new machine
3. **Settings → Restore from backup**
4. Add any missing sets in Set Manager, then **Sync prices**

**Refresh prices**

Use **Settings → Sync prices** in the app (Cardmarket only).

---

## Backup contents

Collection backups include purchases, decks, deck cards, storage locations, card instances, art-style rules, tracked sets, and user settings. They do **not** include the full Scryfall catalog or price history — restore those with Set Manager and price sync after import.

Implementation: `server-backend/collection/util/collection_backup.py`.
