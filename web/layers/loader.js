// Generic layer loader.
// Reads the manifest and builds each active layer according to its `type`, using the style carried by each feature.
// Adding a layer = one data file + one manifest entry: this file does not change.
// Temporal layers (`temporal: true`) show each feature from its time `t` and fade it out over CONFIG.trailHours.
import { map } from "../map.js";
import { CONFIG } from "../config.js";
import { createParticlesLayer } from "./particles.js";

const dataUrl = (file) => CONFIG.dataRoot + file;

// ---------- Flowing arrows: each arrow slides forward along its direction, then starts again ----------
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
let currentHour = null, flowStarted = false;
const nowOnly = (hour, max) => ["case", ["all", ["<=", ["get", "t"], hour], [">", ["get", "t"], hour - 1]], max, 0];

function startArrowFlow() {
  if (flowStarted) return;
  flowStarted = true;
  const cache = new Map(); // layer id → { hour, features of that hour }
  let lastFlow = 0;
  const tick = (now) => {
    if (currentHour !== null && now - lastFlow >= 40) {
      lastFlow = now;
      const phase = reduceMotion ? 0.5 : (now / 1400) % 1;
      for (const entry of layers.values()) {
        const { layer, data } = entry;
        if (layer.type !== "arrows" || map.getLayoutProperty(layer.id, "visibility") === "none") continue;
        const h = Math.floor(currentHour);
        let c = cache.get(layer.id);
        if (!c || c.hour !== h) {
          c = { hour: h, features: data.features.filter((f) => f.properties.t <= currentHour && f.properties.t > currentHour - 1) };
          cache.set(layer.id, c);
        }
        // Two arrows per point, half a cycle apart, so the flow never looks empty
        const moved = [];
        for (const f of c.features) {
          const rad = ((f.properties.rotation ?? 0) - map.getBearing()) * Math.PI / 180;
          for (const p of reduceMotion ? [0.5] : [phase, (phase + 0.5) % 1]) {
            const pt = map.project(f.geometry.coordinates);
            const d = 18 * p - 9; // pixels along the wind, from -9 to +9
            const ll = map.unproject([pt.x + Math.sin(rad) * d, pt.y - Math.cos(rad) * d]);
            moved.push({ type: "Feature", geometry: { type: "Point", coordinates: [ll.lng, ll.lat] },
              properties: { ...f.properties, op: reduceMotion ? 0.85 : 0.9 * Math.sin(Math.PI * p) } });
          }
        }
        map.getSource(`${layer.id}-flow`)?.setData({ type: "FeatureCollection", features: moved });
      }
    }
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

// Arrow icon drawn once on a canvas (pointing up = north); SDF so its color comes from the data
function addArrowImage() {
  if (map.hasImage("wind-arrow")) return;
  const size = 64, c = document.createElement("canvas");
  c.width = c.height = size;
  const g = c.getContext("2d");
  g.fillStyle = "#ffffff";
  g.beginPath();
  g.moveTo(32, 6); g.lineTo(48, 28); g.lineTo(37, 26); g.lineTo(37, 58); g.lineTo(27, 58); g.lineTo(27, 26); g.lineTo(16, 28);
  g.closePath(); g.fill();
  map.addImage("wind-arrow", g.getImageData(0, 0, size, size), { sdf: true, pixelRatio: 2 });
}
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

  // Wind: arrows of the current hour, pointing where the wind blows (rotation), sized by speed (size).
  // They "flow": a small dedicated source whose points slide forward along the wind and start again.
  arrows: (layer) => {
    addArrowImage();
    const flowId = `${layer.id}-flow`;
    map.addSource(flowId, { type: "geojson", data: { type: "FeatureCollection", features: [] } });
    map.addLayer({ id: layer.id, type: "symbol", source: flowId,
      layout: {
        "icon-image": "wind-arrow",
        "icon-rotate": ["coalesce", ["get", "rotation"], 0],
        "icon-rotation-alignment": "map",
        "icon-size": ["interpolate", ["linear"], ["zoom"], 6, ["*", ["coalesce", ["get", "size"], 1], 0.45], 11, ["*", ["coalesce", ["get", "size"], 1], 0.8]],
        "icon-allow-overlap": true,
        "icon-ignore-placement": true,
      },
      paint: { "icon-color": color, "icon-opacity": ["coalesce", ["get", "op"], 0.85] } });
    startArrowFlow();
    return [layer.id];
  },

  // Rain (front-side style, see CONFIG.rainLayer): blue patches where it rains, bigger and darker with mm/h
  rain: (layer) => {
    const mm = ["coalesce", ["get", "rain"], 0];
    map.addLayer({ id: layer.id, type: "circle", source: layer.id, filter: [">", mm, 0], paint: {
      "circle-color": ["interpolate", ["linear"], mm, 0.1, "#9ecae1", 2, "#4292c6", 8, "#08519c"],
      "circle-radius": ["interpolate", ["linear"], ["zoom"],
        6, ["interpolate", ["linear"], mm, 0.1, 6, 10, 18],
        11, ["interpolate", ["linear"], mm, 0.1, 18, 10, 48]],
      "circle-blur": 0.7,
      "circle-opacity": 0.75 } });
    return [layer.id];
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
  active.forEach((l) => { if (l.id === CONFIG.rainLayer.id) l.name = CONFIG.rainLayer.name; });
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
  // Particles: own canvas above the map (no MapLibre source / layer), driven by setHour / setLayerVisible
  if (layer.type === "particles") {
    entry.particles = createParticlesLayer(map, layer, data);
    entry.mapLayerIds = [];
    if (currentHour !== null) entry.particles.setHour(currentHour);
    entry.particles.setVisible(entry.visible ?? isDefaultVisible(layer));
    return true;
  }
  const build = BUILDERS[layer.id === CONFIG.rainLayer.id ? "rain" : layer.type];
  if (!build) { console.warn(`Unknown layer type: "${layer.type}" (${layer.id})`); return false; }
  map.addSource(layer.id, layer.type === "image"
    ? { type: "image", url: dataUrl(layer.file), coordinates: layer.corners }
    // Current-hour layers (weather / rain) only hold the features of the hour shown
    : { type: "geojson", data: isNowOnly(entry) ? hourSubset(entry, currentHour) : data });
  entry.mapLayerIds = build(layer);
  placeInOrder(entry);
  if (layer.popup?.length) enablePopup(layer, entry.mapLayerIds);
  return true;
}

// Weather-like layers: one value per point and per hour, shown for the current hour only (no trail)
const isNowOnly = (entry) => entry.layer.temporal && !CONFIG.trailLayers.includes(entry.layer.id) && !["arrows", "particles"].includes(entry.layer.type);
function hourSubset(entry, hour) {
  const h = hour ?? -Infinity;
  return { type: "FeatureCollection", features: (entry.data?.features ?? []).filter((f) => f.properties.t <= h && f.properties.t > h - 1) };
}

// Put a layer's map layers at their place in CONFIG.layerOrder (below the first loaded layer ranked higher)
function placeInOrder(entry) {
  const order = CONFIG.layerOrder;
  const rank = (id) => { const i = order.indexOf(id); return i === -1 ? order.indexOf("hotspots") - 0.5 : i; };
  const mine = rank(entry.layer.id);
  const above = [...layers.values()]
    .filter((e) => e !== entry && e.mapLayerIds.length && rank(e.layer.id) > mine)
    .sort((a, b) => rank(a.layer.id) - rank(b.layer.id))[0];
  if (!above) return;
  const beforeId = map.getStyle().layers.find((l) => above.mapLayerIds.includes(l.id))?.id;
  if (beforeId) entry.mapLayerIds.forEach((id) => map.moveLayer(id, beforeId));
}

// Tick a box: download and build the layer the first time, then show or hide it
async function toggleLayer(id, visible) {
  const entry = layers.get(id);
  if (!entry || !map) return;
  const label = document.querySelector(`[data-layer="${id}"]`)?.parentElement;
  if (visible && entry.lazy) {
    label?.classList.add("loading");
    // Usually already downloaded in the background (prefetchLayers), so only the drawing is left
    const data = await (entry.prefetch ?? fetchLayer(entry.layer));
    if (data === undefined) { label?.classList.remove("loading"); return; }
    entry.data = data;
    entry.lazy = false;
    if (!addEntry(entry)) { label?.classList.remove("loading"); return; }
    if (currentHour !== null) setHour(currentHour);
    map.once("idle", () => label?.classList.remove("loading"));
  }
  if (!entry.lazy) setLayerVisible(id, visible);
}

// Once the page is shown and idle, download the hidden layers quietly so ticking a box is near-instant
export function prefetchLayers() {
  const start = () => {
    for (const entry of layers.values()) {
      if (entry.lazy && !entry.prefetch && entry.layer.type !== "image") entry.prefetch = fetchLayer(entry.layer);
    }
  };
  if ("requestIdleCallback" in window) requestIdleCallback(start, { timeout: 3000 });
  else setTimeout(start, 1500);
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
  currentHour = hour;
  const nowOnlyExpr = nowOnly(hour, 0.85);
  for (const entry of layers.values()) {
    const { mapLayerIds } = entry;
    if (entry.particles) { entry.particles.setHour(hour); continue; }
    if (!followsTime(entry)) continue;
    if (entry.layer.temporal && !CONFIG.trailLayers.includes(entry.layer.id)) {
      // Weather / rain: swap the small current-hour source only when the hour changes (not every frame).
      // Wind arrows are moved by the flow loop.
      if (isNowOnly(entry) && mapLayerIds.length) {
        const h = Math.floor(hour);
        if (entry.shownHour !== h) {
          entry.shownHour = h;
          map.getSource(entry.layer.id)?.setData(hourSubset(entry, hour));
        }
      }
      continue;
    }
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
  entry.visible = visible;
  entry.particles?.setVisible(visible);
  entry.mapLayerIds.forEach((l) => map.setLayoutProperty(l, "visibility", visible ? "visible" : "none"));
  if (legendEl) renderLegend(legendEl);
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
// Legend of every visible layer (manifest legend + CONFIG.legendExtras); redrawn when a box is ticked.
let legendEl = null;
const SHAPE_BY_TYPE = { circle: "dot", fill: "area", image: "area", line: "line", arrows: "arrow", rain: "dot" };
const ARROW = `<svg viewBox="0 0 12 12" aria-hidden="true"><path d="M6 1 10 6H7.4v5H4.6V6H2z" fill="currentColor"/></svg>`;
export function renderLegend(el) {
  legendEl = el;
  const shown = [...layers.values()].filter((e) => !e.lazy && (e.visible ?? isDefaultVisible(e.layer)));
  const blocks = shown.map(({ layer }) => {
    const items = [...(layer.legend ?? []), ...(CONFIG.legendExtras[layer.id] ?? [])];
    if (!items.length) return "";
    const shape = SHAPE_BY_TYPE[layer.type] ?? "dot";
    return `<h2>${layer.name}</h2>` + items.map((item) => item.note
      ? `<div class="legend-note">${item.note}</div>`
      : `<div class="legend-item"><i class="${item.shape ?? shape}" style="--c:${item.color}">${(item.shape ?? shape) === "arrow" ? ARROW : ""}</i>${item.text}</div>`).join("");
  }).filter(Boolean);
  el.hidden = !blocks.length;
  el.innerHTML = blocks.join("");
}

// Checkbox per loaded layer, in the layers panel.
export function renderLayerList(el, onToggle) {
  el.innerHTML = [...layers.values()].map(({ layer }) =>
    `<label><input type="checkbox" data-layer="${layer.id}"${isDefaultVisible(layer) ? " checked" : ""}> ${layer.name}</label>`).join("");
  el.querySelectorAll("[data-layer]").forEach((box) => (box.onchange = () => toggleLayer(box.dataset.layer, box.checked)));
}
