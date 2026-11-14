# Front-end layers — what is ready to use

For **F** (front end). Every layer and data file below is **already published** and passes the contract validator (`scripts/validate.py`). Formats: [`data_contract.md`](data_contract.md). This file is updated by the backend in every PR that adds or changes something the front end can use (see the [changelog](#changelog)).

All paths are relative to `web/data/` (= `data/` on the site).

## Where to read the data

| File | What |
|---|---|
| `episodes.json` | the episodes, each with its `bbox`, dates, data folder and **own manifest**; `default` = the one to show first |
| `manifest.json` | Chile episode — what the current front page reads |
| `episodes/<id>/manifest.json` | the other episodes |
| `processed/live/manifest.json` | live mode, last 48 h, refreshed every 30 min (`live: true` in `episodes.json`) |

Every layer comes **already styled**: the loader only maps feature properties (`color`, `radius`, `border`, `opacity`, `width`, `rotation`, `size`) to MapLibre paint. `active: false` = published but switched off until checked on the site; turn it on in `scripts/make_manifest.py`. The Map panel shows one checkbox per active layer; layers not shown at start are downloaded only when their box is ticked.

## Episodes

| id | Name | Default | Front page today |
|---|---|---|---|
| `sierra-bermeja-2021-09` | Sierra Bermeja (Málaga) · Sep 2021 | ✅ | — (needs the selector, W4-F2) |
| `chile-2026-02` | Chile–Argentina border · Feb 2026 | | ✅ (`manifest.json`) |
| `los-angeles-2025-01` | Los Angeles · Jan 2025 | | — |
| `live` | Live · Iberian Peninsula · last 48 h | | — (needs the Live button, W4-F1) |

## Layers

✅ = in that episode's manifest · — = not available there

| id | Type | Active | Time | Sierra Bermeja | Chile | Los Angeles | Live | Popup fields | Style properties |
|---|---|---|---|---|---|---|---|---|---|
| `hotspots` | circle | ✅ | ✅ `t` | ✅ | ✅ | ✅ | ✅ | sensor, satellite, timestamp_utc, confidence, frp, country, region (Chile) | color, radius, border |
| `fires` | fill | ✅ | | ✅ | ✅ | ✅ | ✅ | see [fire properties](#fire-properties) | color, opacity |
| `weather` | circle | ✅ | ✅ `t` | ✅ | ✅ | ✅ | — | timestamp_utc, temperature, humidity, rain, speed | color, radius; also `u`, `v` (see [surface wind](#surface-wind)) |
| `wind` | **arrows** | ✅ | ✅ `t` | ✅ | ✅ | ✅ | — | timestamp_utc, speed, direction | rotation, size, color (drawn by the loader's `arrows` type) |
| `wind_particles` | **particles** | | ✅ `t` | ✅ | ✅ | ✅ | — | — | layer-level `color`; per point `u`, `v` (m/s) — **needs the `particles` type in the loader** |
| `spread` | fill | ✅ | | ✅ | ✅ | ✅ | — | fire_id, horizon_hours, wind_speed_kmh, wind_to_deg, slope_deg, spread_km, area_km2 | color, opacity |
| `population` | image | ✅ | | ✅ | ✅ | — | — | — | PNG + `corners` in the manifest |
| `water` | fill | ✅ | | ✅ | ✅ | — | — | name, kind (lake / reservoir) | color, opacity |
| `rivers` | line | ✅ | | ✅ | ✅ | — | — | name | color, width |
| `roads` | line | ✅ | | ✅ | ✅ | — | — | name, highway | color, width (by road type) |
| `fire_stations` | circle | ✅ | | ✅ | ✅ | — | — | name | color, radius, border |
| `water_points` | circle | ✅ | | ✅ | ✅ | — | — | name, kind (fire_water / hydrant / tank / well / spring / water_point) | color (by kind), radius, border |
| `regions` | fill | ✅ | | — | ✅ | — | — | country, region | color, opacity |
| `groundwater` | fill | ✅ | | ✅ | — (Europe only) | — | — | name, vulnerability, chemical_status, at_risk_chemical, geology | color, opacity (by vulnerability) |

### Fire properties
Each fire polygon in `fires.geojson` carries (a property can be missing or `null` when the input wasn't available for that episode):

| Field | Meaning |
|---|---|
| `fire_id`, `start`, `end`, `t_start`, `t_end` | identity and time span (ISO UTC / hours since 1970) |
| `n_hotspots`, `frp_max`, `area_km2` | size and intensity |
| `dist_road_km`, `dist_water_km`, `dist_fire_station_km` | accessibility: nearest road / water body / fire station |
| `dist_water_point_km` | nearest place where crews can load water (hydrant, tank, well, spring…) |
| `gw_body`, `gw_vulnerability`, `gw_chemical_status` | aquifer under the fire and how vulnerable it is to **ash leachate** (`high` = karst or already poor / at risk) — Europe only |
| `slope_deg`, `landcover` | terrain (W5-B3), only when `terrain.py` ran with its rasters |

### Surface wind
`weather.geojson` (read by `weather`, `wind` and `wind_particles`): one point per cell of a 5×5 grid over the episode bbox, **per hour** (`t`). The wind is the **surface wind at 10 m** above ground — one level, no profile:

| Field | Meaning |
|---|---|
| `speed`, `direction` | km/h, and degrees where the wind comes **from** (meteorological) |
| `u`, `v` | the same wind in **m/s, where it blows to**: `u` = east, `v` = north |

For particles: take the points of the current hour (`Math.floor(state.hour)`), sort them south → north then west → east, and pass `{nx, ny, west, south, east, north, cells: [{u, v}]}` to the particle field. The same `u` / `v` will feed fire spread later.

## Other data files

| File | Use | Shape |
|---|---|---|
| `…/alerts.json` | alert panel | `{updated_at, alerts: [{fire_id, risk, since, pop_1km, pop_5km, pop_10km, wind_toward_population, center, color}]}`, sorted most → least severe. Chile and Sierra Bermeja |
| `…/daily_summary.json` | calendar, timeline strip | `{updated_at, "YYYY-MM-DD": {hotspots, total_frp, modis, viirs, no_data}}` |
| `…/hourly_series.json` | counter, small chart | `{updated_at, series: [{t, count, total_frp}]}`, every whole hour |
| `episodes.json` | episode selector | see above |

## Ready to implement (data side done)

- **Fire sheet**: show the accessibility distances, the nearest water point and the aquifer risk (`gw_*`).
- **Wind particles (`particles` type)**: data ready in every episode with weather (`wind_particles`, `active: false`). Particle engine: Miguel's `wind_particles.js` from TerraFlow (`ui/js/wind_particles.js`: bilinear u/v + light curl, own canvas, `pointer-events: none`) — expects exactly the field above; respect `prefers-reduced-motion`.
- **Live button (W4-F1)**: `processed/live/manifest.json` is published and refreshed every 30 min.
- **Episode selector (W4-F2)**: `episodes.json`, start with `default`.

## Changelog

| Date | Change |
|---|---|
| 2026-11-14 | Rivers moved out of `water` into their own `rivers` line layer (a fill layer closed each river into a bogus polygon); the validator now rejects a layer whose geometries don't match its type |
| 2026-11-14 | Surface wind `u`, `v` (m/s) on every `weather.geojson` point; new `wind_particles` layer, type `particles` (Chile, Sierra Bermeja, Los Angeles) |
| 2026-11-14 | `regions` layer and `country` / `region` on hotspots, Chile (W5-B3, #46) |
| 2026-11-14 | New layers `water_points` (Chile, Sierra Bermeja) and `groundwater` (Sierra Bermeja); fire fields `dist_water_point_km`, `gw_body`, `gw_vulnerability`, `gw_chemical_status` (W3-B7) |
| 2026-11-14 | Live mode published in `processed/live/` (W4-B4); episodes Sierra Bermeja (default) and Los Angeles (W4-B5); Chile `alerts.json` and `population` |
