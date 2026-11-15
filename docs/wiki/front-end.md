# Using the data in the front end

The page is plain HTML + JavaScript with **MapLibre GL 4.7.1**, self-hosted in `web/vendor/` (BSD-3 license included); no framework, no build. It only reads static files.

The screen follows the validated mockup (`docs/mockup/`) and the [demo script](../demo-script.md): full-screen map, timeline strip along the bottom, two readouts, Map panel, alert panel and legend on the map. What each part does: [Features](features.md).

## Modules
| File | Role |
|---|---|
| `config.js` | the current episode (from `episodes.json`), base maps, layers switched on at start (`defaultLayers`), legend additions, stacking order, trail length |
| `map.js` | the single map: base maps (Topo relief, Satellite, Dark; cross-fade, never `setStyle`), graticule, towns, the satellite image of the day, `null` + error message when WebGL is unavailable |
| `layers/loader.js` | manifest → data → map layers; temporal fading; `ring` features; `glow`; layers that follow the clock (hotspots, zones per snapshot); legend; popups; layer list |
| `layers/perimeter.js` | fire perimeters as they were at the playback hour, rebuilt from the hotspots so far (same rule as `fires.py`) |
| `layers/particles.js`, `layers/wind_particles.js` | the `particles` layer type: animated surface wind on a canvas; frozen while the player is paused |
| `timeline.js` | strip chart from `daily_summary.json` (peak, last detection) and the playback engine (owns `state.hour`; stops at the end) |
| `story.js` | peak (day with most fires) and last detection, computed from the data |
| `alerts.js` | alert panel: one row per fire (region, people within 5 km, risk), click → the fire's detail (isolated on the map); type filters; rings on the map |
| `readouts.js` | active fires (last 24 h), strongest fire, total |
| `app.js` | wiring, episode selector, controls, presenter keys, `?demo=1` |

Presenter keys: `Space` play/pause, `P` peak day, `←`/`→` one hour, `R` back to the first day (keeps play / pause). The page **opens paused on the peak** and **stops at the last day**; `?demo=1` hides the demo banner (kept when switching episode). A tab on top of the timeline folds the chart.

Popups use human labels and units (`FIELDS` in `layers/loader.js`), scroll when long and pan the map so they stay clear of the header and the timeline.

**Satellite image of the day** (Map panel): NASA GIBS VIIRS true color for the playback day, dimmed so the fires stay brightest. Needs internet; the land outline is the offline fallback.

## How the page loads data
1. `web/config.js` reads `data/episodes.json` and picks the episode: `?episode=<id>`, else `default`. If the file cannot be loaded it silently falls back to Chile (known issue, see [`TODO.md`](../../TODO.md)).
2. `web/map.js` creates the single map, framed on the episode's `bbox`.
3. `web/app.js` calls `loadData()` (the episode's manifest + each layer switched on at start), builds the timeline, then adds the layers once the map style is ready; the other layers are downloaded quietly when idle.
4. `web/layers/loader.js` adds a source + layer per manifest entry according to its `type`; styles come **from the data**: `["get", "color"]`, `["get", "radius"]`, `["get", "border"]`…
5. The legend and the popups are generated from the manifest (`legend`, `popup` fields) plus `CONFIG.legendExtras`.
6. Each time `state.hour` changes, `setHour()` updates opacity and filters: hotspots fade over the trail, fires and zones show while `t_start <= hour < t_until`, perimeters are rebuilt, weather swaps to the current hour.

Which files exist for each episode, and what is in them: [Front-end layers](../frontend_layers.md) and the [data contract](../data_contract.md). Sample data for working offline: `web/data/sample/manifest.json`.

## Layer types the loader knows
| `type` | MapLibre rendering | Style properties read from features |
|---|---|---|
| `circle` | points; `ring: true` features drawn as rings; manifest `glow: true` adds a halo | `color`, `radius`, `border`, `opacity`, `ring` |
| `fill` | polygons + outline | `color`, `opacity` |
| `line` | lines | `color`, `width` |
| `image` | georeferenced image (needs `corners` in the manifest) | — |
| `arrows` | rotated symbols, flowing along the wind | `rotation`, `size`, `color` |
| `particles` | animated wind on a canvas, from `u` / `v` (m/s) per hour | layer-level `color` |

Layers with `t_start` (and optionally `t_until`) follow the clock; so do layers marked `temporal` (they carry `t`).

## Adding a layer (backend side, no front-end code)
1. Write a script that outputs a GeoJSON to `web/data/processed/` with the style properties above.
2. Add an entry to the manifest:
   ```json
   { "id": "roads", "name": "Roads", "file": "processed/roads.geojson", "type": "line",
     "active": false, "popup": ["name"], "legend": [{"color": "#555", "text": "Main road"}] }
   ```
3. Check it on the published site, then set `active: true`.

A new `type` is the only case that needs front-end work.

## Shared state
`web/state.js` holds `hour`, `playing`, `speed`, `basemap`, `satellite` and `layers` (id → visible). Modules change it with `setState()` and react with `subscribe()` — filters, calendar and timeline all go through it.

## Page areas
Stable ids: `#layer-list` (Map panel), `#alerts` (alert panel), `#legend`, `#timeline` with `#strip` (chart) and `#days`, `#episode-select`, `#status`.
