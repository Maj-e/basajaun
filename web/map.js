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

// Se resuelve en cuanto el estilo está listo para recibir capas,
// sin esperar a que todas las teselas del fondo de mapa estén descargadas.
export const mapaListo = new Promise((resolve) => {
  if (map.isStyleLoaded()) resolve();
  else map.once("style.load", resolve);
});
