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
| **Collection** | `/collection/all` | All cards, Top owned, Search, Stats |
| **Storage** | `/storage` | — |
| **Set Manager** | `/manager` | — |
| **Decks** | `/decks` | — |
| **Settings** | `/settings` | — |

`/`, `/collection`, and old `/reports/*` URLs redirect to `/collection/all` or the matching collection view.

**Stats** (`/stats`) is grouped under Collection in the subnav but is its own route.

---

## Set picker

Controlled in **Settings → Set picker mode**:

| Mode | Behaviour |
|------|-----------|
| **Browser** | Horizontal set gallery (banner) with coloured set symbols; filter sidebar shows the **full set name** for the active set |
| **Dropdown** | Searchable set list in the filter sidebar |

Set gallery cards show **set code** and completion count only (not the full name). Favourited sets can be starred in browser mode.

Set symbols use [mtg-vectors](https://github.com/Investigamer/mtg-vectors) with rarity tint from completion %; Scryfall monochrome SVG is used on load failure.

---

## Collection filters

Filter sidebar (collapsible) on **All cards**, **Search**, **Set Manager**, and **Stats**:

- **Set** — scope; full name in sidebar when using set browser
- **Art style** — list picker per set; pencil icon on All cards links to Set Manager art-style editor (`/manager?set=CODE&editArtStyles=1`)
- **Ownership / Finish** — compact button groups (All cards & Search)
- **Type / Colour / Sort** — All cards view only

Filter state is reflected in the URL query string where applicable (`?set=LTR&art=…&owned=…`).

---

## Set completion

Completion counts (owned / catalog) use **distinct base collector numbers** per set:

- **Serialized** prints (collector number ending in `z` / `Z`) are **excluded**
- Numbers are normalised to digits only (`014` and `14` count as one slot; `WTH-53` → `53`)

Implemented in `scripts/util/set_completion.py` and used by report/stats loaders.

---

## Set code aliases

`PLIST` is normalised to **PLST** everywhere (CSV paths, database, UI). Migration runs on schema init (`scripts/util/db_migrate.py`).

---

## Key frontend paths

```text
server-frontend/
├── public/              # static assets + PWA icons
├── src/
│   ├── components/      # SetPicker, SetGallery, FilterSidebar, …
│   ├── views/           # CollectionView, ManagerView, …
│   ├── utils/           # format.js, setScope.js, mtgVectors.js, …
│   └── styles/app.css
└── vite.config.js       # Vite + PWA plugin
```
