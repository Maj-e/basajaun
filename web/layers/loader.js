// Generic layer loader.
// Reads the manifest and builds each active layer according to its `type`, using the style carried by each feature.
// Adding a layer = one data file + one manifest entry: this file does not change.
// Temporal layers (`temporal: true`) show each feature from its time `t` and fade it out over CONFIG.trailHours.
import { map } from "../map.js";
import { CONFIG } from "../config.js";

const dataUrl = (file) => CONFIG.dataRoot + file;
const color = ["coalesce", ["get", "color"], "#888888"];
const isRing = ["==", ["coalesce", ["get", "ring"], false], true];
const byZoom = (value) => ["interpolate", ["linear"], ["zoom"], 6, ["*", value, 0.35], 9, ["*", value, 0.65], 12, value];
const radius = ["coalesce", ["get", "radius"], 5];

// One builder per layer type: returns the ids of the map layers it created.
const BUILDERS = {
  circle: (layer) => {
    const ids = [];
    // Dense layers: a heatmap reads better than overlapping circles when zoomed out
    if (CONFIG.heatmapLayers.includes(layer.id)) {
      map.addLayer({ id: `${layer.id}-heat`, type: "heatmap", source: layer.id, maxzoom: 11, paint: {
        "heatmap-weight": 0,
        "heatmap-intensity": ["interpolate", ["linear"], ["zoom"], 5, 0.6, 10, 1.4],
        "heatmap-radius": ["interpolate", ["linear"], ["zoom"], 5, 8, 10, 22],
        "heatmap-opacity": ["interpolate", ["linear"], ["zoom"], 7, 0.85, 10.5, 0],
        "heatmap-color": ["interpolate", ["linear"], ["heatmap-density"],
          0, "rgba(0,0,0,0)", 0.2, "rgba(154,61,18,0.55)", 0.45, "#c95b17", 0.7, "#ec8128", 0.9, "#f9a957", 1, "#ffd9a8"] } });
      ids.push(`${layer.id}-heat`);
    }
    if (layer.glow) {
      map.addLayer({ id: `${layer.id}-glow`, type: "circle", source: layer.id, paint: {
        "circle-color": color, "circle-blur": 1,
        "circle-radius": ["*", ["coalesce", ["get", "radius"], 5], 2.6] } });
      ids.push(`${layer.id}-glow`);
    }
    map.addLayer({ id: layer.id, type: "circle", source: layer.id, filter: ["!", isRing], paint: {
      "circle-color": color,
      "circle-radius": byZoom(radius),
      "circle-stroke-color": ["coalesce", ["get", "border"], "#070c16"],
      "circle-stroke-width": 0.6,
      "circle-opacity": ["coalesce", ["get", "opacity"], 0.95] } });
    // Features with `ring: true` (e.g. MODIS, 1 km pixel) are drawn as rings
    map.addLayer({ id: `${layer.id}-ring`, type: "circle", source: layer.id, filter: isRing, paint: {
      "circle-color": "rgba(0,0,0,0)",
      "circle-radius": byZoom(["+", radius, 2]),
      "circle-stroke-color": color, "circle-stroke-width": 1.5 } });
    ids.push(layer.id, `${layer.id}-ring`);
    return ids;
  },

  fill: (layer) => {
    map.addLayer({ id: layer.id, type: "fill", source: layer.id, paint: {
      "fill-color": color, "fill-opacity": ["coalesce", ["get", "opacity"], 0.35] } });
    map.addLayer({ id: `${layer.id}-outline`, type: "line", source: layer.id, paint: { "line-color": color, "line-width": 1.5 } });
    return [layer.id, `${layer.id}-outline`];
  },

  line: (layer) => {
    map.addLayer({ id: layer.id, type: "line", source: layer.id, paint: {
      "line-color": color, "line-width": ["coalesce", ["get", "width"], 1.5] } });
    return [layer.id];
  },

  image: (layer) => {
    map.addLayer({ id: layer.id, type: "raster", source: layer.id, paint: { "raster-opacity": 0.6 } });
    return [layer.id];
  },
};

