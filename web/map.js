import { CONFIG } from "./config.js";

// Única instancia del mapa: los demás módulos la importan desde aquí.
export const map = new maplibregl.Map({
  container: "mapa",
  style: CONFIG.basemap,
  bounds: CONFIG.bbox,
  fitBoundsOptions: { padding: 20 },
  attributionControl: { compact: true },
});

map.addControl(new maplibregl.NavigationControl(), "top-right");
map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-left");

// Se resuelve cuando el fondo de mapa está cargado y se pueden agregar capas.
export const mapaListo = new Promise((resolve) => map.on("load", resolve));
