# Data sources

## NASA FIRMS — fire hotspots (in use)

**What it is:** each row is one satellite pixel where a thermal anomaly (likely a fire) was detected at a given time.

**Access:** REST API with a free `MAP_KEY` (see [Operations](operations.md#firms-api-key)).
```
https://firms.modaps.eosdis.nasa.gov/api/area/csv/{MAP_KEY}/{SOURCE}/{west},{south},{east},{north}/{DAYS}/{DATE}
```

**Sources we download** (`scripts/download_firms.py`):
| Base source | Instrument / satellite | Resolution |
|---|---|---|
| `MODIS` | MODIS on Terra and Aqua | ~1 km |
| `VIIRS_SNPP` | VIIRS on Suomi-NPP | ~375 m |
| `VIIRS_NOAA20` | VIIRS on NOAA-20 | ~375 m |
| `VIIRS_NOAA21` | VIIRS on NOAA-21 | ~375 m |

The script adds a suffix automatically: **`_NRT`** (near real time) for data less than 60 days old, **`_SP`** (standard processing, the archive) for older data. It requests **5-day chunks** and caches each source as a CSV in `data/raw/`.

**What the real data looks like** (first download, demo area, 1–14 Feb 2026):
| | MODIS | VIIRS |
|---|---|---|
| Rows | 97 | 355 (S-NPP) + 346 (NOAA-20) + 277 (NOAA-21) |
| `satellite` codes | `Terra`, `Aqua` | `N` (S-NPP), `N20` (NOAA-20), `N21` (NOAA-21) |
| `confidence` | number 0–100 | `l` / `n` / `h` |
| Brightness column | `brightness` (+ `bright_t31`) | `bright_ti4` (+ `bright_ti5`) |
| FRP (MW) | median 21.6, max 1111.1 | median ~4.5, max ~270 |

Other columns in both: `latitude`, `longitude`, `scan`, `track`, `acq_date`, `acq_time`, `instrument`, `version`, `frp`, `daynight`, `type`.

**Quirks to handle:**
- `acq_time` is an integer without leading zeros (`453` = 04:53 UTC) → pad with `zfill(4)`.
- The two instruments use **different confidence scales** → mapped to `low` / `medium` / `high` (see [`docs/data_contract.md`](../data_contract.md#firms-field-mapping--contract)).
- A fire seen by both instruments appears **twice** → deduplication step (W2-B1).
- `type` distinguishes presumed vegetation fires (`0`) from static sources (`2`: industrial sites…). In the demo data, **250 detections are `type 2`**, 231 of them in two ~1 km cells that fire every day (around 34.1° S 70.5° W and 33.3° S 70.7° W). **Proposal:** keep `type 0` only → **825 vegetation fires** (B1 to confirm).
- Detections are published roughly **3 hours after each satellite pass**; each satellite passes a few times a day.

**Volume:** 1,075 detections for 14 days ≈ 90 KB of CSV → the hotspot GeoJSON will stay well under 1 MB, so **one file is enough** (no per-day split).

## Planned sources

| Use | Source | Access | Task |
|---|---|---|---|
| Population density | WorldPop, 1 km, UN adjusted | GeoTIFF per country | W3-B3 |
| Wind and weather | Open-Meteo historical archive (ERA5) | API, no key | W3-B2 |
| Water, roads, fire stations | OpenStreetMap | Overpass API | W3-B4 |
| Relief | Terrarium tiles (AWS Open Data) | Tiles, no key | W3-F1 |
| Basemap | OpenFreeMap `positron` style | Vector tiles, no key | in use |

Update this page when a source is wired in: what it returns, its quirks, its volume.
