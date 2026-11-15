# Data contract — Ulinautas

Frozen in task **W0-B1** (B1 + F). Every script and the front end follow it; any change goes through B1 (contract owner) and is announced to the whole team. The validator (`scripts/validate.py`, W1-B4) checks it in CI.

### `web/data/processed/hotspots.geojson` — one Feature per hotspot
```json
{
  "type": "Feature",
  "geometry": { "type": "Point", "coordinates": [-70.6483, -33.4569] },
  "properties": {
    "id": "VIIRS_N20_20260214_0742_-33.4569_-70.6483",
    "sensor": "VIIRS",
    "satellite": "NOAA-20",
    "timestamp_utc": "2026-02-14T07:42:00Z",
    "date": "2026-02-14",
    "t": 493927.7,
    "confidence": "high",
    "frp": 18.4,
    "brightness_k": 342.1,
    "day_night": "N",
    "resolution_m": 375,
    "detected_by": ["VIIRS"],
    "fire_id": null,
    "color": "#d7301f",
    "radius": 6.2,
    "border": "#222222",
    "country": "Chile",
    "region": "Maule"
  }
}
```
`t` = hours since 1970 (number), for fast filtering in the animation. `country` and `region` are written by `regions.py` (geoBoundaries ADM1): the name of the country and the first-level region that contain the point, or `null` when the point falls outside every polygon. They are optional in the schema so episodes generated before that step still validate.

### `web/data/processed/daily_summary.json`
```json
{ "updated_at": "2026-02-14T08:00:00Z", "2026-02-14": { "hotspots": 412, "total_frp": 9832.5, "modis": 120, "viirs": 292, "no_data": false } }
```

### `web/data/processed/alerts.json`
```json
{ "updated_at": "2026-02-14T08:00:00Z", "alerts": [
  { "fire_id": 12, "type": "population", "risk": "critical", "since": "2026-02-14T07:42:00Z", "message": "≈23,400 people within 5 km",
    "pop_1km": 800, "pop_5km": 23400, "pop_10km": 51000, "wind_toward_population": false, "center": [-70.65, -33.46], "color": "#a50f15" },
  { "fire_id": 12, "type": "smoke", "risk": "high", "since": "2026-02-14T09:00:00Z", "message": "Smoke toward ≈12,000 people (wind 25 km/h from W)",
    "smoke_people": 12000, "wind_kmh": 25.0, "pop_1km": 800, "pop_5km": 23400, "pop_10km": 51000, "wind_toward_population": false,
    "center": [-70.65, -33.46], "color": "#d7301f" }
] }
```
An object (not a bare list) so it carries `updated_at` like every other file; `alerts` is sorted from most to least severe. One fire can have several alerts, one per **`type`** (W3-B8), each with a short `message`:

| `type` | When | Extra fields |
|---|---|---|
| `population` | people within 1 / 5 / 10 km of the fire (W3-B1) | — |
| `wind` | strongest surface wind (10 m) during the fire's active hours ≥ 30 km/h (high) / 45 km/h (critical) | `wind_kmh` |
| `smoke` | people in a ±30° sector downwind, as far as the wind carries the smoke in 2 h (max 25 km); calm (< 5 km/h) = none | `smoke_people`, `wind_kmh` |
| `contamination` | fire or its 6 h spread over a medium / high vulnerability aquifer (ash leachate, Europe only) | `gw_body`, `gw_vulnerability` |

Every type also carries the fire's `pop_1km` / `pop_5km` / `pop_10km`, `center` and `since`. Thresholds: `ALERT_THRESHOLDS` in `scripts/config.py`. Alerts need `population.tif`: an episode without population has no `alerts.json`.

### `web/data/processed/hourly_series.json`
```json
{ "updated_at": "2026-02-14T08:00:00Z", "series": [{ "t": 491950, "count": 12, "total_frp": 340.5 }, { "t": 491951, "count": 0, "total_frp": 0.0 }] }
```
One entry per **whole** hour of the period (`t` = hours since 1970, integer), zero-filled: feeds the timeline counter and chart.

### `web/data/episodes.json` — fire episodes (W4-B5)
```json
{
  "updated_at": "2026-02-14T08:00:00Z",
  "default": "sierra-bermeja-2021-09",
  "episodes": [
    { "id": "sierra-bermeja-2021-09", "name": "Sierra Bermeja (Málaga) · Sep 2021", "bbox": [-5.6, 36.3, -4.6, 36.9],
      "start": "2021-09-08", "end": "2021-09-20", "dir": "episodes/sierra-bermeja-2021-09",
      "manifest": "episodes/sierra-bermeja-2021-09/manifest.json" },
    { "id": "chile-2026-02", "name": "Chile–Argentina border · Feb 2026", "bbox": [-72.0, -38.0, -70.0, -33.0],
      "start": "2026-02-01", "end": "2026-02-14", "dir": "processed", "manifest": "manifest.json" },
    { "id": "los-angeles-2025-01", "name": "Los Angeles · Jan 2025", "bbox": [-119.0, 33.6, -117.4, 34.6],
      "start": "2025-01-06", "end": "2025-01-16", "dir": "episodes/los-angeles-2025-01",
      "manifest": "episodes/los-angeles-2025-01/manifest.json", "skip": ["osm"] }
  ]
}
```
Each episode has its own data folder (`dir`) and **its own manifest** (`manifest`), both relative to `web/data/`; the manifest's `file` paths point into that folder. The front end loads `default` first; switching episode = loading another `manifest`. `bbox` is west, south, east, north. `skip` lists pipeline steps that episode doesn't run (front end ignores it).
A **live** episode (`"live": true`, no `start` / `end`) covers today and yesterday; its data in `processed/live/` is published by `update-data.yml` every 30 min and never committed.
Build an episode with `make data EPISODE=<id>`; without `EPISODE`, the default one. Chile keeps its files in `processed/` + `manifest.json`, which the current front end reads, until the episode selector (W4-F2) reads this file.