// Loaded layers: id → { layer, data, mapLayerIds }. Read by the timeline, readouts, story and layer panel.
export const layers = new Map();
export let manifest = null;

// Fetch the manifest and every active layer's data. Works without a map (readouts and timeline still need the data).
export async function loadData() {
  const response = await fetch(CONFIG.manifest);
  if (!response.ok) throw new Error(`Manifest unavailable (${response.status})`);
  manifest = await response.json();
  // Layers shown at start are downloaded now, all at once; the others only when their box is ticked
  const active = manifest.layers.filter((l) => l.active);
  const files = await Promise.all(active.map(async (layer) => {
    if (!isDefaultVisible(layer)) return { layer, data: null, lazy: true };
    const data = await fetchLayer(layer);
    return data === undefined ? null : { layer, data };
  }));
  files.filter(Boolean).forEach(({ layer, data, lazy }) => layers.set(layer.id, { layer, data, lazy: !!lazy, mapLayerIds: [] }));
  return manifest;
}

// null for an image (MapLibre fetches it), undefined when the file is missing
async function fetchLayer(layer) {
  if (layer.type === "image") return null;
  try {
    const r = await fetch(dataUrl(layer.file));
    if (!r.ok) throw new Error(r.status);
    return await r.json();
  } catch {
    console.warn(`Layer file unavailable: ${layer.file}`);
    return undefined;
  }
}

// Add every loaded layer to the map.
export function addToMap() {
  if (!map) return;
  for (const entry of layers.values()) if (!entry.lazy) addEntry(entry);
}

function addEntry(entry) {
  const { layer, data } = entry;
  const build = BUILDERS[layer.type];
  if (!build) { console.warn(`Unknown layer type: "${layer.type}" (${layer.id})`); return false; }
  map.addSource(layer.id, layer.type === "image"
    ? { type: "image", url: dataUrl(layer.file), coordinates: layer.corners }
    : { type: "geojson", data });
  entry.mapLayerIds = build(layer);
  if (layer.popup?.length) enablePopup(layer, entry.mapLayerIds);
  return true;
}

// Tick a box: download and build the layer the first time, then show or hide it
async function toggleLayer(id, visible) {
  const entry = layers.get(id);
  if (!entry || !map) return;
  if (visible && entry.lazy) {
    const data = await fetchLayer(entry.layer);
    if (data === undefined) return;
    entry.data = data;
    entry.lazy = false;
    if (!addEntry(entry)) return;
    if (currentHour !== null) setHour(currentHour);
  }
  if (!entry.lazy) setLayerVisible(id, visible);
}

export const isDefaultVisible = (layer) => CONFIG.defaultLayers.includes(layer.id);

// A layer follows the playback if the manifest says so, or if its features carry a start time (fires: t_start)
const followsTime = ({ layer, data }) => layer.temporal || data?.features?.[0]?.properties?.t_start !== undefined;

// Temporal layers: show features detected before `hour`, fading over the trail.
export function setHour(hour) {
  if (!map) return;
  const trail = CONFIG.trailHours;
  const age = ["-", hour, ["get", "t"]];
  const visible = ["all", ["<=", ["get", "t"], hour], [">", ["get", "t"], hour - trail]];
  const fade = ["case", visible, ["interpolate", ["linear"], age, 0, 0.8, trail, 0.25], 0];
  const heatWeight = ["case", visible, ["interpolate", ["linear"], age, 0, 1, trail, 0.2], 0];
  const glowFade = ["case", visible, ["interpolate", ["linear"], age, 0, 0.8, 6, 0.3, trail, 0.05], 0];
  for (const entry of layers.values()) {
    const { mapLayerIds } = entry;
    if (!followsTime(entry)) continue;
    for (const id of mapLayerIds) {
      const type = map.getLayer(id)?.type;
      if (id.endsWith("-heat")) map.setPaintProperty(id, "heatmap-weight", heatWeight);
      else if (id.endsWith("-glow")) map.setPaintProperty(id, "circle-opacity", glowFade);
      else if (id.endsWith("-ring")) map.setPaintProperty(id, "circle-stroke-opacity", fade);
      else if (type === "circle") { map.setPaintProperty(id, "circle-opacity", fade); map.setPaintProperty(id, "circle-stroke-opacity", fade); }
      else if (type === "fill") map.setPaintProperty(id, "fill-opacity", ["case", ["<=", ["get", "t_start"], hour], ["coalesce", ["get", "opacity"], 0.35], 0]);
      else if (type === "line" && id.endsWith("-outline")) map.setPaintProperty(id, "line-opacity", ["case", ["<=", ["get", "t_start"], hour], 1, 0]);
    }
  }
}

