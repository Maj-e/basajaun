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
| `galicia-2025-08` | Galicia · Aug 2025 (1 km cells) | | — |
| `chile-2026-02` | Chile–Argentina border · Feb 2026 | | ✅ (`manifest.json`) |
| `live` | Live · Iberian Peninsula · last 48 h | | — (needs the Live button, W4-F1) |

## Layers

✅ = in that episode's manifest · — = not available there

`galicia-2025-08` (Galicia, 1 km cells; replaces the whole-peninsula `spain-2025-08`, too heavy for the browser, and the short-lived north-west one) has: `hotspots`, `regions`, `fires`, `fire_risk`, `evacuation`, `spread`, `population`, `wind`, `weather`, `wind_particles`, `water`, `rivers`, `groundwater`, `ignition_risk`. No OSM roads / stations / water points yet (the Overpass download was not reachable when it was built: `osm_options` in `episodes.json` already limits it to main roads, no hydrants), no slope or land cover.

| id | Type | Active | Time | Sierra Bermeja | Chile | Live | Popup fields | Style properties |
|---|---|---|---|---|---|---|---|---|
| `hotspots` | circle | ✅ | ✅ `t` | ✅ | ✅ | ✅ | sensor, satellite, timestamp_utc, confidence, frp, country, region (Chile) | color, radius, border |
| `fires` | fill | ✅ | | ✅ | ✅ | ✅ | see [fire properties](#fire-properties) | color, opacity |
| `weather` | circle | ✅ | ✅ `t` | ✅ | ✅ | — | timestamp_utc, temperature, humidity, rain, speed | color, radius; also `u`, `v` (see [surface wind](#surface-wind)) |
| `wind` | **arrows** | ✅ | ✅ `t` | ✅ | ✅ | — | timestamp_utc, speed, direction | rotation, size, color (drawn by the loader's `arrows` type) |
| `wind_particles` | **particles** | ✅ | ✅ `t` | ✅ | ✅ | — | — | layer-level `color`; per point `u`, `v` (m/s) — drawn by the loader's `particles` type (`layers/particles.js`) |
| `fire_risk` | fill | | | ✅ | ✅ | — | fire_id, risk_level, risk_score, risk_factors, evacuate_people, warn_people | color, opacity (by risk level) |
| `evacuation` | fill | | | ✅ | ✅ | — | fire_id, evacuate_people, warn_people | color, opacity |
| `spread` | fill | ✅ | | ✅ | ✅ | — | fire_id, horizon_hours, wind_speed_kmh, wind_to_deg, slope_deg, spread_km, area_km2 | color, opacity |
| `population` | image | ✅ | | ✅ | ✅ | — | — | PNG + `corners` in the manifest |
| `water` | fill | ✅ | | ✅ | ✅ | — | name, kind (lake / reservoir) | color, opacity |
| `rivers` | line | ✅ | | ✅ | ✅ | — | name | color, width |
| `roads` | line | ✅ | | ✅ | ✅ | — | name, highway | color, width (by road type) |
| `fire_stations` | circle | ✅ | | ✅ | ✅ | — | name | color, radius, border |
| `water_points` | circle | ✅ | | ✅ | ✅ | — | name, kind (fire_water / hydrant / tank / well / spring / water_point) | color (by kind), radius, border |
| `regions` | fill | ✅ | | — | ✅ | — | country, region | color, opacity |
| `groundwater` | fill | ✅ | | ✅ | — (Europe only) | — | name, vulnerability, chemical_status, at_risk_chemical, geology | color, opacity (by vulnerability) |
| `ignition_risk` | fill | ✅ | ✅ `t` (one grid per day, `hold_hours: 24`) | ✅ | ✅ | — | cell_id, reference_date, risk_level, risk_pct, drivers, recommended_action | color, opacity (by level); see [AI module](wiki/ai-risk.md) |

### Fire properties
Each fire polygon in `fires.geojson` carries (a property can be missing or `null` when the input wasn't available for that episode):

| Field | Meaning |
|---|---|
| `fire_id`, `start`, `end`, `t_start`, `t_end` | identity and time span (ISO UTC / hours since 1970) |
| `n_hotspots`, `frp_max`, `area_km2` | size and intensity |
| `dist_road_km`, `dist_water_km`, `dist_fire_station_km` | accessibility: nearest road / water body / fire station |
| `dist_water_point_km` | nearest place where crews can load water (hydrant, tank, well, spring…) |
| `gw_body`, `gw_vulnerability`, `gw_chemical_status` | aquifer under the fire and how vulnerable it is to **ash leachate** (`high` = karst or already poor / at risk) — Europe only |
| `risk_level`, `risk_score`, `risk_factors` | combined risk (W3-B11): `low` / `medium` / `high` / `extreme`, score 0–100, which factors are on (`fire`, `people`, `smoke`, `strong wind`) |
| `evacuate_people`, `warn_people` | people in fire + 1 km + 6 h spread (evacuate) / the rest within 5 km (warning) |
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
| `…/alerts.json` | alert panel | `{updated_at, alerts: [{fire_id, type, risk, since, message, pop_1km, pop_5km, pop_10km, wind_toward_population, center, color, …}]}`, sorted most → least severe. **`type`**: `population` / `wind` (`wind_kmh`) / `smoke` (`smoke_people`, `wind_kmh`) / `contamination` (`gw_body`, `gw_vulnerability`); a fire can have one alert per type. Chile, Sierra Bermeja, Spain Aug 2025 |
| `…/daily_summary.json` | calendar, timeline strip | `{updated_at, "YYYY-MM-DD": {hotspots, total_frp, modis, viirs, no_data}}` |
| `…/hourly_series.json` | counter, small chart | `{updated_at, series: [{t, count, total_frp}]}`, every whole hour |
| `episodes.json` | episode selector | see above |

## Ready to implement (data side done)

- **Fire sheet**: show the accessibility distances, the nearest water point and the aquifer risk (`gw_*`).
- **Risk + evacuation**: `fire_risk` colours each fire by its combined level (legend explains the combinations), `evacuation` draws the zone; both `active: false`. Good candidates for the fire sheet: `risk_level`, `risk_factors`, `evacuate_people`.
- **Alert types (W3-F5)**: `type` + ready-to-show `message` on every alert; icon / chip per type, colour by `risk`. Every type keeps `pop_5km`, `center`, `since`, so the current panel already lists them (as population figures).
- **Live button (W4-F1)**: `processed/live/manifest.json` is published and refreshed every 30 min.
- **Episode selector (W4-F2)**: `episodes.json`, start with `default`.

## Changelog

| Date | Change |
|---|---|
| 2026-11-15 | `spread`, `evacuation` and `fire_risk` now have **one polygon per fire snapshot** (every 6 h from the first to the last detection, `scripts/fire_history.py`): each feature carries `t_start` and, except the fire's last one, `t_until`; the front shows it while `t_start <= hour < t_until`. Zone, people to evacuate and risk level therefore change with the playback. Each feature also has `last`; the last snapshot of a fire stays until **24 h after its last detection** (`ACTIVE_HOURS`), then spread, evacuation and risk disappear and the perimeter (`fires`) stays at 60 % of its opacity as burned area. The last snapshot equals the old single polygon, `fires.geojson` and the alerts are unchanged; scripts that read the zones use the features with `last: true` |
| 2026-11-15 | New layer `ignition_risk` (AI module): a 12 × 12 grid with one score per cell and day, `temporal` with the new manifest field `hold_hours: 24` (a temporal feature stays visible that many hours; default 1). Published for every episode, switched on in the manifest and on at start (`defaultLayers`), drawn at the bottom of the stack (`layerOrder`). The map now repaints only when the playback hour crosses a whole hour |
| 2026-11-15 | `fires` shows each perimeter **as it was at the playback hour**: the front rebuilds it from the hotspots detected so far (`web/layers/perimeter.js`, same rule as `fires.py`: convex hull + 500 m), so scrubbing back shrinks it. `fires.geojson` is unchanged (final shapes: used for clicks, figures and the other scripts) |
| 2026-11-15 | When the episode goes on for a day or more after the last hotspot, the timeline marks **Last detection** (dashed line) and labels the empty tail *No detections · burned area only* (Sierra Bermeja: 12 → 20 Sep) |
| 2026-11-15 | The player **stops at the last day** instead of looping (the burned area stays on the map); Play from the end starts over from the first day |
| 2026-11-15 | The wind particles move only while the player plays; paused, they freeze into a still image (before, they kept moving after Pause, which looked like the fire kept evolving) |
| 2026-11-15 | `wind_particles` is on by default too; `R` (restart) goes to the first day and no longer starts playing by itself |
| 2026-11-15 | Default episode back to Sierra Bermeja (Málaga); the page opens **paused on the peak** with `roads` and `groundwater` on (`CONFIG.defaultLayers`); spread, evacuation and risk polygons now appear only once their fire has started, so scrubbing back hides them (before, they stayed on at every hour) |
| 2026-11-15 | Episodes kept for the demo: Sierra Bermeja (Málaga), Galicia (default) and Chile; Los Angeles removed (the layer table no longer has its column) |
| 2026-11-15 | Lighter GeoJSON in every episode (`scripts/compact.py`, new last step before the manifest): coordinates rounded to 5 decimals (~1 m) and no indentation; same fires, same properties. `spread.geojson` of the NW Spain episode 8.2 → 1.8 MB, whole episode 20 → 13 MB; Chile 9.4 → 8.5 MB |
| 2026-11-15 | Episode `spain-2025-08` (whole peninsula, 27 MB) replaced by `galicia-2025-08` (Galicia, 5 MB, 238 fires, 494 alerts, risk score and evacuation): the national one was too heavy for a smooth map; fires outside Galicia (Castilla y León, Portugal, Extremadura) are no longer in it |
| 2026-11-15 | `particles` type in the loader (`layers/particles.js` + Miguel's TerraFlow engine `layers/wind_particles.js`); `wind_particles` active in every episode with weather; still image under reduced motion |
| 2026-11-15 | `spread` fixed outside Chile: ellipses were drawn at about half their size (fixed Chile UTM zone); `area_km2` now matches the polygon. Evacuation and contamination alerts regenerated |
| 2026-11-15 | Combined risk score + evacuation (W3-B11): layers `fire_risk`, `evacuation`; fire fields `risk_*`, `evacuate_people`, `warn_people` (Chile, Sierra Bermeja, Spain Aug 2025) |
| 2026-11-15 | Typed alerts (W3-B8): `type` + `message` on every alert; new `wind`, `smoke`, `contamination` alerts (Chile 129 alerts, Sierra Bermeja 16, Spain Aug 2025 1,437) |
| 2026-11-14 | Rivers moved out of `water` into their own `rivers` line layer (a fill layer closed each river into a bogus polygon); the validator now rejects a layer whose geometries don't match its type |
| 2026-11-14 | Surface wind `u`, `v` (m/s) on every `weather.geojson` point; new `wind_particles` layer, type `particles` (Chile, Sierra Bermeja, Los Angeles) |
| 2026-11-14 | `regions` layer and `country` / `region` on hotspots, Chile (W5-B3, #46) |
| 2026-11-14 | New layers `water_points` (Chile, Sierra Bermeja) and `groundwater` (Sierra Bermeja); fire fields `dist_water_point_km`, `gw_body`, `gw_vulnerability`, `gw_chemical_status` (W3-B7) |
| 2026-11-14 | Live mode published in `processed/live/` (W4-B4); episodes Sierra Bermeja (default) and Los Angeles (W4-B5); Chile `alerts.json` and `population` |
