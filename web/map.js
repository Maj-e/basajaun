import { CONFIG } from "./config.js";

// Single map instance: every other module imports it from here.
export const map = new maplibregl.Map({
  container: "map",
  style: CONFIG.basemap,
  bounds: CONFIG.bbox,
  fitBoundsOptions: { padding: 20 },
  attributionControl: { compact: true },
});

map.addControl(new maplibregl.NavigationControl(), "top-right");
map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-left");

// Resolves as soon as the style can accept layers,
// without waiting for every basemap tile to download.
export const mapReady = new Promise((resolve) => {
  if (map.isStyleLoaded()) resolve();
  else map.once("style.load", resolve);
});