export function setLayerVisible(id, visible) {
  const entry = layers.get(id);
  if (!map || !entry) return;
  entry.mapLayerIds.forEach((l) => map.setLayoutProperty(l, "visibility", visible ? "visible" : "none"));
}

// Keep one fire's hotspots. `null` restores every hotspot.
// The ring / fill split stays in the filter: replacing it would draw MODIS pixels as dots.
export function setHotspotFire(fireId) {
  if (!map) return;
  const entry = layers.get("hotspots");
  if (!entry) return;
  const byFire = fireId == null ? null : ["any",
    ["==", ["get", "fire_id"], fireId],
    ["==", ["get", "fire_id"], String(fireId)]];
  for (const id of entry.mapLayerIds) {
    const base = id.endsWith("-glow") ? null : id.endsWith("-ring") ? isRing : ["!", isRing];
    const filter = byFire ? (base ? ["all", base, byFire] : byFire) : base;
    map.setFilter(id, filter);
  }
}

// Human labels for known fields; unknown fields show their name.
const LABELS = { sensor: "Sensor", satellite: "Satellite", timestamp_utc: "Time (UTC)", confidence: "Confidence", frp: "FRP (fire intensity)" };
const format = (field, v) => {
  if (field === "frp") return `${Math.round(Number(v)).toLocaleString("en")} MW`;
  if (field === "timestamp_utc") return String(v).replace("T", " ").replace(":00Z", "");
  return v;
};

function enablePopup(layer, mapLayerIds) {
  const targets = mapLayerIds.filter((id) => !id.endsWith("-glow"));
  targets.forEach((id) => {
    map.on("mouseenter", id, () => (map.getCanvas().style.cursor = "pointer"));
    map.on("mouseleave", id, () => (map.getCanvas().style.cursor = ""));
    map.on("click", id, (e) => {
      const props = e.features[0].properties;
      const rows = layer.popup
        .filter((field) => props[field] !== undefined && props[field] !== null)
        .map((field) => `<tr><th>${LABELS[field] ?? field}</th><td>${format(field, props[field])}</td></tr>`)
        .join("");
      new maplibregl.Popup({ offset: 10 }).setLngLat(e.lngLat)
        .setHTML(`<strong>${layer.name}</strong><table class="popup">${rows}</table>`).addTo(map);
    });
  });
}

// Legend built from the manifest, in the #legend aside.
export function renderLegend(el) {
  const withLegend = [...layers.values()].map((l) => l.layer).filter((l) => l.legend?.length && isDefaultVisible(l));
  el.hidden = !withLegend.length;
  el.innerHTML = withLegend.map((l) =>
    `<h2>${l.name}</h2>` +
    l.legend.map((item) => `<div class="legend-item"><i class="${item.shape === "ring" ? "ring" : "dot"}" style="--c:${item.color}"></i>${item.text}</div>`).join("")
  ).join("");
}

// Checkbox per loaded layer, in the layers panel.
export function renderLayerList(el, onToggle) {
  el.innerHTML = [...layers.values()].map(({ layer }) =>
    `<label><input type="checkbox" data-layer="${layer.id}"${isDefaultVisible(layer) ? " checked" : ""}> ${layer.name}</label>`).join("");
  el.querySelectorAll("[data-layer]").forEach((box) => (box.onchange = () => toggleLayer(box.dataset.layer, box.checked)));
}
