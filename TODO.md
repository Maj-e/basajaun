# TODO — Ulinautas (MODIS + VIIRS fire hotspots)

Team: **4 backend** (B1–B4) and **1 front end / DevOps** (F).
Data contract (file formats, layer manifest, MODIS / VIIRS field mapping): [`docs/data_contract.md`](docs/data_contract.md).

---

## 1. Roles

| Role | Person | Responsible for |
|---|---|---|
| **B1 — Harmonization** | ___ | Data contract (**owner**), MODIS / VIIRS normalization, deduplication, risk and alerts |
| **B2 — Ingestion & fires** | ___ | FIRMS key and demo area, download, grouping into fires, wind and weather, spread projection |
| **B3 — Aggregates & population** | ___ | Volume measurement, hotspot export, summaries (calendar, time series), population |
| **B4 — Data platform** | ___ | Repo and CI, contract validator, layer manifest, checks on the published URL, OSM, automatic refresh, API |
| **F — Front end / DevOps** | ___ | Web page, generic layer loader, filters, calendar, timeline, panels; deployment and domain |

**Principle:** with a single front-end developer, **the backend ships display-ready data** (colors, sizes, legends already computed) and **declares every layer in a manifest**. F writes a generic loader once; after that, **adding a layer = one file + one manifest entry**, with no front-end change.

---

## 2. Tasks per role

| Wave | B1 — Harmonization | B2 — Ingestion & fires | B3 — Aggregates & population | B4 — Data platform | F — Front end / DevOps |
|---|---|---|---|---|---|
| **0 · Base** | **W0-B1** Frozen contract + sample data | **W0-B2** FIRMS key + area + `config.py` | **W0-B3** FIRMS volume measurement | **W0-B4** Repo, environment, Makefile, CI | **W0-F1** Web skeleton + deployment |
| **1 · MVP** | **W1-B1** MODIS / VIIRS normalization + tests | **W1-B2** Full FIRMS download | **W1-B3** Hotspot export + daily summary | **W1-B4** Contract validator + manifest | **W1-F0** Playback screen mockup<br>**W1-F1** Layer loader + hotspot layer<br>**W1-F2** Filters + "no data" status |
| **2 · Calendar + playback** | **W2-B1** MODIS / VIIRS deduplication | **W2-B2** Fires (grouping) | **W2-B3** Time series (counter, chart) | **W2-B4** End-to-end check on the URL | **W2-F1** Calendar<br>**W2-F2** Timeline + animation<br>**W2-F3** Figures follow the visible area |
| **3 · Layers + alerts** | **W3-B1** Exposed population + risk + alerts | **W3-B2** Wind + weather<br>**W3-B5** Dedup + fires in `make data` | **W3-B3** Population (WorldPop)<br>**W3-B6** Regions per hotspot | **W3-B4** OSM: water, roads, fire stations + accessibility | **W3-F1** Layer panel + temporal layers + relief<br>**W3-F2** Alert panel<br>**W3-F3** Isolate a fire<br>**W3-F4** Region selector |
| **4 · Live + episodes** | **W4-B1** Alerts on recent data | — | — | **W4-B4** Automatic refresh with validation<br>**W4-B5** Pipeline per episode | **W4-F1** "Live" button<br>**W4-F2** Episode selector + world basemap |
| **5 · Later** | **W5-B1** Notifications | **W5-B2** Spread projection | **W5-B3** Slope and land cover | **W5-B4** FastAPI API + hosting | **W5-F1** Mobile, i18n, animation export |

A **—** cell: the role helps the others (testing, PR review, data for the front end).

---

## 3. Waves

Each wave leaves the app **working and published**. From Wave 1 on there is a presentable MVP; later waves add features **behind a toggle** (the manifest `active` field): a feature that isn't ready stays off and doesn't break the demo.

| Wave | Goal | Visible result | Prio |
|---|---|---|---|
| **0 · Base** | All 5 people can work in parallel from the start | Page online with sample data, frozen contract, measured volume | P0 |
| **1 · MVP** | Read harmonized MODIS + VIIRS | **Map of real hotspots with date, sensor and confidence filters, published** | P0 |
| **2 · Calendar + playback** | Navigate through time | Hotspot calendar, animated playback, fire outlines | P0 / P1 |
| **3 · Layers + alerts** | Context and risk for the population; zoom on one zone | Population, wind, weather, water, roads, fire stations, relief layers + alert panel; isolate a fire; pick a region | P1 |
| **4 · Live + episodes** | Active hotspots in near real time; anywhere on Earth | "Live" button: last 48 h; switch between fire episodes on other continents | P1 / P2 |
| **5 · Later** | From demo to product | API, notifications, spread projection, mobile… (independent) | P2 |