### Surface wind in `weather.geojson`
One point per grid cell (5×5 over the bbox) and per hour. Wind is the **surface wind at 10 m** above ground, one level only:
`speed` (km/h) + `direction` (degrees, where the wind comes **from**), and the same wind as `u`, `v` (m/s, where it blows **to**; `u` = east, `v` = north). Particles and fire spread models read `u` / `v`.

### Combined risk + evacuation (W3-B11)
`scripts/risk_score.py` adds to every fire in `fires.geojson`: `risk_score` (0–100), `risk_level` (`low` / `medium` / `high` / `extreme`), `risk_factors` (`fire`, `people`, `smoke`, `strong wind`), `evacuate_people` (fire + 1 km + 6 h spread) and `warn_people` (the rest within 5 km). Four factors of 0–2 points; the level comes from the total, raised by the combinations: smoke + people ≥ medium, fire + strong wind ≥ high, all four = extreme. Layers `fire_risk.geojson` (fires coloured by level) and `evacuation.geojson` (zones). Thresholds: `RISK_SCORE` in `scripts/config.py`.

### Rules shared by every file
- **Style computed by the backend:** each Feature carries its display properties (`color`, `radius`, `border`, `opacity`, `rotation`, `size`, `width` depending on the layer type). The front end never picks colors.
- **Timestamp:** each JSON file has `updated_at` (ISO 8601 UTC) at root level (in GeoJSON: a property of the `FeatureCollection`). The front end shows "Data from DD/MM HH:MM".
- **Temporal layers:** features carry `t` (hours since 1970, number) for the timeline.

### `web/data/manifest.json` — layer list
Generated by `scripts/make_manifest.py`. **Only layers whose file exists are listed.** Adding a layer = adding a file + its entry here.
```json
{
  "updated_at": "2026-02-14T08:00:00Z",
  "layers": [
    {
      "id": "hotspots",
      "name": "Fire hotspots",
      "file": "processed/hotspots.geojson",
      "type": "circle",
      "temporal": true,
      "active": true,
      "popup": ["sensor", "satellite", "timestamp_utc", "confidence", "frp"],
      "legend": [{"color": "#d7301f", "text": "High confidence"}, {"color": "#fc8d59", "text": "Medium confidence"}, {"color": "#fdcc8a", "text": "Low confidence"}]
    },
    {
      "id": "population",
      "name": "Population density",
      "file": "processed/population.png",
      "type": "image",
      "corners": [[-72.0, -33.0], [-70.0, -33.0], [-70.0, -38.0], [-72.0, -38.0]],
      "temporal": false,
      "active": false,
      "legend": [{"color": "#fee5d9", "text": "< 10 people/km²"}, {"color": "#a50f15", "text": "> 1000 people/km²"}]
    }
  ]
}
```
`file` paths are relative to `web/data/`. What is published per episode, for the front end: [`frontend_layers.md`](frontend_layers.md). Layer types: `circle`, `fill`, `line`, `image`, `arrows`, `particles` (new: animated surface wind, front-end task). A new type = a front-end task.

`active` is the **feature toggle**: a layer stays `false` until it has been checked on the published URL.

### FIRMS field mapping → contract
| Contract | MODIS (FIRMS CSV) | VIIRS (FIRMS CSV) |
|---|---|---|
| `lat` / `lon` | `latitude` / `longitude` | `latitude` / `longitude` |
| `timestamp_utc` | `acq_date` + `acq_time` (`HHMM`) | same |
| `satellite` | `satellite`: `Terra` / `Aqua` (or `T` / `A`) | `satellite`: `N` → S-NPP, `N20` / `1` → NOAA-20, `N21` → NOAA-21 |
| `confidence` | `confidence` 0–100: `<30` low · `30–79` medium · `≥80` high | `confidence`: `l`/`low` → low · `n`/`nominal` → medium · `h`/`high` → high |
| `frp` | `frp` (MW) | `frp` (MW) |
| `brightness_k` | `brightness` | `bright_ti4` |
| `day_night` | `daynight` | `daynight` |
| `resolution_m` | `1000` | `375` |

> Check the `satellite` codes against the first real download (W1-B2) and update this table if they differ.
