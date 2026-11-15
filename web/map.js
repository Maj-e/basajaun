import { CONFIG } from "./config.js";

// Single map instance (or null when WebGL is unavailable): every other module imports it from here.
export let map = null;
export let mapError = null;

// Graticule around the episode: one line per degree (every 0.5° for small areas)
const grid = { type: "FeatureCollection", features: [] };
{
  const [w, s, e, n] = CONFIG.bbox;
  const step = Math.max(e - w, n - s) < 3 ? 0.5 : 1;
  const x0 = Math.floor((w - 5) / step) * step, x1 = Math.ceil((e + 5) / step) * step;
  const y0 = Math.floor((s - 5) / step) * step, y1 = Math.ceil((n + 5) / step) * step;
  for (let x = x0; x <= x1; x += step) grid.features.push({ type: "Feature", geometry: { type: "LineString", coordinates: [[x, y0], [x, y1]] } });
  for (let y = y0; y <= y1; y += step) grid.features.push({ type: "Feature", geometry: { type: "LineString", coordinates: [[x0, y], [x1, y]] } });
}

// Base maps (W3-F7): every raster source and layer is declared up front, only the chosen one is visible.
// MapLibre downloads tiles only for visible layers, so declaring them costs nothing, and switching never calls setStyle()
// (that would wipe the data layers the loader adds).
const tiled = CONFIG.basemaps.options.filter((b) => b.tiles || b.dem);
// A hillshade (elevation tiles) fades through its exaggeration, a raster through its opacity
const fadeProp = (b) => (b.dem ? "hillshade-exaggeration" : "raster-opacity");
const fullValue = (b) => (b.dem ? b.paint["hillshade-exaggeration"] : 1);
const baseSources = Object.fromEntries(tiled.map((b) => [`base-${b.id}`, b.dem
  ? { type: "raster-dem", tiles: [b.dem], tileSize: b.tileSize, maxzoom: b.maxzoom, encoding: b.encoding, attribution: b.attribution }
  : { type: "raster", tiles: [b.tiles], tileSize: b.tileSize, maxzoom: b.maxzoom, attribution: b.attribution }]));
const baseLayers = tiled.map((b) => {
  const on = b.id === CONFIG.basemaps.default;
  const paint = { ...b.paint, [fadeProp(b)]: on ? fullValue(b) : 0, [`${fadeProp(b)}-transition`]: { duration: 400 } };
  if (!b.dem) paint["raster-fade-duration"] = 0;
  return { id: `base-${b.id}`, type: b.dem ? "hillshade" : "raster", source: `base-${b.id}`,
    layout: { visibility: on ? "visible" : "none" }, paint };
});

const style = {
  version: 8,
  sources: {
    land: { type: "geojson", data: CONFIG.land, attribution: "Land: Natural Earth · Fires: NASA FIRMS" },
    grid: { type: "geojson", data: grid },
    ...baseSources,
    "sat-a": { type: "raster", tiles: [CONFIG.satellite.tiles.replace("{date}", "2026-02-01")], tileSize: 256, maxzoom: CONFIG.satellite.maxzoom, attribution: CONFIG.satellite.attribution },
    "sat-b": { type: "raster", tiles: [CONFIG.satellite.tiles.replace("{date}", "2026-02-01")], tileSize: 256, maxzoom: CONFIG.satellite.maxzoom },
  },
  layers: [
    { id: "ocean", type: "background", paint: { "background-color": "#070c16" } },
    { id: "grid", type: "line", source: "grid", paint: { "line-color": "#1a2538", "line-width": 1 } },
    { id: "land", type: "fill", source: "land", paint: { "fill-color": "#131c2b" } },
    ...baseLayers,
    // Dimmed and desaturated so the fires stay the brightest thing on screen
    // Double buffer: the next day loads in the hidden layer, then cross-fades in at once (no tile-by-tile squares)
    ...["sat-a", "sat-b"].map((id) => ({ id, type: "raster", source: id, layout: { visibility: "none" },
      paint: { "raster-opacity": 0, "raster-opacity-transition": { duration: 500 }, "raster-fade-duration": 0,
               "raster-brightness-max": 0.55, "raster-saturation": -0.35, "raster-contrast": 0.1 } })),
    { id: "land-edge", type: "line", source: "land", paint: { "line-color": "#26344b", "line-width": 1.2 } },
  ],
};

try {
  map = new maplibregl.Map({
    container: "map",
    style,
    bounds: CONFIG.view,
    fitBoundsOptions: { padding: CONFIG.framePadding },
    attributionControl: { compact: true },
    dragRotate: false,
  });
  CONFIG.places.forEach(([name, lon, lat]) => {
    const el = document.createElement("div");
    el.className = "city";
    el.textContent = name;
    new maplibregl.Marker({ element: el, anchor: "left" }).setLngLat([lon, lat]).addTo(map);
  });
} catch (err) {
  // Typically WebGL disabled or unavailable: the rest of the page keeps working
  map = null;
  mapError = err;
}

