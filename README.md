# Ulinautas

Wildfire hotspot visualization from the **MODIS** and **VIIRS** satellites (NASA FIRMS), harmonized into a single dataset and shown on a web page: layered map, calendar, population-density alerts and time playback.

> Hackathon project (1 day). Work plan: [`TODO.md`](TODO.md) · data contract: [`docs/data_contract.md`](docs/data_contract.md) · **wiki: [`docs/wiki/`](docs/wiki/README.md)** (what we do, data sources, pipeline, operations, decisions).

**Convention:** everything in this repository is in English — code, UI, documentation, data field names.

---

## Stack

| Part | Technology | Role |
|---|---|---|
| Data processing | **Python 3.11** · pandas · geopandas · rasterio · rasterstats · scikit-learn · requests | Download, harmonize and enrich the data |
| Python environment | **[uv](https://docs.astral.sh/uv/)** (`pyproject.toml` + `uv.lock`) | Installs in seconds, pinned versions |
| Data exchange | Static **GeoJSON / JSON** files | Contract between the scripts and the front end |
| Front end | **HTML + JavaScript** (ES modules, no framework, no build) | User interface |
| Map | **MapLibre GL JS 4.7.1** (self-hosted in `web/vendor/`) | Vector map, filters, animation, layers |
| Hosting | **GitHub Pages** + custom domain | Published automatically on every push to `main`, free HTTPS |
| CI/CD | **GitHub Actions** | Tests and validation on every PR, deploy of `web/`, automatic data refresh |

### Why this stack

- **No server to maintain.** Data is computed with Python, locally or in GitHub Actions every 30 min (as fresh as FIRMS itself, which publishes ~3 h after each satellite pass), and published as files. The page depends on no live API: nothing can go down during the demo.
- **Python for geospatial work.** Projections, rasters, clustering and zonal statistics are much simpler in Python than in JavaScript.
- **MapLibre for the map.** Free, no API key, renders tens of thousands of points smoothly and filters / animates them with expressions, without reloading data.
- **No framework, no build.** Nobody loses time configuring npm, Webpack or Docker. It runs with `make serve`.
- **Teams that don't block each other.** The data contract separates the backend from the front end: the front end moves forward with sample data while the scripts produce the real data.

### Alternatives set aside (for now)

| Alternative | Why not today | When it would make sense |
|---|---|---|
| React + Vite | Too much setup and state management for one day | If the project continues and the UI grows |
| deck.gl | One more API to learn | If the MapLibre animation is not smooth enough |
| Streamlit | Limited UI and animation | If nobody on the team writes JavaScript |
| FastAPI + PostGIS | Too much infrastructure | For the real-time mode, after the hackathon |
| Leaflet | Slower with many points | If someone masters it and the data is small |

**Demo fallback:** if the front end fails, `web/data/processed/hotspots.geojson` can be dragged into [kepler.gl/demo](https://kepler.gl/demo) to get an animated map in 2 minutes.

---

## Architecture

```
                 ┌──────────────────── scripts/ (Python, run by make data) ─────────────────────┐
                 │                                                                              │
 NASA FIRMS ───► │ download_firms.py ─► data/raw/*.csv ─► harmonize.py ─► fires.py ─► exposure.py │
 (MODIS, VIIRS)  │                                           │              │            ▲      │
                 │                                           │              │            │      │
 WorldPop ─────► │ population.py ────────────────────────────┼──────────────┼────────────┤      │
 Open-Meteo ───► │ weather.py ───────────────────────────────┼──────────────┼────────────┘      │
 OpenStreetMap ► │ osm.py ───────────────────────────────────┼──────────────┤                   │
                 └───────────────────────────────────────────┼──────────────┼───────────────────┘
                                                             ▼              ▼
                                    web/data/processed/*.geojson|json + web/data/manifest.json
                                                             │
                                                             ▼
                                web/ (HTML + JS + MapLibre) ──► GitHub Pages ──► https://<domain>
```

1. **Download**: FIRMS CSVs (MODIS + VIIRS S-NPP, NOAA-20, NOAA-21) are saved in `data/raw/`.
2. **Harmonization**: both sensors are mapped to one schema (confidence, UTC datetime, FRP, brightness, resolution).
3. **Enrichment**: MODIS/VIIRS deduplication, grouping into fires, exposed population, wind, distances to water, roads and fire stations.
4. **Publication**: results are written to `web/data/processed/`, **already styled** (colors, sizes), and declared in `web/data/manifest.json`; they are versioned and published with the site.
5. **Display**: the front end reads the manifest and builds each layer with a generic loader; all filtering and animation happen in the browser.

---

## Project layout

```
ulinautas/
├── README.md
├── TODO.md                         # roles, tasks per role, waves, task details
├── Makefile                        # install / data / sample / test / serve
├── pyproject.toml, uv.lock         # dependencies (uv)
├── .python-version                 # 3.11
├── .env.example                    # FIRMS_MAP_KEY=
├── .gitignore                      # .env, data/raw/, .venv/, __pycache__/
├── docs/
│   ├── data_contract.md            # format of every data file + layer manifest
│   ├── wiki/                       # project wiki: overview, data sources, pipeline, front end, operations, status
│   └── schemas/                    # JSON schemas checked by CI
├── .github/
│   └── workflows/
│       ├── ci.yml                  # tests + contract validation on every PR
│       ├── deploy.yml              # publishes web/ to GitHub Pages on every push to main
│       ├── e2e.yml                 # validates the data served by the published URL
│       └── update-data.yml         # refreshes recent data every 30 min (only if valid)
│
├── data/
│   └── raw/                        # downloaded FIRMS CSVs (not versioned)
│
├── scripts/                        # BACKEND (B1–B4)
│   ├── config.py                   # area (bbox), dates, paths, risk thresholds
│   ├── make_sample.py              # sample data generated from the contract
│   ├── download_firms.py           # MODIS + VIIRS download from the FIRMS API
│   ├── harmonize.py                # MODIS / VIIRS normalization
│   ├── export_hotspots.py          # hotspots.geojson (already styled) + daily_summary.json
│   ├── dedup.py                    # MODIS / VIIRS deduplication
│   ├── fires.py                    # grouping into fires → fires.geojson
│   ├── series.py                   # hourly time series
│   ├── population.py               # WorldPop crop → population.tif / population.png
│   ├── weather.py                  # hourly wind and weather → weather.geojson
│   ├── exposure.py                 # exposed population + risk + wind → alerts.json
│   ├── osm.py                      # water, roads, fire stations + distances per fire
│   ├── make_manifest.py            # manifest.json: list of available layers
│   ├── validate.py                 # validates web/data/ against docs/schemas/
│   ├── check_site.py               # end-to-end check against the published URL
│   └── tests/
│
└── web/                            # FRONT END (F) — everything here is published
    ├── CNAME                       # custom domain (later)
    ├── index.html                  # page layout (map + panels + timeline)
    ├── style.css
    ├── config.js                   # demo area, data paths, basemap
    ├── map.js                      # the single MapLibre map instance
    ├── state.js                    # shared state (date, filters, playback hour, layers)
    ├── app.js                      # entry point: loads data, wires modules, controls and presenter keys
    ├── timeline.js                 # strip chart (fires per day) + playback engine
    ├── story.js                    # spark and peak, computed from the data, and their callouts
    ├── readouts.js                 # header figures: active fires, strongest fire
    ├── layers/
    │   └── loader.js               # generic loader: manifest → layers, temporal fading, rings, legend, popups
    └── data/
        ├── manifest.json           # available layers (generated by the backend)
        ├── sample/                 # sample data from the contract (front-end development)
        └── processed/              # pipeline outputs (versioned and published)
            ├── demo/               # fixed episode for playback
            └── live/               # last 48 h, refreshed by update-data.yml
```

### Layout rules

- **Scripts write only to `web/data/`**: the local site and the published site read the same relative paths.
- **Front-end paths are always relative** (`data/processed/hotspots.geojson`, never `/data/...`), so the site works on the custom domain and on `github.io/ulinautas/`.
- **One layer = one already-styled data file + one entry in `web/data/manifest.json`.** The generic front-end loader (`web/layers/loader.js`) displays it with no new code; the `active` field is the feature toggle.
- **One shared state** in `web/state.js`: modules read `state`, change it with `setState()` and react with `subscribe()`.
- **`data/raw/` is not versioned** (size); `web/data/processed/` is (the demo works without re-running anything).

---

## Data contract

| File | Content | Produced by |
|---|---|---|
| `manifest.json` | List of available layers, their type, legend and toggle | `make_manifest.py` |
| `hotspots.geojson` | One point per hotspot, MODIS and VIIRS harmonized | `export_hotspots.py`, completed by `dedup.py` / `fires.py` |
| `daily_summary.json` | Hotspots and FRP per day (feeds the calendar) | `export_hotspots.py` |
| `hourly_series.json` | Active hotspots and FRP per hour (timeline counter) | `series.py` |
| `fires.geojson` | One polygon per fire (grouped hotspots) | `fires.py`, completed by `osm.py` |
| `alerts.json` | One record per fire with exposed population and risk | `exposure.py` |
| `population.png` | Population density cropped to the area | `population.py` |
| `weather.geojson` | Wind, temperature, humidity, rain per hour | `weather.py` |
| `water.geojson`, `roads.geojson`, `fire_stations.geojson` | OpenStreetMap layers | `osm.py` |

Detailed schema of each file and MODIS / VIIRS field mapping: see [`docs/data_contract.md`](docs/data_contract.md).

### MODIS / VIIRS harmonization (summary)

| | MODIS | VIIRS | Harmonized |
|---|---|---|---|
| Resolution | ~1 km | ~375 m | `resolution_m` |
| Confidence | 0–100 | `low` / `nominal` / `high` | `low` / `medium` / `high` |
| Brightness | `brightness` | `bright_ti4` | `brightness_k` |
| Date | `acq_date` + `acq_time` | same | `timestamp_utc` (ISO 8601) |
| Double detection | — | — | a single hotspot, `detected_by: ["MODIS","VIIRS"]` |

---

## Getting started

Requirements: [uv](https://docs.astral.sh/uv/getting-started/installation/) (it installs Python 3.11 if needed) and a [FIRMS API key](https://firms.modaps.eosdis.nasa.gov/api/map_key/).

```bash
cp .env.example .env     # set FIRMS_MAP_KEY
make install             # uv sync → .venv with the locked dependencies
make test                # pytest
make sample              # sample data → web/data/sample/
make data                # run the pipeline in order → web/data/processed/
make serve               # front end at http://localhost:8000
```

Add a dependency with `uv add <package>` (`uv add --dev <package>` for dev-only tools) and commit `uv.lock` with it.

### Publishing
Every push to `main` deploys `web/` to GitHub Pages (`.github/workflows/deploy.yml`): https://maj-e.github.io/ulinautas/. The custom domain will be set in `web/CNAME` and in *Settings → Pages → Custom domain*. Recent data is refreshed automatically every 30 min (`.github/workflows/update-data.yml`, with `FIRMS_MAP_KEY` in the repository secrets).

---

## Team workflow

| Role | Folders |
|---|---|
| **B1–B4** — Backend | `scripts/`, `docs/`, `.github/workflows/ci.yml`, `e2e.yml`, `update-data.yml`, `Makefile` |
| **F** — Front end / DevOps | `web/`, `.github/workflows/deploy.yml`, domain |

- Branches: `feature/<task-id>-<name>` → PR to **`dev`** → `dev` is merged into **`main`** (published) once checked.
- One task in `TODO.md` = one branch = one short PR, merged only with green CI.
- `main` always works and is always published.

## Data sources

| Use | Source | Access |
|---|---|---|
| MODIS / VIIRS hotspots | [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov/) | API with MAP_KEY |
| Wind / weather | [Open-Meteo](https://open-meteo.com/) (historical archive, ERA5) | API, no key |
| Population | [WorldPop](https://www.worldpop.org/) 1 km | GeoTIFF per country |
| Water, roads, fire stations | [OpenStreetMap](https://www.openstreetmap.org/) | Overpass API |
| Relief | Terrarium tiles (AWS Open Data) | Tiles, no key |

## Team

- _Name_ — role