**Prio:** P0 = required for the MVP · P1 = strong improvement · P2 = once everything before is done.

### Rules of the day
1. **The contract is frozen before the first filter** (W0-B1 + F, 20 minutes together). After that, every change goes through B1 and is announced to the whole team.
2. **The site is online from Wave 0.** The MVP is not "publishing", it is replacing the sample data with the real data.
3. **A task is done when it works on the published URL**, not "on my machine".
4. **Midday checkpoint:** if harmonization isn't ready, publish VIIRS only as a fallback (without changing the goal).
5. **Freeze time set at the start of the day:** what hasn't started by then is dropped; what doesn't work is switched off in the manifest.
6. One task = one branch `feature/<id>-<name>` = one short PR to `dev` with green CI; `dev` is merged into `main` (published) once checked.

### How to add a feature after the MVP
1. Backend: a script in `scripts/` that writes a file to `web/data/processed/` **already styled** (`color`, `radius`, etc. properties), added to `make data`.
2. Backend: an entry in `web/data/manifest.json` (layer type, legend, `active: false` until checked).
3. The validator (W1-B4) passes in CI → merge → check on the URL → `active: true`.
4. F only steps in if the layer needs a display type the loader doesn't know yet.

---

## 4. Task details

Format: **what to do** · **files** · **done when** · **depends on**.

### Wave 0 — Base (P0)

- [x] **W0-B1** · Frozen contract + sample data · **B1** (with F)
  - 20-min session B1 + F: go through [`docs/data_contract.md`](docs/data_contract.md) field by field (hotspots, daily summary, fires, alerts, **manifest**, style properties, `updated_at` field) and freeze it
  - Script that **generates** the sample data from the contract (not by hand): ~50 MODIS + VIIRS hotspots in the area, 3 days, 3 confidence levels, with `t`, `color`, `radius`; `daily_summary`, `alerts`, `manifest.json`
  - Files: `scripts/make_sample.py` → `web/data/sample/*` (replaces the provisional files written for W1-F1)
  - **Done when:** F loads the sample files without asking for any format change
  - Depends on: —

- [x] **W0-B2** · FIRMS key + area + `config.py` · **B2**
  - Request the MAP_KEY at https://firms.modaps.eosdis.nasa.gov/api/map_key/ and test it:
    `curl "https://firms.modaps.eosdis.nasa.gov/api/area/csv/$FIRMS_MAP_KEY/VIIRS_SNPP_NRT/world/1"`
  - Pick an area and ~2 weeks with a real fire episode (good for playback)
    ```python
    BBOX = (-72.0, -38.0, -70.0, -33.0)   # west, south, east, north → replace
    START_DATE, END_DATE = "2026-02-01", "2026-02-14"
    RAW = Path("data/raw"); SAMPLE = Path("web/data/sample"); PROCESSED = Path("web/data/processed")
    ```
  - Also update `bbox` in `web/config.js` so the map frames the area
  - Files: `scripts/config.py`, `.env` (local, never committed)
  - **Done when:** the API answers and the area and dates are set
  - Depends on: —

- [x] **W0-B3** · FIRMS volume measurement · **B3**
  - Quick first download (VIIRS + MODIS, demo area and period), count the hotspots and measure the size of a raw GeoJSON
  - Write the result in `docs/volume.md` and decide with B1: **if the GeoJSON exceeds ~10 MB**, export one file per day; otherwise a single file
  - Adjust the number of sample hotspots in W0-B1 if the real volume is very different
  - **Done when:** the hotspot count and size are written down and the "one file / one per day" decision is made
  - Depends on: W0-B2

