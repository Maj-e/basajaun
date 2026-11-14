// Entry point: wires the modules together. Each wave adds its import here (filters, calendar…).
import { map, mapReady } from "./map.js";
import { CONFIG } from "./config.js";
import { layers, loadLayers } from "./layers/loader.js";

const status = document.getElementById("status");

mapReady
  .then(loadLayers)
  .then(() => {
    status.textContent = CONFIG.manifest.includes("sample") ? "Sample data" : "Live data";
  })
  .catch((err) => {
    console.error(err);
    status.textContent = "Data unavailable";
  });

// Only report errors from our own layers (not from a basemap tile).
map.on("error", (e) => {
  if (e.sourceId && layers.has(e.sourceId)) {
    console.error(e.error);
    status.textContent = `Layer unavailable: ${layers.get(e.sourceId).layer.name}`;
  }
});
