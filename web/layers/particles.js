// `particles` layer type: animated surface wind from the layer's file (weather.geojson).
// Each point carries the surface wind at 10 m as u / v (m/s, where it blows to) for one hour `t` (see docs/frontend_layers.md).
// The loader creates one controller per particles layer and drives it with setHour / setVisible, like any other layer.
import { WindParticles } from "./wind_particles.js";

const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/** Field for one hour: cells south → north, then west → east, as WindParticles expects. */
export function fieldFor(features) {
  const pts = features.filter((f) => Number.isFinite(f.properties.u) && Number.isFinite(f.properties.v));
  if (!pts.length) return null;
  const lons = [...new Set(pts.map((f) => f.geometry.coordinates[0]))].sort((a, b) => a - b);
  const lats = [...new Set(pts.map((f) => f.geometry.coordinates[1]))].sort((a, b) => a - b);
  const at = new Map(pts.map((f) => [`${f.geometry.coordinates[0]},${f.geometry.coordinates[1]}`, f.properties]));
  const cells = [];
  for (const lat of lats) for (const lon of lons) cells.push(at.get(`${lon},${lat}`) ?? { u: 0, v: 0 });
  return { nx: lons.length, ny: lats.length, west: lons[0], east: lons.at(-1), south: lats[0], north: lats.at(-1), cells };
}

export function createParticlesLayer(map, layer, data) {
  const byHour = new Map();
  for (const f of data?.features ?? []) {
    const h = Math.floor(f.properties.t);
    if (!byHour.has(h)) byHour.set(h, []);
    byHour.get(h).push(f);
  }
  const hours = [...byHour.keys()].sort((a, b) => a - b);

  const canvas = document.createElement("canvas");
  canvas.className = "particles-canvas";
  canvas.dataset.particles = layer.id; // not data-layer: that attribute identifies the panel checkbox
  canvas.setAttribute("aria-hidden", "true");
  map.getContainer().appendChild(canvas);
  const engine = new WindParticles(canvas, map, { color: layer.color, reduceMotion });
  let shownHour = null;

  // Nearest available hour at or before `hour` (weather is hourly; playback hours have decimals)
  const hourFor = (hour) => {
    if (!hours.length) return null;
    if (!Number.isFinite(hour)) return hours[0];
    let best = hours[0];
    for (const h of hours) { if (h > Math.floor(hour)) break; best = h; }
    return best;
  };

  return {
    setHour(hour) {
      const h = hourFor(hour);
      if (h === null || h === shownHour) return;
      const keep = shownHour !== null;
      shownHour = h;
      engine.setField(fieldFor(byHour.get(h)), { keepParticles: keep });
    },
    setVisible(visible) {
      engine.setEnabled(visible);
    },
  };
}
