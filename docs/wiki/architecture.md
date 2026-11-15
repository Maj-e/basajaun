# Architecture

How the project is built and why. The short version is in the [README](../../README.md); this page keeps the reasoning.

## Stack

| Part | Technology | Role |
|---|---|---|
| Data processing | **Python 3.11** · pandas · geopandas · shapely · rasterio · rasterstats · scikit-learn · requests | Download, harmonize and enrich the data |
| Python environment | **[uv](https://docs.astral.sh/uv/)** (`pyproject.toml` + `uv.lock`) | Installs in seconds, pinned versions |
| Data exchange | Static **GeoJSON / JSON / PNG** files | Contract between the scripts and the front end |
| Front end | **HTML + JavaScript** (ES modules, no framework, no build) | User interface |
| Map | **MapLibre GL JS 4.7.1** (self-hosted in `web/vendor/`) | Vector map, filters, animation, layers |
| Hosting | **GitHub Pages** | Published automatically on every push to `main`, free HTTPS |
| CI/CD | **GitHub Actions** | Tests and validation on every PR, deploy of `web/`, automatic data refresh |

## Why this stack

- **No server to maintain.** Data is computed with Python, locally or in GitHub Actions every 30 min (as fresh as FIRMS itself, which publishes ~3 h after each satellite pass), and published as files. The page depends on no live API: nothing can go down during the demo.
- **Python for geospatial work.** Projections, rasters, clustering and zonal statistics are much simpler in Python than in JavaScript.
- **MapLibre for the map.** Free, no API key, renders tens of thousands of points smoothly and filters / animates them with expressions, without reloading data.
- **No framework, no build.** Nobody loses time configuring npm, Webpack or Docker. It runs with `make serve`.
- **Teams that don't block each other.** The data contract separates the backend from the front end: the front end moves forward with sample data while the scripts produce the real data.

## Alternatives set aside (for now)

| Alternative | Why not today | When it would make sense |
|---|---|---|
| React + Vite | Too much setup and state management for one day | If the project continues and the UI grows |
| deck.gl | One more API to learn | If the MapLibre animation is not smooth enough |
| Streamlit | Limited UI and animation | If nobody on the team writes JavaScript |
| FastAPI + PostGIS | Too much infrastructure | For the real-time mode, after the hackathon |
| Leaflet | Slower with many points | If someone masters it and the data is small |

**Demo fallback:** if the front end fails, `web/data/processed/hotspots.geojson` can be dragged into [kepler.gl/demo](https://kepler.gl/demo) to get an animated map in 2 minutes.

## Data flow

```
                 ┌────────────────────── scripts/ (Python, run by `make data`) ───────────────────────┐
 NASA FIRMS ───► │ download_firms ─► harmonize ─► export_hotspots ─► dedup ─► regions ─► fires ─► series│
 (MODIS, VIIRS)  │                                                                                   │
 WorldPop ─────► │ population ───────────────────────────────────────────────┐                        │
 Open-Meteo ───► │ weather ──► terrain ─► spread (per snapshot, fire_history) │                        │
 OpenStreetMap ► │ osm / natural_earth_water / groundwater ──────────────────┼─► exposure ─► risk_score│
                 │                                                           │      (alerts, evacuation)│
                 │                              compact ─► make_manifest ─► validate                  │
                 └───────────────────────────────────────────────────────────┬───────────────────────┘
                                                                             ▼
                          web/data/episodes/<id>/*.geojson|json|png + manifest.json
                                                                             │
                              web/ (HTML + JS + MapLibre) ──► GitHub Pages ──► the published site
```

1. **Download**: FIRMS CSVs (MODIS Terra/Aqua + VIIRS S-NPP, NOAA-20, NOAA-21) are saved in `data/raw/`.
2. **Harmonization**: both sensors are mapped to one schema (confidence, UTC datetime, FRP, brightness, resolution), MODIS / VIIRS double detections are merged into one hotspot.
3. **Enrichment**: grouping into fires, exposed population, wind, accessibility, aquifers, then the derived zones (6 h spread, evacuation, risk score), computed **per fire snapshot** so they change with the playback. The AI module (`ml_features.py` → `risk_ml.py`, branch `IA`) adds a daily ignition-risk grid; see [AI module](ai-risk.md).
4. **Publication**: results are written per **episode** to `web/data/episodes/<id>/`, **already styled** (colors, sizes), and declared in that episode's `manifest.json`; they are versioned and published with the site.
5. **Display**: the front end reads `episodes.json`, then the episode's manifest, and builds each layer with a generic loader; all filtering and animation happen in the browser.

## Layout rules

- **Scripts write only to `web/data/`**: the local site and the published site read the same relative paths.
- **Front-end paths are always relative** (`data/episodes/…`, never `/data/...`), so the site works on a custom domain and under `github.io/<repo>/`.
- **One layer = one already-styled data file + one entry in the manifest.** The generic front-end loader (`web/layers/loader.js`) displays it with no new code; the `active` field is the feature toggle.
- **One shared state** in `web/state.js`: modules read `state`, change it with `setState()` and react with `subscribe()`.
- **`data/raw/` is not versioned** (size); `web/data/episodes/` is (the demo works without re-running anything), except `processed/live/`, which the refresh workflow publishes.
- **The deploy stamps the front end with a version** (`scripts/version_assets.py`), so a deploy never mixes old and new modules; `make serve` sends `no-store` for the same reason.

## Files each episode publishes

| File | Content | Produced by |
|---|---|---|
| `manifest.json` | layers available, their type, legend and toggle | `make_manifest.py` |
| `hotspots.geojson` | one point per hotspot, MODIS and VIIRS harmonized | `export_hotspots.py`, `dedup.py`, `fires.py` |
| `fires.geojson` | one polygon per fire (grouped hotspots) + risk and accessibility figures | `fires.py`, `osm.py`, `risk_score.py` |
| `spread.geojson`, `evacuation.geojson`, `fire_risk.geojson` | zones per fire snapshot (`t_start`, `t_until`) | `spread.py`, `risk_score.py`, `fire_history.py` |
| `alerts.json` | typed alerts per fire | `exposure.py`, `alert_types.py` |
| `daily_summary.json`, `hourly_series.json` | hotspots and FRP per day / hour (timeline) | `export_hotspots.py`, `series.py` |
| `weather.geojson` | hourly wind, rain, temperature on a 5×5 grid | `weather.py` |
| `population.png` | population density | `population.py` |
| `ignition_risk.geojson` | daily AI ignition risk on a 12 × 12 grid (branch `IA`) | `ml_features.py`, `risk_ml.py` |
| `roads`, `rivers`, `water`, `fire_stations`, `water_points`, `groundwater`, `regions` `.geojson` | context layers | `osm.py`, `natural_earth_water.py`, `groundwater.py`, `regions.py` |

## Project layout

```
├── README.md · TODO.md · Makefile · pyproject.toml + uv.lock · .env.example
├── docs/
│   ├── wiki/                  # project wiki (start at docs/wiki/README.md)
│   ├── data_contract.md       # format of every data file
│   ├── frontend_layers.md     # layers ready for the front end + changelog
│   ├── demo-script.md · licenses.md · volume.md
│   ├── schemas/               # JSON schemas checked by CI
│   └── media/                 # README images (the demo GIF goes here)
├── scripts/                   # BACKEND: the pipeline, one script per step (+ tests/)
│   ├── config.py              # episode (bbox, dates, skips), paths, thresholds
│   ├── download_firms · harmonize · export_hotspots · dedup · regions · fires · series
│   ├── population · weather · terrain · osm · natural_earth_water · groundwater
│   ├── spread · exposure · alert_types · risk_score · fire_history
│   ├── ml_features · risk_ml      # AI ignition risk (branch IA, pending merge)
│   ├── compact · make_manifest · validate · make_sample
│   └── serve · version_assets · check_site · measure_volume
├── .github/workflows/         # ci (tests + contract), deploy (Pages), e2e (published URL), update-data (live, every 30 min)
├── data/raw/                  # downloaded FIRMS CSVs and other raw inputs (not versioned)
└── web/                       # FRONT END: everything here is published
    ├── index.html · style.css · config.js
    ├── app.js · map.js · state.js · timeline.js · story.js · readouts.js · alerts.js
    ├── layers/                # loader.js (manifest → layers), perimeter.js, particles.js, wind_particles.js
    ├── vendor/                # MapLibre GL JS, self-hosted
    └── data/                  # episodes.json, episodes/<id>/, processed/live/, static/, sample/
```
