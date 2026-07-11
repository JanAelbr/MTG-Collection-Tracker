# Art style rules

Art-style labels split a set into collector-number groups (e.g. LTR main set vs showcase). Rules are stored in the local SQLite database (`art_style_rules` table).

## Runtime behavior

- On first run, bundled defaults from `server-backend/collection/lib/art_style_seed.py` are seeded for sets with custom groupings.
- Other sets default to a single `"All"` group.
- Edit rules in **Set Manager** or via the art-style link on the collection filter sidebar.
- Legacy `data/art_styles/*.json` files are imported once on upgrade if still present.
- Custom rules are included in **Settings → Backup & restore** exports (`art_styles/{set}.json` inside the ZIP).

## Shipping updated defaults

When you tune art-style rules locally and want fresh installs to get the same defaults:

1. Edit rules in the app (Set Manager).
2. Regenerate the bundled seed from your local database:

   ```powershell
   .\.venv\Scripts\python.exe scripts\generate_art_style_seed.py
   ```

3. Commit `server-backend/collection/lib/art_style_seed.py`.

The generator reads `art_style_rules` from your local `collection.db` (`%LOCALAPPDATA%\MtgCollectionTracker\collection.db` on Windows) and rewrites the Python module. It is a maintainer tool — the app does not call it at runtime.

Existing databases keep their own rules; seeding only fills sets that do not already have DB rows.
