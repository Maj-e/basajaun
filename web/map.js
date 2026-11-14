import { CONFIG } from "./config.js";

// Single map instance (or null when WebGL is unavailable): every other module imports it from here.
export let map = null;
export let mapError = null;

const grid = { type: "FeatureCollection", features: [] };
for (let lon = -76; lon <= -66; lon++) grid.features.push({ type: "Feature", geometry: { type: "LineString", coordinates: [[lon, -41], [lon, -30]] } });
for (let lat = -41; lat <= -30; lat++) grid.features.push({ type: "Feature", geometry: { type: "LineString", coordinates: [[-76, lat], [-66, lat]] } });

const style = {
  version: 8,
  sources: {
    land: { type: "geojson", data: CONFIG.land, attribution: "Land: Natural Earth · Fires: NASA FIRMS" },
    grid: { type: "geojson", data: grid },
    satellite: { type: "raster", tiles: [CONFIG.satellite.tiles.replace("{date}", "2026-02-01")], tileSize: 256, maxzoom: CONFIG.satellite.maxzoom, attribution: CONFIG.satellite.attribution },
  },
  layers: [
    { id: "ocean", type: "background", paint: { "background-color": "#070c16" } },
    { id: "grid", type: "line", source: "grid", paint: { "line-color": "#1a2538", "line-width": 1 } },
    { id: "land", type: "fill", source: "land", paint: { "fill-color": "#131c2b" } },
    // Dimmed and desaturated so the fires stay the brightest thing on screen
    { id: "satellite", type: "raster", source: "satellite", layout: { visibility: "none" },
      paint: { "raster-brightness-max": 0.55, "raster-saturation": -0.35, "raster-contrast": 0.1 } },
    { id: "land-edge", type: "line", source: "land", paint: { "line-color": "#26344b", "line-width": 1.2 } },
  ],
};

try {
  map = new maplibregl.Map({
    container: "map",
    style,
    bounds: CONFIG.view,
    fitBoundsOptions: { padding: { top: 130, bottom: 200, left: 60, right: 60 } },
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

let satelliteDate = null;
// Show or hide the NASA daily image, and keep it on the playback day.
export function updateSatellite(visible, date) {
  if (!map || !map.getLayer("satellite")) return;
  map.setLayoutProperty("satellite", "visibility", visible ? "visible" : "none");
  if (visible && date && date !== satelliteDate) {
    satelliteDate = date;
    map.getSource("satellite").setTiles([CONFIG.satellite.tiles.replace("{date}", date)]);
  }
}
