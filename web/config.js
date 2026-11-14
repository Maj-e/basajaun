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
  // Map margins kept clear of the header and the timeline (mobile: taller header + panel bar)
  framePadding: window.matchMedia("(max-width: 760px)").matches
    ? { top: 170, bottom: 230, left: 16, right: 16 }
    : { top: 130, bottom: 200, left: 60, right: 60 },
  // Layers shown when the page opens; every other active layer starts unchecked in the Layers panel
  // (design council: one place to look during playback)
  defaultLayers: ["hotspots", "fires"],
  // Point layers that also get a heatmap when zoomed out (readability of dense episodes)
  heatmapLayers: ["hotspots"],
  // Episodes offered by the Demo button, in pitch order (missing ones are skipped)
  demoEpisodes: ["sierra-bermeja-2021-09", "spain-2025-08", "chile-2026-02"],
  // Fires stay visible this many hours after their detection, fading out
  trailHours: 24,
  // The backend "weather" layer is drawn as rain (blue, sized by mm/h, only where it rains). Exception to
  // "the style comes from the data": weather.geojson is shared with the wind and its colors are wind speed.
  rainLayer: { id: "weather", name: "Rain" },
  // Legend additions per layer (front-side styles, and what a size or a shape means); appended to the manifest legend
  legendExtras: {
    hotspots: [{ note: "Dot size grows with fire intensity" }],
    fires: [{ color: "#de2d26", text: "Fire outline (grouped hotspots)" }],
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
