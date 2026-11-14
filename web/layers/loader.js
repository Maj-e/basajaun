// Generic layer loader (W1-F1).
// Reads the manifest and builds each enabled layer according to its `type`, using the style carried by each feature.
// Adding a layer = one data file + one manifest entry: this file does not change.
import { map } from "../map.js";
import { CONFIG } from "../config.js";

// One builder per layer type. A new type (e.g. "arrows" in W3-F1) = one more entry here.
const BUILDERS = {
  circle: (layer) => {
    addGeojsonSource(layer);
    map.addLayer({
      id: layer.id,
      type: "circle",
      source: layer.id,
      paint: {
        "circle-color": ["coalesce", ["get", "color"], "#888888"],
        "circle-radius": ["coalesce", ["get", "radius"], 5],
        "circle-stroke-color": ["coalesce", ["get", "stroke"], "#ffffff"],
        "circle-stroke-width": 1.5,
        "circle-opacity": ["coalesce", ["get", "opacity"], 0.9],
      },
    });
    return [layer.id];
  },

  fill: (layer) => {
    addGeojsonSource(layer);
    map.addLayer({
      id: layer.id,
      type: "fill",
      source: layer.id,
      paint: {
        "fill-color": ["coalesce", ["get", "color"], "#888888"],
        "fill-opacity": ["coalesce", ["get", "opacity"], 0.35],
      },
    });
    map.addLayer({
      id: `${layer.id}-outline`,
      type: "line",
      source: layer.id,
      paint: { "line-color": ["coalesce", ["get", "color"], "#888888"], "line-width": 1.5 },
    });
    return [layer.id, `${layer.id}-outline`];
  },

  line: (layer) => {
    addGeojsonSource(layer);
    map.addLayer({
      id: layer.id,
      type: "line",
      source: layer.id,
      paint: {
        "line-color": ["coalesce", ["get", "color"], "#888888"],
        "line-width": ["coalesce", ["get", "width"], 1.5],
      },
    });
    return [layer.id];
  },

  image: (layer) => {
    map.addSource(layer.id, { type: "image", url: dataUrl(layer.file), coordinates: layer.corners });
    map.addLayer({ id: layer.id, type: "raster", source: layer.id, paint: { "raster-opacity": 0.6 } });
    return [layer.id];
  },
};

const dataUrl = (file) => CONFIG.dataRoot + file;

function addGeojsonSource(layer) {
  map.addSource(layer.id, { type: "geojson", data: dataUrl(layer.file) });
}

// Layers actually loaded: id → { layer, mapLayerIds }. Used later by the layer panel and the filters.
export const layers = new Map();

export async function loadLayers() {
  const response = await fetch(CONFIG.manifest);
  if (!response.ok) throw new Error(`Manifest unavailable (${response.status})`);
  const manifest = await response.json();

  for (const layer of manifest.layers.filter((l) => l.enabled)) {
    const build = BUILDERS[layer.type];
    if (!build) {
      console.warn(`Unknown layer type: "${layer.type}" (${layer.id})`);
      continue;
    }
    const mapLayerIds = build(layer);
    layers.set(layer.id, { layer, mapLayerIds });
    if (layer.popup?.length) enablePopup(layer, mapLayerIds[0]);
  }

  map.addControl(new Legend([...layers.values()].map((l) => l.layer)), "bottom-right");
  return manifest;
}

function enablePopup(layer, mapLayerId) {
  map.on("mouseenter", mapLayerId, () => (map.getCanvas().style.cursor = "pointer"));
  map.on("mouseleave", mapLayerId, () => (map.getCanvas().style.cursor = ""));
  map.on("click", mapLayerId, (e) => {
    const props = e.features[0].properties;
    const rows = layer.popup
      .filter((field) => props[field] !== undefined)
      .map((field) => `<tr><th>${field}</th><td>${props[field]}</td></tr>`)
      .join("");
    new maplibregl.Popup()
      .setLngLat(e.lngLat)
      .setHTML(`<strong>${layer.name}</strong><table class="popup">${rows}</table>`)
      .addTo(map);
  });
}

// Legend built from the manifest, as a MapLibre control.
class Legend {
  constructor(layersWithLegend) {
    this.layers = layersWithLegend.filter((l) => l.legend?.length);
  }
  onAdd() {
    this.el = document.createElement("div");
    this.el.className = "maplibregl-ctrl legend";
    this.el.innerHTML = this.layers
      .map(
        (l) =>
          `<h3>${l.name}</h3>` +
          l.legend.map((item) => `<div><span style="background:${item.color}"></span>${item.label}</div>`).join("")
      )
      .join("");
    if (!this.layers.length) this.el.hidden = true;
    return this.el;
  }
  onRemove() {
    this.el.remove();
  }
}
