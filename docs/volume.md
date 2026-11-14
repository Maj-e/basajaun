# FIRMS volume — W0-B3

Measurement for the demo area and period defined by B2 in `scripts/config.py`. W1-B3 exports one GeoJSON or one file per day according to the decision below.

## Area and period

| Item | Value |
|---|---|
| BBOX (west, south, east, north) | `-72.0, -38.0, -70.0, -33.0` |
| Start | `2026-02-01` (inclusive) |
| End | `2026-02-14` (inclusive) |
| Days | 14 |
| Area API chunk | 5 days (`2026-02-01`, `2026-02-06`, `2026-02-11`) |

## Sources

`scripts/download_firms.py` (`api_source`) uses `_NRT` when the start date is less than 60 days old and `_SP` otherwise. On 2026-11-14 the February period is older than 60 days, so the four products are:

- `MODIS_SP`
- `VIIRS_SNPP_SP`
- `VIIRS_NOAA20_SP`
- `VIIRS_NOAA21_SP`

## Threshold

`BYTE_THRESHOLD` in `scripts/measure_volume.py` is `10 * 1024 * 1024` = **10,485,760 bytes** (10 MiB).

- Size at or below that threshold → **one single file** (`web/data/processed/hotspots.geojson`).
- Size above that threshold → **one file per day**.

The size that counts is the raw GeoJSON on disk (`data/raw/focos_bruto.geojson`), before deduplication. Properties follow `docs/data_contract.md`: `satellite`, `date`, `confidence`, `radius`, `stroke`. `frp` may be `null`.

## Result

Measured on 2026-11-14 with `python scripts/measure_volume.py`. The twelve CSV windows and `focos_bruto.geojson` are in `data/raw/` (gitignored). The console URL contains the map key; do not paste that log into the repo or the chat.

| Item | Value |
|---|---|
| Measured at | 2026-11-14 |
| Hotspots, total | 1075 |
| `MODIS_SP` | 97 |
| `VIIRS_SNPP_SP` | 355 |
| `VIIRS_NOAA20_SP` | 346 |
| `VIIRS_NOAA21_SP` | 277 |
| Raw GeoJSON | 271694 bytes |
| Heaviest day | 2026-02-12 (177 hotspots) |
| Heaviest day size | 44829 bytes |
| Decision | **one single file** |

271694 bytes is under the 10485760-byte threshold. W1-B3 publishes one file: `web/data/processed/hotspots.geojson`. It does not split the period into one file per day.

Hotspots per day:

| Date | Hotspots |
|---|---|
| 2026-02-01 | 38 |
| 2026-02-02 | 108 |
| 2026-02-03 | 25 |
| 2026-02-04 | 24 |
| 2026-02-05 | 41 |
| 2026-02-06 | 64 |
| 2026-02-07 | 40 |
| 2026-02-08 | 52 |
| 2026-02-09 | 55 |
| 2026-02-10 | 78 |
| 2026-02-11 | 86 |
| 2026-02-12 | 177 |
| 2026-02-13 | 164 |
| 2026-02-14 | 123 |

## Note for B1

**Decision: one single file.** W1-B3 writes `web/data/processed/hotspots.geojson` for the whole period. No daily GeoJSON files.

The real set has 1075 hotspots and weighs 271694 bytes. The sample in `web/data/sample/hotspots_sample.geojson` stays at **12** features. It only has to exercise the contract (both sensors and the three confidence levels). It does not have to copy the real count, and `scripts/make_sample.py` does not change.
