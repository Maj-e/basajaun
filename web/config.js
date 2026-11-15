// Front-end configuration. The episode (area, dates, data folder) comes from web/data/episodes.json (W4-B5).
export const CONFIG = {
  // Data root: `file` paths in the manifest are relative to this folder
  dataRoot: "data/",
  // Offline land outline (Natural Earth): the default basemap and the offline fallback
  land: "data/static/land.geojson",
  // NASA GIBS daily true-color imagery, synced with the playback day
  satellite: {
    tiles: "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/VIIRS_SNPP_CorrectedReflectance_TrueColor/default/{date}/GoogleMapsCompatible_Level9/{z}/{y}/{x}.jpg",
    maxzoom: 9,
    attribution: "Imagery: NASA GIBS / VIIRS",
  },
  // Base maps the user can pick (W3-F7). Static tiles: cached by the browser, never re-requested while the playback runs.
  // `paint` dims and desaturates the imagery so the fires stay the brightest thing on screen.
  // "dark" has no tiles: it is the offline land outline above, also what shows under the tiles while they load.
  basemaps: {
    default: "topo",
    options: [
      // Topo = terrain relief: open elevation tiles shaded by the GPU in dark tones.
      // Mapterhorn: Terrarium in lossless WebP, 512 px tiles (a quarter of the requests of 256 px tiles), served from a CDN.
      // 30 m worldwide, finer (down to 1 m lidar) where national agencies publish it.
      // Fallback if it ever goes down: AWS Open Data, 256 px PNG, maxzoom 15:
      //   https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png (attribution "Mapzen / AWS Terrain Tiles")
      { id: "topo", name: "Topo", maxzoom: 16, tileSize: 512, encoding: "terrarium",
        dem: "https://tiles.mapterhorn.com/{z}/{x}/{y}.webp",
        attribution: "<a href='https://mapterhorn.com/attribution'>© Mapterhorn</a>",
        paint: { "hillshade-exaggeration": 0.75, "hillshade-shadow-color": "#03060c", "hillshade-highlight-color": "#8aa0c4",
                 "hillshade-accent-color": "#0a1424", "hillshade-illumination-anchor": "map" } },
      { id: "satellite", name: "Satellite", maxzoom: 14, tileSize: 256,
        tiles: "https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2021_3857/default/g/{z}/{y}/{x}.jpg",
        // CC BY-NC-SA 4.0: free for non-commercial use with this exact attribution; commercial use needs an EOX licence
        attribution: "EOxCloudless https://cloudless.eox.at by EOX IT Services GmbH (Contains modified Copernicus Sentinel data 2021)",
        paint: { "raster-brightness-max": 0.62, "raster-saturation": -0.25, "raster-contrast": 0.1 } },
      { id: "dark", name: "Dark" },
    ],
  },
  // Map margins kept clear of the header and the timeline (mobile: taller header + panel bar)
  framePadding: window.matchMedia("(max-width: 760px)").matches
    ? { top: 170, bottom: 230, left: 16, right: 16 }
    : { top: 200, bottom: 200, left: 60, right: 380 }, // right: the map panel
  // Layer groups in the Layers tab, in this order; a layer not listed here goes to "Other"
  layerGroups: [
    { name: "Fire", ids: ["hotspots", "fires", "spread", "fire_risk", "evacuation"] },
    { name: "People", ids: ["population", "regions"] },
    { name: "Weather", ids: ["weather", "wind", "wind_particles"] },
    { name: "Water and terrain", ids: ["water", "rivers", "groundwater"] },
    { name: "Firefighting", ids: ["roads", "fire_stations", "water_points"] },
  ],
  // Layers shown when the page opens; every other active layer starts unchecked in the Layers panel
  // (design council: one place to look during playback)
  defaultLayers: ["hotspots", "fires", "roads", "groundwater", "wind_particles"],
  // Point layers that also get a heatmap when zoomed out (readability of dense episodes)
  heatmapLayers: ["hotspots"],
  // Fires stay visible this many hours after their detection, fading out
  trailHours: 24,
  // The backend "weather" layer is drawn as rain (blue, sized by mm/h, only where it rains). Exception to
  // "the style comes from the data": weather.geojson is shared with the wind and its colors are wind speed.
  rainLayer: { id: "weather", name: "Rain" },
  // Legend additions per layer (front-side styles, and what a size or a shape means); appended to the manifest legend
  legendExtras: {
    hotspots: [{ note: "Dot size grows with fire intensity" }],
    fires: [{ color: "#de2d26", text: "Fire outline (grouped hotspots)" },
            { note: "It grows with each detection. Faint once the fire has had no detections for 24 h: burned area, not active fire" }],
    spread: [{ color: "#fb6a4a", text: "Possible extent in 6 h" }, { note: "Estimate from wind + slope, not a forecast" }],
    wind: [{ note: "Arrow points where the wind blows; bigger = faster" }],
    weather: [{ color: "#9ecae1", text: "< 2 mm/h" }, { color: "#4292c6", text: "2–8 mm/h" }, { color: "#08519c", text: "> 8 mm/h" },
              { note: "Bigger, darker patch = heavier rain (current hour)" }],
  },
  // Stacking order, bottom to top (unknown layers go just under the hotspots)
  layerOrder: ["population", "groundwater", "regions", "water", "weather", "spread", "roads", "fires",
               "fire_stations", "water_points", "hotspots", "wind"],
  // Temporal layers that keep a trail; every other temporal layer (weather, wind) shows the current hour only
  trailLayers: ["hotspots"],
};

// ---------- Episode: ?episode=<id>, else the default of episodes.json ----------
const FALLBACK = { id: "chile-2026-02", name: "Chile–Argentina border · Feb 2026", bbox: [-72.0, -38.0, -70.0, -33.0], dir: "processed", manifest: "manifest.json" };
const doc = await fetch("data/episodes.json").then((r) => (r.ok ? r.json() : null)).catch(() => null);
// The live episode needs the Live button (W4-F1): not offered in the selector yet
const episodes = (doc?.episodes ?? [FALLBACK]).filter((e) => !e.live);
const wanted = new URLSearchParams(location.search).get("episode");
const episode = episodes.find((e) => e.id === wanted) ?? episodes.find((e) => e.id === doc?.default) ?? episodes[0];
const [w, s_, e_, n] = episode.bbox;
const padX = (e_ - w) * 0.15, padY = (n - s_) * 0.15;

Object.assign(CONFIG, {
  episodes,
  episode,
  bbox: episode.bbox,
  // Initial view: the episode area plus a margin
  view: [[w - padX, s_ - padY], [e_ + padX, n + padY]],
  manifest: `${CONFIG.dataRoot}${episode.manifest}`,
  dailySummary: `${CONFIG.dataRoot}${episode.dir}/daily_summary.json`,
  // Population alerts (scripts/exposure.py); missing file = no alerts shown
  alerts: `${CONFIG.dataRoot}${episode.dir}/alerts.json`,
  // Shown in the caption: the episode name without its date part
  areaName: episode.name.split(" · ")[0],
  // Reference towns, when the episode lists them
  places: episode.places ?? [],
});