- [x] **W0-B4** · Repo, environment, Makefile, CI · **B4**
  - Folder layout from the [README](README.md#project-layout), `pyproject.toml` + `uv.lock` (uv), `.gitignore` (`.env`, `data/raw/`, `.venv/`), `.env.example`
  - `Makefile`: `make install`, `make data` (every script in order, missing ones skipped), `make sample`, `make test`, `make serve`
  - `.github/workflows/ci.yml`: `make test` on every PR; protection of `main` (PR required + green CI)
  - **Done when:** `make test` passes on a clean machine and a PR with a broken test is blocked
  - Depends on: —

- [x] **W0-F1** · Web skeleton + deployment · **F**
  - `index.html` + MapLibre GL `4.7.1` (unpkg); map framed on the area; empty panels: left (filters, calendar, layers), right (alerts), bottom (timeline)
  - `state.js`: shared state (`date`, `range`, `sensors`, `confidences`, `hour`, `layers`) with `setState` / `subscribe`
  - `.github/workflows/deploy.yml`: publishes `web/` to GitHub Pages on every push to `main`
  - **Demo URL: `https://maj-e.github.io/ulinautas/`** until the custom domain is verified from outside (`web/CNAME` + DNS + HTTPS in parallel, blocking nothing)
  - Paths **always relative** (`data/processed/...`)
  - **Done when:** the skeleton is visible on the github.io URL
  - Depends on: W0-B4 (layout)

### Wave 1 — MVP (P0)

- [x] **W1-B1** · MODIS / VIIRS normalization + tests · **B1**
  - `normalize_modis(df)`: confidence 0–100 → `low` (< 30) / `medium` (30–79) / `high` (≥ 80); `brightness` → `brightness_k`; `resolution_m = 1000`
  - `normalize_viirs(df, satellite)`: `l`/`low` → low, `n`/`nominal` → medium, `h`/`high` → high; `bright_ti4` → `brightness_k`; `resolution_m = 375`
  - `parse_datetime(acq_date, acq_time)`: `str.zfill(4)` (`742` → `0742`) → UTC datetime
  - Tests with 3 MODIS + 3 VIIRS rows written by hand
  - Files: `scripts/harmonize.py`, `scripts/tests/test_harmonize.py`
  - **Done when:** `make test` passes (start from a test CSV, without waiting for W1-B2)
  - Depends on: W0-B1

- [x] **W1-B2** · Full FIRMS download · **B2**
  - `https://firms.modaps.eosdis.nasa.gov/api/area/csv/{MAP_KEY}/{SOURCE}/{west},{south},{east},{north}/{DAYS}/{DATE}`
  - Sources `MODIS_NRT`, `VIIRS_SNPP_NRT`, `VIIRS_NOAA20_NRT`, `VIIRS_NOAA21_NRT` (`_SP` for older dates); 5-day chunks; don't download again if the file exists
  - Check the real codes of the `satellite` column and tell B1 if they differ from the contract
  - Files: `scripts/download_firms.py` → `data/raw/*.csv`
  - **Done when:** the 4 CSVs for the period are in `data/raw/`
  - Depends on: W0-B2

- [x] **W1-B3** · Hotspot export + daily summary · **B3**
  - Read `data/raw/*.csv` → W1-B1 functions → `pd.concat` → `id`, `date`, `t` (hours since 1970) → clip to `BBOX`
  - **Style computed here**: `color` by confidence (`high` `#d7301f`, `medium` `#fc8d59`, `low` `#fdcc8a`), `radius` by FRP (3 to 16 px), `border` by sensor
  - Coordinates to 4 decimals, FRP to 1; one or several files depending on the W0-B3 decision
  - `daily_summary.json`: **every** day of the period (`hotspots: 0`, `no_data: true` when empty)
  - `updated_at` field (generation time) in every file
  - Files: `scripts/export_hotspots.py` → `web/data/processed/hotspots*.geojson`, `daily_summary.json`
  - **Done when:** `make data` generates the files and the validator (W1-B4) accepts them
  - Depends on: W1-B1, W1-B2, W0-B3

- [x] **W1-B4** · Contract validator + manifest · **B4**
  - JSON schemas for every contract file (`docs/schemas/*.json`) + `scripts/validate.py` validating all of `web/data/` (`jsonschema`)
  - Add `uv run scripts/validate.py` to CI
  - `scripts/make_manifest.py`: generates `web/data/manifest.json` listing **only layers whose file exists** (name, file, type, temporal, legend, `active`, `updated_at`)
  - **Done when:** breaking a field in a PR fails CI, and the manifest reflects the files present
  - Depends on: W0-B1, W0-B4

- [x] **W1-F0** · Playback screen mockup · **F**
  - Design decisions from the design council: the page is the support of the demo story (`docs/demo-script.md`), dark "night thermal pass" world, full-screen map, dominant timeline strip with spark and peak computed from data, two readouts, legend on the map, alerts off until population exists, no "Live" label until wired
  - Files: `docs/mockup/index.html` (+ `hotspots.json`: 825 real vegetation fires, `land.geojson`: offline land outline); open with `cd docs/mockup && python3 -m http.server`
  - **Done when:** the team has reviewed the mockup; W1-F2, W2-F1, W2-F2 build from it
  - Depends on: —

- [x] **W1-F1** · Layer loader + hotspot layer · **F** — *merged (#5), showing the real FIRMS data on the published site*
  - `web/layers/loader.js`: reads `manifest.json` and, for each `active` layer, creates source + layer by `type` (`circle`, `fill`, `line`, `image`) using **the style properties from the file**:
    ```js
    "circle-color": ["get", "color"], "circle-radius": ["get", "radius"], "circle-stroke-color": ["get", "border"]
    ```
  - Legend built from the manifest; generic popup (shows the properties listed in the manifest)
  - **Done when:** the sample hotspots show with their style and popup, with no hand-written style in the front end
  - Depends on: W0-F1, W0-B1

- [ ] **W1-F2** · Filters + "no data" status · **F**
  - Date (`<input type="date">`), sensor (MODIS / VIIRS), confidence → `setState` → `map.setFilter`
  - Status banner: "Data from DD/MM HH:MM" (`updated_at` field) or "Layer unavailable" when the file is missing
  - Switch `CONFIG.manifest` from `data/sample/` to `data/manifest.json` once W1-B3 is on `main`
  - **Done when:** the filters work **with real data on the published URL** → ✅ **MVP**
  - Depends on: W1-F1, W1-B3

### Wave 2 — Calendar + playback (P0 / P1)

- [x] **W2-B1** · MODIS / VIIRS deduplication · **B1** · P1
  - Project to meters (UTM); distance < 1 km **and** |Δt| < 60 min → a single hotspot (keep the VIIRS one), `detected_by: ["MODIS","VIIRS"]`
  - Print how many hotspots were merged
  - Files: `scripts/dedup.py`
  - **Done when:** the validator accepts the output and the number of duplicates is documented
  - Depends on: W1-B3

- [x] **W2-B2** · Fires (grouping) · **B2** · P1
  - `DBSCAN(eps=1.0, min_samples=2)` on `[x_km, y_km, t / 12]` → `fire_id` on each hotspot
  - One polygon per fire (convex hull + 500 m buffer), **already styled** (`color`, `opacity`), with `start`, `end`, `n_hotspots`, `frp_max`, `area_km2`
  - Manifest entry with `active: false` until checked
  - Files: `scripts/fires.py` → `web/data/processed/fires.geojson`
  - **Done when:** known fires in the area come out as 1 group and the layer shows on the map with no new front-end code
  - Depends on: W2-B1

- [x] **W2-B3** · Time series · **B3** · P1
  - Per hour: active hotspots and total FRP (for the counter and a small timeline chart)
  - Files: `scripts/series.py` → `web/data/processed/hourly_series.json`
  - **Done when:** the file covers the whole period, hour by hour, and passes the validator
  - Depends on: W1-B3

- [x] **W2-B4** · End-to-end check on the URL · **B4**
  - Job after each deployment: downloads `manifest.json` and every listed file from the published URL, validates them against the contract, fails if any is missing
  - Simple load check: download time of the files used by the first page load
  - Files: `.github/workflows/e2e.yml`, `scripts/check_site.py`
  - **Done when:** a broken or missing file on the published site fails the job
  - Depends on: W1-B4, W0-F1

- [ ] **W2-F1** · Calendar · **F** · P0
  - Monthly grid from `daily_summary.json`: color by hotspot count, striped days without data, count on hover
  - Click → `setState({ date })`; Shift + click → range
  - Files: `web/calendar.js`
  - **Done when:** calendar and date filter always stay in sync, on the published URL
  - Depends on: W1-F2

- [x] **W2-F2** · Timeline + animation · **F** · P1 — *implemented from the mockup: strip chart, playback engine, spark / peak beats computed from data, presenter keys, readouts, NASA daily satellite toggle, WebGL fallback*
  - Slider in hours + ▶/⏸ + x1 / x4 / x16; `requestAnimationFrame` advances `state.hour`
  - The loader applies to every `temporal: true` layer: filter `t ≤ hour` and `t > hour − 6`, decreasing opacity (6-hour trail)
  - Counter and small chart from `hourly_series.json`
  - Files: `web/timeline.js`
  - **Done when:** hotspots appear at their time and fade out over 6 h, smoothly with the real data
  - Depends on: W1-F2, W2-B3

- [x] **W2-F3** · Figures follow the visible area · **F**
  - Zooming or panning recomputes the readouts, the timeline bars, the spark and the peak on the hotspots visible on screen; a scope line says "whole area" or "visible area · N of M fires", with a **Show whole area** button
  - Files: `web/app.js` (`applyScope`), `web/timeline.js` (`setData`), `web/story.js`
  - **Done when:** zooming on a sector updates every figure, and the button restores the whole area
  - Depends on: W2-F2

### Wave 3 — Layers + alerts (P1)

- [ ] **W3-B1** · Exposed population + risk + alerts · **B1**
  - 1 / 5 / 10 km buffers per fire, `rasterstats.zonal_stats(stats="sum")` → `pop_1km`, `pop_5km`, `pop_10km`
  - Risk (thresholds in `config.py`): `critical` if `pop_1km ≥ 1000` or (`pop_5km ≥ 10000` and `frp_max ≥ 100`) · `high` if `pop_5km ≥ 1000` · `medium` if `pop_10km ≥ 100` · `low` otherwise
  - +1 level if the wind (W3-B2) blows toward the populated area (< 45°) at ≥ 20 km/h → `wind_toward_population: true`
  - `since` = time of the first hotspot; `color` by risk; sorted from most to least severe
  - Files: `scripts/exposure.py` → `web/data/processed/alerts.json`
  - **Done when:** the validator accepts `alerts.json` and not everything is `critical`
  - Depends on: W3-B3, W2-B2 (wind optional: W3-B2)

- [x] **W3-B2** · Wind + weather · **B2**
  - 5×5 grid over the `BBOX`, one Open-Meteo call:
    `https://archive-api.open-meteo.com/v1/archive?latitude=..&longitude=..&start_date=..&end_date=..&hourly=wind_speed_10m,wind_direction_10m,temperature_2m,relative_humidity_2m,precipitation`
  - **Temporal** GeoJSON output: one point per cell and per hour with `t`, `direction`, `speed`, `temperature`, `humidity`, `rain` + style (`rotation`, `size`, `color`)
  - Manifest entries: "wind" layer (type `arrows`, temporal) and "weather" layer (type `circle`, temporal)
  - Files: `scripts/weather.py` → `web/data/processed/weather.geojson`
  - **Done when:** the file passes the validator and covers every hour
  - Depends on: W0-B2

- [ ] **W3-B3** · Population (WorldPop) · **B3**
  - WorldPop "Population counts, 1 km, UN adjusted" for the country → crop to `BBOX` (`rasterio.mask`)
  - Export `population.tif` (for W3-B1) and a colored `population.png` + its 4 corners in the manifest (type `image`)
  - Files: `scripts/population.py`
  - **Done when:** the image overlays the map exactly
  - Depends on: W0-B2

- [ ] **W3-B4** · OSM: water, roads, fire stations + accessibility · **B4**
  - One Overpass query over the `BBOX`: water (`natural=water`, `waterway=river`, `landuse=reservoir`), roads (`highway=primary|secondary|tertiary|track|path`), fire stations (`amenity=fire_station`)
  - Style computed (color and width by road type), simplified geometries
  - For each fire: `dist_road_km`, `dist_water_km`, `dist_fire_station_km`
  - Files: `scripts/osm.py` → `water.geojson`, `roads.geojson`, `fire_stations.geojson` + manifest entries
  - **Done when:** the 3 layers show in the panel with no new front-end code and fires carry the 3 distances
  - Depends on: W2-B2

- [ ] **W3-F1** · Layer panel + temporal layers + relief · **F**
  - Checkbox panel generated from the manifest (one checkbox per `active` layer)
  - New `arrows` type in the loader: `symbol` layer with `icon-rotate: ["get","rotation"]`, `icon-size: ["get","size"]`
  - Relief: `raster-dem` source (AWS Terrarium tiles) + `hillshade` layer
  - Fire popup: shows the W3-B4 distances
  - **Done when:** every manifest layer can be toggled from the panel and the wind arrows turn during playback
  - Depends on: W2-F2

- [x] **W3-B5** · Dedup + fires in `make data` · **B2**
  - Add `dedup.py` (W2-B1) and `fires.py` (W2-B2) to the `make data` pipeline after the export, so `processed/hotspots.geojson` is deduplicated and carries `fire_id`, and `processed/fires.geojson` exists
  - **Done when:** `make data && make validate` passes and `make manifest` lists the `fires` layer
  - Depends on: W1-B3, W2-B1, W2-B2

- [ ] **W3-F3** · Isolate a fire · **F**
  - Click a fire outline → the map zooms on it, only its hotspots stay visible, and the readouts, timeline, spark and peak describe **that fire** (start, growth, max FRP); a **Show whole area** button returns to the overview
  - Builds on W2-F3 (figures already follow a scope)
  - **Done when:** clicking a fire shows its own story, on the published URL
  - Depends on: W3-B5

- [ ] **W3-B6** · Regions per hotspot · **B3**
  - Download administrative boundaries for every country of the episode (geoBoundaries ADM1, optionally ADM2), add a `region` (and `country`) property to each hotspot, and export `regions.geojson` (styled, in the manifest)
  - **Done when:** every hotspot carries `country` + `region` and the validator accepts the new fields
  - Depends on: W1-B3

- [ ] **W3-F4** · Region selector · **F**
  - A "Region" list in the header (built from the data): picking one zooms on it and scopes the figures to its hotspots, like W2-F3
  - **Done when:** picking a region updates the map and every figure
  - Depends on: W3-B6, W2-F3

- [ ] **W3-F2** · Alert panel · **F**
  - List from `alerts.json`: color by risk, population within 5 km, time; click → `map.flyTo({ center, zoom: 11 })`
  - During playback: only alerts with `since ≤ state.hour`
  - Files: `web/alerts.js`
  - **Done when:** alerts are clickable and in sync with the timeline, on the published URL
  - Depends on: W1-F2 (with sample `alerts`), W3-B1

### Wave 4 — Live + episodes (P1 / P2)

- [ ] **W4-B5** · Pipeline per episode · **B4** (with B2)
  - `web/data/episodes.json`: one entry per episode (`id`, `name`, `bbox`, `start`, `end`, `manifest`); the pipeline reads the episode instead of the fixed `BBOX`: `make data EPISODE=chile-2026-02` writes to `web/data/episodes/<id>/`
  - Pick 1–2 more real episodes (other continents, < 2 weeks, clearly visible in FIRMS)
  - **Done when:** two episodes are generated and validated side by side
  - Depends on: W1-B3, W1-B4

- [ ] **W4-F2** · Episode selector + world basemap · **F**
  - Episode list in the header; switching reframes the map and replays that episode (all figures are already computed from the data)
  - Replace the Chile/Argentina land outline with a world one (Natural Earth 50m, simplified); reference towns per episode
  - **Done when:** switching episodes works on the published URL, offline basemap included
  - Depends on: W4-B5

- [ ] **W4-B4** · Automatic refresh with validation · **B4**
  - `.github/workflows/update-data.yml` every 30 min + manual trigger: downloads the last 48 h → pipeline → **`validate.py`** → commit **only if valid**; otherwise the last good file is kept
  - Data in `web/data/processed/live/` (the demo episode is untouched)
  - `FIRMS_MAP_KEY` in the repository secrets, never in the browser
  - **Done when:** a manual run refreshes `live/`, and an invalid file never reaches the site
  - Depends on: W1-B4, W2-B4

- [ ] **W4-B1** · Alerts on recent data · **B1**
  - Run dedup + fires + exposure on `live/` → `live/alerts.json`
  - **Done when:** live mode has its own valid alerts
  - Depends on: W4-B4, W3-B1

- [ ] **W4-F1** · "Live" button · **F**
  - Button in the bottom bar: switches the data base from `processed/` to `processed/live/`, reloads the manifest every 5 min, "pulse" on new hotspots, "Updated X min ago" indicator
  - Demo mode (fixed episode) stays the default; `active: false` if live mode isn't ready
  - **Done when:** one click switches to live mode and recent hotspots appear without a reload
  - Depends on: W4-B4

### Wave 5 — Later (P2, independent)

- [ ] **W5-B1** · Notifications · **B1** — new `critical` alert in `live/` → webhook message (Telegram / Discord / email)
- [ ] **W5-B2** · Spread projection · **B2** — 6-hour ellipse from wind and slope, "estimate" layer in the manifest
- [ ] **W5-B3** · Slope and land cover · **B3** — mean slope per fire (Copernicus DEM), vegetation (ESA WorldCover)
- [ ] **W5-B4** · FastAPI API + hosting · **B4** — `GET /hotspots?from=&to=&bbox=`, `/fires`, `/alerts` on `api.<domain>` (Render / Railway / Fly.io), with fallback: if the API doesn't answer, the front end reads the static files
- [ ] **W5-F1** · Mobile, i18n, animation export · **F** — collapsible panels, `web/i18n.js` (Spanish UI), MP4 / GIF capture
