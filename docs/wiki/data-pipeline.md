# Data pipeline

Everything runs with **`make data`**: it executes the scripts below in order for one **episode** and **skips the ones that don't exist yet or that the episode skips** (`skip` in `web/data/episodes.json`).

```
FIRMS API ─► download_firms ─► data/raw/*.csv ─► export_hotspots (harmonize) ─► dedup ─► regions ─► fires ─► series
                                                                                                      │
 WorldPop ─► population ┐                                                                             ▼
 Open-Meteo ─► weather ─┤                    terrain (slope, land cover, optional)         fire_history (snapshots)
 OSM ─► osm ────────────┤                                                                             │
 Natural Earth ─► natural_earth_water (when OSM is skipped)                                           ▼
 EEA ─► groundwater ────┴────────────► spread ─► exposure (alerts) ─► risk_score (risk, evacuation) ─► compact ─► make_manifest ─► validate
```

Outputs go to the episode's folder under **`web/data/`** (`episodes/<id>/`, or `processed/` for the Chile episode; published with the site). Raw downloads stay in **`data/raw/`** (not versioned, one subfolder per episode).

## Steps

In the order `make data` runs them (`PIPELINE` in the `Makefile`).

| Step | Script | What it does → output |
|---|---|---|
| Download | `download_firms.py` | FIRMS API (MODIS + VIIRS) → `data/raw/{SOURCE}_{start}_{end}.csv`, reusing the CSVs already there |
| Export | `export_hotspots.py` (uses `harmonize.py`) | normalizes MODIS / VIIRS to one schema → `hotspots.geojson`, `daily_summary.json` |
| Deduplicate | `dedup.py` | the same fire seen by both sensors → one hotspot (`detected_by`) |
| Regions | `regions.py` | country and region on every hotspot (Natural Earth, geoBoundaries) → `regions.geojson` |
| Group into fires | `fires.py` | DBSCAN over space and time → `fires.geojson` + `fire_id` on the hotspots |
| Time series | `series.py` | hotspots → `hourly_series.json` |
| Population | `population.py` | WorldPop → `population.png` / `.tif` |
| Weather | `weather.py` | Open-Meteo → `weather.geojson` (hourly wind u/v, speed, rain on a 5×5 grid) |
| Terrain | `terrain.py` | slope and land cover per fire, only when its rasters are in `data/raw/` |
| Spread | `spread.py` | 6 h wind-driven spread ellipse per fire **snapshot** (`fire_history.py`) → `spread.geojson` |
| OSM | `osm.py` | Overpass → `water`, `rivers`, `roads`, `fire_stations`, `water_points` + distances per fire (`osm_options` trims large areas) |
| National water | `natural_earth_water.py` | water and rivers from Natural Earth, only for episodes that skip OSM |
| Aquifers | `groundwater.py` | groundwater bodies and ash-leachate risk (Europe) → `groundwater.geojson` |
| Alerts | `exposure.py` (+ `alert_types.py`) | fires + population + wind → typed alerts in `alerts.json` |
| Risk | `risk_score.py` | risk level and evacuation estimate per snapshot → `fire_risk.geojson`, `evacuation.geojson`, figures in `fires.geojson` |
| AI ignition risk | `ml_features.py` → `risk_ml.py` | weather, distances, population and slope on a 12 × 12 grid → daily ignition probability and levels → `ignition_risk.geojson`; runs before the manifest. See [AI module](ai-risk.md) |
| Compact | `compact.py` | 5-decimal coordinates, per-layer simplification, no indentation; last step before the manifest |
| Manifest | `make_manifest.py` | existing files → the episode's `manifest.json` (+ layer legends) |
| Validation | `validate.py` | everything → pass / fail against `docs/schemas/` |

**Fire snapshots** (`fire_history.py`, used by `spread.py` and `risk_score.py`): one snapshot every 6 h from a fire's first to its last detection. Each zone feature carries `t_start`, `t_until` and `last`; the last snapshot stays 24 h after the fire's last detection. The last snapshot equals the single polygon of `fires.geojson`.

## Configuration
The episode decides everything: `web/data/episodes.json` lists them (id, `bbox`, `start` / `end`, `dir`, `manifest`, optional `skip`, `min_confidence`, `thin`, `osm_options`). `scripts/config.py` reads it:
- **`EPISODE=<id> make data`** builds another episode (`make episode` shows the selected one); empty = the `default`.
- `BBOX`, `START_DATE`, `END_DATE` come from the episode; the `live` episode moves with the clock.
- paths `RAW`, `SAMPLE`, `PROCESSED`, risk and alert thresholds (`RISK_SCORE`, `ALERT_THRESHOLDS`)
- reads `FIRMS_MAP_KEY` from `.env` or the environment

The front end reads the same `episodes.json`, so a new episode needs no front-end change.

## Commands
```bash
make install   # uv sync: .venv with locked dependencies
make data      # full pipeline for the default episode (EPISODE=<id> for another)
make live      # fresh download of the last 48 h (not committed)
make sample    # sample data for front-end work
make test      # pytest
make serve     # site at http://localhost:8000 (no browser caching)
```
Run a single step: `uv run scripts/download_firms.py`.

## Rules
- A script writes **only** to the episode's folder under `web/data/` (or `data/raw/` for downloads).
- Every output follows [`docs/data_contract.md`](../data_contract.md) and carries an `updated_at` timestamp.
- Outputs are **already styled** (`color`, `radius`, …) and declared in the manifest.
- Tests never call FIRMS: they use small hand-written CSVs.
