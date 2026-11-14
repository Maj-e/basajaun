# Data pipeline

Everything runs with **`make data`**: it executes the scripts below in order and **skips the ones that don't exist yet**, so it works at every stage of the project.

```
FIRMS API ──► download_firms.py ──► data/raw/*.csv
                                         │
                                         ▼
                    export_hotspots.py (uses harmonize.py)
                                         │
              ┌──────────────────────────┼──────────────────────────┐
              ▼                          ▼                          ▼
     hotspots.geojson          daily_summary.json         dedup.py → fires.py
                                                                    │
     WorldPop ─► population.py ─┐                                   ▼
     Open-Meteo ─► weather.py ──┼──────────────► exposure.py ─► alerts.json
     OSM ─► osm.py ─────────────┘
                                         │
                       make_manifest.py ─► web/data/manifest.json
                       validate.py      ─► checks everything against the contract
```

All outputs go to **`web/data/processed/`** (published with the site). Raw downloads stay in **`data/raw/`** (not versioned).

## Steps

| Step | Script | Input → output | Status |
|---|---|---|---|
| Download | `download_firms.py` | FIRMS API → `data/raw/{SOURCE}_{start}_{end}.csv` | ✅ working |
| Normalize | `harmonize.py` | MODIS / VIIRS rows → common schema | W1-B1 |
| Export | `export_hotspots.py` | raw CSVs → `hotspots.geojson`, `daily_summary.json` | W1-B3 |
| Deduplicate | `dedup.py` | same fire seen by MODIS and VIIRS → one hotspot | W2-B1 |
| Group into fires | `fires.py` | hotspots → `fires.geojson` + `fire_id` | W2-B2 |
| Time series | `series.py` | hotspots → `hourly_series.json` | W2-B3 |
| Population | `population.py` | WorldPop → `population.png` / `.tif` | W3-B3 |
| Weather | `weather.py` | Open-Meteo → `weather.geojson` | W3-B2 |
| Risk and alerts | `exposure.py` | fires + population + wind → `alerts.json` | W3-B1 |
| OSM | `osm.py` | Overpass → `water`, `roads`, `fire_stations` | W3-B4 |
| Manifest | `make_manifest.py` | existing files → `manifest.json` | W1-B4 |
| Validation | `validate.py` | everything → pass / fail against `docs/schemas/` | W1-B4 |

## Configuration
`scripts/config.py`:
- `BBOX = (-72.0, -38.0, -70.0, -33.0)` — west, south, east, north (south-central Chile)
- `START_DATE`, `END_DATE` = `2026-02-01` → `2026-02-14`
- paths `RAW`, `SAMPLE`, `PROCESSED`
- reads `FIRMS_MAP_KEY` from `.env` or the environment

When the area changes, also update `bbox` in `web/config.js` so the map frames it.

## Commands
```bash
make install   # uv sync: .venv with locked dependencies
make data      # full pipeline
make sample    # sample data for front-end work (W0-B1)
make test      # pytest
make serve     # site at http://localhost:8000
```
Run a single step: `uv run scripts/download_firms.py`.

## Rules
- A script writes **only** to `web/data/processed/` (or `data/raw/` for downloads).
- Every output follows [`docs/data_contract.md`](../data_contract.md) and carries an `updated_at` timestamp.
- Outputs are **already styled** (`color`, `radius`, …) and declared in the manifest.
- Tests never call FIRMS: they use small hand-written CSVs.
