// Generic layer loader.
// Reads the manifest and builds each active layer according to its `type`, using the style carried by each feature.
// Adding a layer = one data file + one manifest entry: this file does not change.
// Temporal layers (`temporal: true`) show each feature from its time `t` and fade it out over CONFIG.trailHours.
import { map } from "../map.js";
import { CONFIG } from "../config.js";
import { createParticlesLayer } from "./particles.js";
import { indexByFire, perimetersAt } from "./perimeter.js";

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

// null for an image (MapLibre fetches it), undefined when the file is missing.
// One download per file: wind, weather and rain share weather.geojson.
const requests = new Map();
function fetchLayer(layer, priority = "auto") {
  if (layer.type === "image") return Promise.resolve(null);
  if (!requests.has(layer.file)) {
    requests.set(layer.file, fetch(dataUrl(layer.file), { priority })
      .then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); })
      .catch(() => { console.warn(`Layer file unavailable: ${layer.file}`); return undefined; }));
  }
  return requests.get(layer.file);
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
// One file at a time and at low priority, so it never competes with the map tiles or a box the user ticks.
export function prefetchLayers() {
  const start = async () => {
    for (const entry of layers.values()) {
      if (!entry.lazy || entry.prefetch || entry.layer.type === "image") continue;
      entry.prefetch = fetchLayer(entry.layer, "low");
      await entry.prefetch;
    }
  };
  if ("requestIdleCallback" in window) requestIdleCallback(start, { timeout: 3000 });
  else setTimeout(start, 1500);
}

export const isDefaultVisible = (layer) => CONFIG.defaultLayers.includes(layer.id);

// A layer follows the playback if the manifest says so, or if its features carry a start time (fires: t_start)
const hasStart = (data) => data?.features?.[0]?.properties?.t_start !== undefined;
// Polygons of a fire (spread, evacuation, risk) carry its fire_id but no time of their own: they start with their fire
const linkedToFire = ({ layer, data }) => layer.id !== "fires" && ["fill", "line"].includes(layer.type) && !hasStart(data)
  && data?.features?.[0]?.properties?.fire_id !== undefined;
const followsTime = (entry) => entry.layer.temporal || hasStart(entry.data) || linkedToFire(entry);

// Expression giving each feature the start time of its fire (hidden when the fire is unknown)
function fireStartExpr() {
  const fires = layers.get("fires")?.data?.features ?? [];
  const pairs = fires.flatMap((f) => [Number(f.properties.fire_id), f.properties.t_start]);
  return pairs.length ? ["match", ["to-number", ["get", "fire_id"], -1], ...pairs, 1e12] : 1e12;
}

// Fire perimeters as they were at `hour`: rebuilt from the hotspots so far (perimeter.js), once per playback hour.
// entry.data keeps the final shapes: clicking a fire still frames its whole extent.
function showPerimeters(entry, hour) {
  const hotspots = layers.get("hotspots")?.data;
  const source = map.getSource(entry.layer.id);
  if (!hotspots || !source?.setData || !entry.data) return;
  const h = Math.floor(hour);
  if (entry.perimeterHour === h) return;
  entry.perimeterHour = h;
  entry.byFire ??= indexByFire(hotspots.features);
  source.setData(perimetersAt(entry.data, entry.byFire, hour));
}

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
    if (entry.layer.id === "fires" && mapLayerIds.length) showPerimeters(entry, hour);
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
    const startOf = linkedToFire(entry) ? fireStartExpr() : ["get", "t_start"];
    // Visible from t_start; snapshots of a fire's zones (spread, evacuation, risk) also end at t_until, when the next one starts
    // Fire perimeters stay once the fire stops growing, but fainter: what burned, no longer what is burning
    const burnedOut = entry.layer.id === "fires" ? ["case", [">", hour, ["+", ["get", "t_end"], CONFIG.trailHours]], 0.6, 1] : 1;
    const live = ["all", ["<=", startOf, hour], ["<", hour, ["coalesce", ["get", "t_until"], 1e12]]];
    for (const id of mapLayerIds) {
      const type = map.getLayer(id)?.type;
      if (id.endsWith("-heat")) map.setPaintProperty(id, "heatmap-weight", heatWeight);
      else if (id.endsWith("-glow")) map.setPaintProperty(id, "circle-opacity", glowFade);
      else if (id.endsWith("-ring")) map.setPaintProperty(id, "circle-stroke-opacity", fade);
      else if (type === "circle") { map.setPaintProperty(id, "circle-opacity", fade); map.setPaintProperty(id, "circle-stroke-opacity", fade); }
      else if (type === "fill") map.setPaintProperty(id, "fill-opacity", ["case", live, ["*", ["coalesce", ["get", "opacity"], 0.35], burnedOut], 0]);
      else if (type === "line" && id.endsWith("-outline")) map.setPaintProperty(id, "line-opacity", ["case", live, burnedOut, 0]);
    }
  }
}

