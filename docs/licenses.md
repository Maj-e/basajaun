# Licences and things to keep in mind

What each data source and map service allows, the attribution it needs, and what to review before the project goes beyond a non-commercial hackathon demo.

Status column: **checked** = read from the provider's own page while building W3-F7 (2026-11-15); **to verify** = stated from general knowledge, re-check the provider's page before relying on it.

## Base maps (front end, `CONFIG.basemaps` in `web/config.js`)

| Use | Source | Licence / terms | Attribution | Status |
|---|---|---|---|---|
| Topo (default): terrain relief | Mapterhorn (`tiles.mapterhorn.com`), Terrarium in lossless WebP, 512 px, up to z16 | Built from open-data sources, each with its own licence (e.g. CC BY 4.0, open government licences; list in `download.mapterhorn.com/attribution.json`); code is BSD-3. **The public endpoint states no usage policy or rate limit**; no API key | "© Mapterhorn" linking to https://mapterhorn.com/attribution (as its TileJSON asks) | checked; usage terms of the free endpoint **unclear**, ask the project or self-host |
| Topo fallback | AWS Open Data, Terrain Tiles (Terrarium, 256 px PNG, up to z15) | Open data, no API key | "Mapzen / AWS Terrain Tiles" | to verify the exact source credits; URL kept as a comment in `config.js` |
| Satellite (cloud-free) | EOX Sentinel-2 cloudless 2021 (`tiles.maps.eox.at`) | **CC BY-NC-SA 4.0**; non-commercial use unrestricted while the attribution is kept; commercial use needs an *EOX Commercial Attribution-RestrictedUse 1.2* licence; no sub-licensing or resale by default | "EOxCloudless https://cloudless.eox.at by EOX IT Services GmbH (Contains modified Copernicus Sentinel data 2021)" | checked |
| Dark | Natural Earth land outline (`data/static/land.geojson`) | Public domain | "Land: Natural Earth" | to verify |
| Image of the day | NASA GIBS, VIIRS SNPP corrected reflectance | NASA open data policy; no rate limit stated | "Imagery: NASA GIBS / VIIRS"; NASA asks for: *"We acknowledge the use of imagery provided by services from NASA's Global Imagery Browse Services (GIBS), part of NASA's Earth Science Data and Information System (ESDIS)."* | checked |

Dropped options and why:
- **Esri World Topo** (`server.arcgisonline.com`): deprecated, no longer updated, and its terms without an ArcGIS API key are unclear. Do not use.
- **OpenTopoMap** official server: in "survival mode" (no tiles above zoom 13, data from Jan 2023) and its author plans to drop raster tiles. Not reliable.
- **tile.openstreetmap.org**: its policy forbids heavy use and prefetching, and asks for an identifying User-Agent and a visible attribution. Not meant for an app's default basemap.
- **NASA GIBS Blue Marble**: open and cloud-free, but ~500 m per pixel: too blurry at fire scale.

## Data sources (pipeline and layers)

| Data | Provider | Licence | Attribution | Status |
|---|---|---|---|---|
| Fire hotspots (MODIS, VIIRS) | NASA FIRMS | NASA open data; ~3 h latency | "NASA FIRMS" | to verify |
| Population | WorldPop | CC BY 4.0 | "WorldPop" | to verify |
| Weather, wind, rain | Open-Meteo | CC BY 4.0; free API for non-commercial use, commercial use needs a paid plan | "Weather data by Open-Meteo.com" | to verify |
| Water, roads, fire stations | OpenStreetMap | ODbL 1.0 | "© OpenStreetMap contributors" | to verify |
| Land outline | Natural Earth | Public domain | "Natural Earth" | to verify |
| Groundwater | EEA | Check the dataset's own licence | "EEA" | to verify |
| Map library | MapLibre GL JS 4.7.1 (`web/vendor/`) | BSD-3-Clause | none required | to verify |

## To keep in mind for the future

1. **Non-commercial only (today).** The Sentinel-2 cloudless basemap (CC BY-NC-SA) and Open-Meteo's free tier both exclude commercial use. If the project is ever sold, offered as a paid service or used by a company, get an EOX licence and an Open-Meteo plan, or switch those two sources.
2. **ShareAlike.** CC BY-SA / ODbL derivatives must be shared under the same licence. Anything derived from OSM data (the water, roads and fire-station layers) keeps ODbL; tell users when a derived dataset is published.
3. **Attribution must stay visible.** The map's attribution control shows the basemap credits; the "About the data" panel (W5-F3) should list every source above. Do not hide or shorten the EOX text.
4. **Tile servers can change.** The Mapterhorn, EOX and NASA endpoints are public and best-effort (Mapterhorn is a community project with no stated limits: for real traffic, serve its PMTiles archive from our own hosting; the AWS URL in `config.js` is the quick fallback). If one disappears or starts blocking, the Dark basemap (offline) keeps the map usable. For a real deployment, host the tiles (PMTiles / own server) instead of depending on third parties.
5. **Year of the mosaic.** The EOX layer is the 2021 mosaic (`s2cloudless-2021_3857`); newer years may exist. When updating it, update the year in the attribution too.
6. **Do not bulk-download tiles.** Several providers forbid prefetching or offline "save area". The only prefetch in the app is the next-day NASA tiles for the current view, which is small and short-lived.
7. **No API keys.** Everything used today needs none. If a provider with a key is adopted later, keep the key out of the repo (server side or an allowed-domains key).
8. **Re-check every "to verify" row** before a public launch, and write the date next to it.
