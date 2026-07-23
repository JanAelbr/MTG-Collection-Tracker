# Frontend — Vue app

The interactive UI lives in `server-frontend/` (Vue 3 + Vite). The FastAPI backend serves the built `dist/` folder in production.

---

## Requirements

- **Node.js 22 LTS** recommended (Node 24 works; avoid attaching a debugger during `npm run build` — see below)
- `npm install` in `server-frontend/`

```powershell
.\scripts\build_frontend.ps1
# or
cd server-frontend
npm install
npm run build
```

Output: `server-frontend/dist/` (HTML, JS, CSS, service worker, PWA manifest).

### Build troubleshooting

If `npm run build` crashes after `✓ built` with a V8 / `v8_inspector` fatal error, VS Code’s **JavaScript Debugger** is usually attached to Node. Either:

- Run the build from a normal terminal (not **Debug**), or
- Use the provided build script (`node --no-inspect` is set in `package.json`)

---

## Development

```powershell
.\scripts\dev_app.ps1 -Install   # first time
.\scripts\dev_app.ps1
```

- Vite: http://localhost:5173 (proxies `/api` to `:8000`)
- API: http://localhost:8000

---

## Progressive Web App (PWA)

The app is installable as a PWA (`vite-plugin-pwa`).

| Asset | Purpose |
|-------|---------|
| `public/app-logo.svg` | Source logo (three card backs on dark background) |
| `public/pwa-*.png`, `maskable-icon-512x512.png` | Manifest icons |
| `public/apple-touch-icon-180x180.png` | iOS home screen |
| `public/favicon.ico` | Browser tab |

Regenerate PNG/ICO files after changing the logo:

```bash
cd server-frontend
npm run generate-pwa-icons
```

Requires `@vite-pwa/assets-generator` (dev dependency). Commit the updated files in `public/` before deploying.

Runtime caching (service worker) prefetches set icons from **mtg-vectors** (jsDelivr) and Scryfall SVG fallbacks for one year.

---

## Navigation

| Section | Default route | Sub-navigation |
|---------|---------------|----------------|
| **Collection** | `/collection/all` | All cards, Search, Stats |
| **Storage** | `/storage` | Gallery / Table / Breakdown (`?view=`) |

Storage **Breakdown** shows value tiles, finish/set charts, and top prints for the **selected location** (`?view=breakdown`).
| **Decks** | `/decks` | — |
| **Settings** | `/settings` | — |

`/`, `/collection`, and old `/reports/*` URLs redirect to `/collection/all` or the matching collection view.

**Stats** (`/stats`) is grouped under Collection in the subnav but is its own route.

---

## Favourites & home

`/` is the **Favourites** home. Sections appear in order: **Cards**, **Art styles**, **Sets**.

- **Cards** — collection-style card grid (print + finish); drag to reorder
- **Art styles** — one horizontal scrolling gallery row per favourited style; drag rows to reorder
- **Sets** — links into collection scoped to that set

Favourite ★ toggles on cards and sets appear on hover. Star art styles in the filter list. Settings remain at `/settings`.

---

## Set picker

Collection and Stats use a horizontal set gallery (banner) with coloured set symbols. The filter sidebar shows the **full set name** for the active set.

The gallery shows **one card per family**, and by default only families with **owned cards** (plus All and the active set). Use the navbar **Search sets** field to find any set already in the DB or on Scryfall (first 12 matches). Selecting a set that is not in the library yet **imports and populates** it automatically — there is no separate add/remove control. Related set codes appear as **tags to the right** (root first) only while that family is selected, in a scrollable column list. On startup / first sets load, missing Scryfall siblings for tracked families are imported automatically.

Set gallery cards show **set code** and completion count only (not the full name). Favourited sets can be starred in the gallery.

Set symbols use [mtg-vectors](https://github.com/Investigamer/mtg-vectors) with rarity tint from completion %; Scryfall monochrome SVG is used on load failure.

---

## Collection filters

Filter sidebar (collapsible) on **All cards**, **Search**, and **Stats**:

- **Set** — scope; full name in sidebar; favourites starred in the gallery
- **Art style** — list picker per set; pencil icon on All cards opens the inline art-style rules editor (`/collection/all?set=CODE&editArtStyles=1`)
- **Ownership / Finish** — compact button groups (All cards gallery & Search)
- **Type / Colour / Sort** — All cards gallery only
- **Table view** — on All cards with a specific set selected (`?view=table`); per-finish ownership, price health, bulk storage assign

Filter state is reflected in the URL query string where applicable (`?set=LTR&family=1&owned=…`).

---

## Set completion

Completion counts (owned / catalog) use **distinct base collector numbers** per set:

- **Serialized** prints (collector number ending in `z` / `Z`) are **excluded**
- Numbers are normalised to digits only (`014` and `14` count as one slot; `WTH-53` → `53`)

Implemented in `server-backend/collection/util/set_completion.py` and used by report/stats loaders.

---

## Set code aliases

`PLIST` is normalised to **PLST** everywhere (database and UI). Alias consolidation runs on schema init (`server-backend/collection/util/db_migrate.py`).

---

## Key frontend paths

```text
server-frontend/
├── public/              # static assets + PWA icons
├── src/
│   ├── components/      # SetPicker, SetGallery, FilterSidebar, …
│   ├── views/           # FavoritesHomeView, CollectionView, StorageView, …
│   ├── utils/           # format.js, setScope.js, favorites.js, mtgVectors.js, …
│   └── styles/app.css
└── vite.config.js       # Vite + PWA plugin
```