// Resolves when the style can accept layers (does not wait for every tile).
export const mapReady = new Promise((resolve, reject) => {
  if (!map) return reject(mapError);
  if (map.isStyleLoaded()) resolve(map);
  else map.once("style.load", () => resolve(map));
});

// ---------- Base map switch ----------
let currentBase = CONFIG.basemaps.default;
let baseToken = 0;

// Cross-fade to another base map. The new one loads while still invisible and only fades in once its tiles are
// there (or after 2.5 s, e.g. offline), so the user never sees a half-drawn map. "dark" = no raster layer.
export function setBasemap(id) {
  if (!map || !map.getLayer("land") || id === currentBase) return;
  const token = ++baseToken;
  const next = `base-${id}`;
  currentBase = id;
  const fadeOutOthers = () => {
    tiled.forEach((b) => {
      const lid = `base-${b.id}`;
      if (lid === next || !map.getLayer(lid)) return;
      map.setPaintProperty(lid, fadeProp(b), 0);
      setTimeout(() => { if (lid !== `base-${currentBase}`) map.setLayoutProperty(lid, "visibility", "none"); }, 450);
    });
  };
  if (!map.getLayer(next)) return fadeOutOthers();      // "dark": just fade the rasters out
  const nextOpt = tiled.find((b) => `base-${b.id}` === next);
  // Barely visible, not 0: MapLibre skips the tiles of a fully transparent layer
  map.setPaintProperty(next, fadeProp(nextOpt), 0.01);
  map.setLayoutProperty(next, "visibility", "visible");
  let done = false;
  const reveal = () => {
    if (done || baseToken !== token) return;
    done = true;
    map.off("sourcedata", check);
    map.setPaintProperty(next, fadeProp(nextOpt), fullValue(nextOpt));
    fadeOutOthers();
  };
  const check = () => { if (map.isSourceLoaded(next)) reveal(); };
  map.on("sourcedata", check);
  setTimeout(reveal, 2500);
  check();
}

// ---------- Satellite image of the day (NASA GIBS), double-buffered ----------
const tileUrl = (date) => CONFIG.satellite.tiles.replace("{date}", date);
let front = "sat-a", back = "sat-b";
let frontDate = null, pendingDate = null, wantVisible = false;
const listeners = new Set();
export const onSatelliteDate = (fn) => listeners.add(fn);

function show(id, on) {
  map.setLayoutProperty(id, "visibility", on ? "visible" : "none");
}

// Show or hide the image; keep it on the playback day without ever showing a half-loaded day.
export function updateSatellite(visible, date) {
  if (!map || !map.getLayer("sat-a")) return;
  if (visible !== wantVisible) {
    wantVisible = visible;
    if (!visible) { show("sat-a", false); show("sat-b", false); pendingDate = null; return; }
    if (frontDate) { show(front, true); map.setPaintProperty(front, "raster-opacity", 1); }
  }
  if (!visible || !date || date === frontDate || date === pendingDate) return;
  // Load the new day in the hidden buffer
  pendingDate = date;
  map.getSource(back).setTiles([tileUrl(date)]);
  // 1 %, not 0: MapLibre treats a fully transparent layer as hidden and would not download its tiles
  map.setPaintProperty(back, "raster-opacity", 0.01);
  show(back, true);
  const target = back;
  const swapWhenLoaded = () => {
    if (pendingDate !== date) return map.off("sourcedata", swapWhenLoaded); // a newer day was asked meanwhile
    if (!map.isSourceLoaded(target)) return;
    map.off("sourcedata", swapWhenLoaded);
    map.setPaintProperty(target, "raster-opacity", 1);
    const old = front;
    map.setPaintProperty(old, "raster-opacity", 0);
    setTimeout(() => { if (old !== front) show(old, false); }, 550);
    [front, back] = [target, old];
    frontDate = date; pendingDate = null;
    listeners.forEach((fn) => fn(date));
    prefetchNextDay(date);
  };
  map.on("sourcedata", swapWhenLoaded);
  swapWhenLoaded();
}

// Warm the browser cache with the next day's tiles for the current view, so the next swap is quick.
function prefetchNextDay(date) {
  const next = new Date(Date.parse(`${date}T00:00:00Z`) + 86400000).toISOString().slice(0, 10);
  const z = Math.max(0, Math.min(CONFIG.satellite.maxzoom, Math.floor(map.getZoom() + 1)));
  const b = map.getBounds(), n = 2 ** z;
  const tx = (lon) => Math.floor(((lon + 180) / 360) * n);
  const ty = (lat) => { const r = (lat * Math.PI) / 180; return Math.floor(((1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2) * n); };
  const [x0, x1, y0, y1] = [tx(b.getWest()), tx(b.getEast()), ty(b.getNorth()), ty(b.getSouth())];
  if ((x1 - x0 + 1) * (y1 - y0 + 1) > 60) return; // zoomed far out: not worth it
  for (let x = x0; x <= x1; x++) for (let y = y0; y <= y1; y++) {
    new Image().src = tileUrl(next).replace("{z}", z).replace("{x}", x).replace("{y}", y);
  }
}