// The player started or paused: the wind particles move only while it plays
export function setPlayback(playing) {
  for (const entry of layers.values()) entry.particles?.setPlaying(playing);
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
// Popups: human labels and units instead of raw field names; empty fields are skipped.
const COMPASS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
const compass = (deg) => COMPASS[Math.round((((Number(deg) % 360) + 360) % 360) / 45) % 8];
const words = (v) => { const t = String(v).replace(/_/g, " "); return t.charAt(0).toUpperCase() + t.slice(1); };
const num = (v, d = 1) => Number(v).toLocaleString("en", { maximumFractionDigits: d });
const FORMAT = {
  text: (v) => v,
  words,
  time: (v) => {
    const d = new Date(v);
    if (Number.isNaN(d.getTime())) return v;
    return `${d.getUTCDate()} ${d.toLocaleString("en", { month: "short", timeZone: "UTC" })} · ${String(d.getUTCHours()).padStart(2, "0")}:${String(d.getUTCMinutes()).padStart(2, "0")} UTC`;
  },
  mw: (v) => `${num(v, 0)} MW`,
  km: (v) => `${num(v)} km`,
  km2: (v) => `${num(v)} km²`,
  deg: (v) => `${num(v, 0)}°`,
  int: (v) => num(v, 0),
  people: (v) => `${num(v, 0)} people`,
  score: (v) => `${num(v, 0)} / 100`,
  hours: (v) => `${num(v, 0)} h`,
  kmh: (v) => `${num(v, 0)} km/h`,
  pct: (v) => `${num(v, 0)} %`,
  mm: (v) => `${num(v)} mm`,
  celsius: (v) => `${num(v)} °C`,
  windFrom: (v) => `from ${compass(v)} (${num(v, 0)}°)`,
  windTo: (v) => `towards ${compass(v)} (${num(v, 0)}°)`,
  list: (v) => {
    let a = v;
    if (typeof a === "string") { try { a = JSON.parse(a); } catch { return words(a); } }
    return Array.isArray(a) ? a.map(words).join(", ") : words(a);
  },
};
const FIELDS = {
  sensor: ["Sensor"], satellite: ["Satellite"], timestamp_utc: ["Time", "time"], confidence: ["Confidence", "words"],
  frp: ["Fire intensity (FRP)", "mw"], country: ["Country"], region: ["Region"],
  start: ["First detected", "time"], end: ["Last detected", "time"], n_hotspots: ["Hotspots", "int"],
  frp_max: ["Peak intensity (FRP)", "mw"], area_km2: ["Area", "km2"], slope_deg: ["Mean slope", "deg"], landcover: ["Land cover", "words"],
  dist_road_km: ["Nearest road", "km"], dist_water_km: ["Nearest water", "km"], dist_fire_station_km: ["Nearest fire station", "km"],
  dist_water_point_km: ["Nearest water point", "km"], gw_body: ["Groundwater body"], gw_vulnerability: ["Groundwater vulnerability", "words"],
  gw_chemical_status: ["Groundwater status", "words"], risk_level: ["Risk", "words"], risk_score: ["Risk score", "score"],
  risk_factors: ["Risk factors", "list"], evacuate_people: ["To evacuate", "people"], warn_people: ["To warn", "people"],
  horizon_hours: ["Horizon", "hours"], wind_speed_kmh: ["Wind", "kmh"], wind_to_deg: ["Spreading", "windTo"], spread_km: ["Spread distance", "km"],
  speed: ["Wind speed", "kmh"], direction: ["Wind", "windFrom"], temperature: ["Temperature", "celsius"], humidity: ["Humidity", "pct"], rain: ["Rain", "mm"],
  name: ["Name"], kind: ["Type", "words"], highway: ["Road type", "words"],
};
const isEmpty = (v) => v === undefined || v === null || v === "" || v === "null" || v === "[]";
export function popupHtml(title, props, fields) {
  const rows = fields
    .filter((f) => f !== "fire_id" && !isEmpty(props[f]))
    .map((f) => {
      const [label, kind = "text"] = FIELDS[f] ?? [words(f)];
      return `<tr><th>${label}</th><td>${FORMAT[kind](props[f])}</td></tr>`;
    }).join("");
  const id = isEmpty(props.fire_id) ? "" : ` <span class="popup-id">#${props.fire_id}</span>`;
  return `<strong>${title}${id}</strong>${rows ? `<table class="popup">${rows}</table>` : ""}`;
}

// Keep an open popup clear of the header and the timeline, which sit on top of the map
export function keepInView(popup) {
  const nudge = () => {
    const el = popup.getElement();
    if (!el || !map) return;
    const r = el.getBoundingClientRect();
    const top = (document.querySelector(".head")?.getBoundingClientRect().bottom ?? 0) + 8;
    const bottom = (document.getElementById("timeline")?.getBoundingClientRect().top ?? innerHeight) - 8;
    const left = 8, right = innerWidth - 8;
    let dx = 0, dy = 0;
    if (r.top < top) dy = r.top - top; else if (r.bottom > bottom) dy = Math.min(r.bottom - bottom, r.top - top);
    if (r.left < left) dx = r.left - left; else if (r.right > right) dx = r.right - right;
    if (dx || dy) map.panBy([dx, dy], { duration: 300 });
  };
  // Wait for a zoom in progress (e.g. isolating a fire) to finish
  if (map.isMoving()) map.once("moveend", nudge); else requestAnimationFrame(nudge);
  return popup;
}

function enablePopup(layer, mapLayerIds) {
  const targets = mapLayerIds.filter((id) => !id.endsWith("-glow"));
  targets.forEach((id) => {
    map.on("mouseenter", id, () => (map.getCanvas().style.cursor = "pointer"));
    map.on("mouseleave", id, () => (map.getCanvas().style.cursor = ""));
    map.on("click", id, (e) => {
      const popup = new maplibregl.Popup({ offset: 10, maxWidth: "300px" }).setLngLat(e.lngLat)
        .setHTML(popupHtml(layer.name, e.features[0].properties, layer.popup)).addTo(map);
      keepInView(popup);
    });
  });
}

// Legend of each visible layer (manifest legend + CONFIG.legendExtras), right under its box in the Layers tab;
// redrawn when a box is ticked. `el` is the layer list.
let legendEl = null;
const SHAPE_BY_TYPE = { circle: "dot", fill: "area", image: "area", line: "line", arrows: "arrow", rain: "dot" };
const ARROW = `<svg viewBox="0 0 12 12" aria-hidden="true"><path d="M6 1 10 6H7.4v5H4.6V6H2z" fill="currentColor"/></svg>`;
export function renderLegend(el) {
  legendEl = el;
  for (const box of el.querySelectorAll(".layer-legend")) {
    const entry = layers.get(box.dataset.for);
    const shown = entry && !entry.lazy && (entry.visible ?? isDefaultVisible(entry.layer));
    const items = shown ? [...(entry.layer.legend ?? []), ...(CONFIG.legendExtras[entry.layer.id] ?? [])] : [];
    box.hidden = !items.length;
    if (!items.length) { box.innerHTML = ""; continue; }
    const shape = SHAPE_BY_TYPE[entry.layer.type] ?? "dot";
    const keys = items.filter((item) => !item.note);
    const notes = items.filter((item) => item.note);
    box.innerHTML = (keys.length ? `<ul class="legend-items">${keys.map((item) =>
      `<li><i class="${item.shape ?? shape}" style="--c:${item.color}">${(item.shape ?? shape) === "arrow" ? ARROW : ""}</i>${item.text}</li>`).join("")}</ul>` : "") +
      notes.map((item) => `<p class="legend-note">${item.note}</p>`).join("");
  }
}

// Boxes in the Layers tab, grouped by theme (CONFIG.layerGroups), each with its legend underneath.
export function renderLayerList(el, onToggle) {
  const all = [...layers.values()].map((e) => e.layer);
  const listed = new Set(CONFIG.layerGroups.flatMap((g) => g.ids));
  const groups = [...CONFIG.layerGroups.map((g) => ({ name: g.name, layers: g.ids.map((id) => all.find((l) => l.id === id)).filter(Boolean) })),
    { name: "Other", layers: all.filter((l) => !listed.has(l.id)) }].filter((g) => g.layers.length);
  el.innerHTML = groups.map((g) => `<fieldset class="group"><legend>${g.name}</legend>${g.layers.map((layer) =>
    `<div class="layer-row"><label class="layer"><input type="checkbox" data-layer="${layer.id}"${isDefaultVisible(layer) ? " checked" : ""}> <span>${layer.name}</span></label>` +
    `<div class="layer-legend" data-for="${layer.id}" hidden></div></div>`).join("")}</fieldset>`).join("");
  el.querySelectorAll("[data-layer]").forEach((box) => (box.onchange = () => toggleLayer(box.dataset.layer, box.checked)));
  renderLegend(el);
}
