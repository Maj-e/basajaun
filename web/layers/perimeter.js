// Fire perimeters as they were at a given hour (not the final shape).
// The backend writes one polygon per fire: convex hull of all its hotspots + 500 m. At hour h the same rule is
// applied to the hotspots detected up to h, so scrubbing back shrinks the perimeter to what was burning then.
// Pure functions (no map, no DOM): the loader only feeds the result to the map source.

const BUFFER_M = 500;
const STEPS = 12; // points of the circle drawn around each hull vertex

const cross = (o, a, b) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);

// Convex hull (Andrew's monotone chain). Returns the vertices counter-clockwise, without repeating the first.
export function convexHull(points) {
  const pts = [...points].sort((p, q) => p[0] - q[0] || p[1] - q[1]);
  if (pts.length < 3) return pts;
  const half = (list) => {
    const out = [];
    for (const p of list) {
      while (out.length >= 2 && cross(out.at(-2), out.at(-1), p) <= 0) out.pop();
      out.push(p);
    }
    out.pop();
    return out;
  };
  return [...half(pts), ...half([...pts].reverse())];
}

// Hull of the points grown by BUFFER_M (the hull of the buffered hull's vertices equals the buffered hull)
export function bufferedHull(points) {
  const hull = convexHull(points);
  const grown = [];
  for (const [lon, lat] of hull) {
    const dLat = BUFFER_M / 111320, dLon = dLat / Math.max(0.2, Math.cos((lat * Math.PI) / 180));
    for (let i = 0; i < STEPS; i++) {
      const a = (i / STEPS) * 2 * Math.PI;
      grown.push([lon + dLon * Math.cos(a), lat + dLat * Math.sin(a)]);
    }
  }
  const ring = convexHull(grown).map(([x, y]) => [Math.round(x * 1e5) / 1e5, Math.round(y * 1e5) / 1e5]);
  return ring.length ? [...ring, ring[0]] : ring;
}

// Index the hotspots by fire, oldest first, so each hour needs a slice rather than a scan
export function indexByFire(hotspots) {
  const byFire = new Map();
  for (const f of hotspots) {
    const id = Number(f.properties.fire_id);
    if (!Number.isFinite(id) || f.geometry?.type !== "Point") continue;
    if (!byFire.has(id)) byFire.set(id, []);
    byFire.get(id).push({ t: f.properties.t, p: f.geometry.coordinates });
  }
  for (const list of byFire.values()) list.sort((a, b) => a.t - b.t);
  return byFire;
}

// The fires FeatureCollection as of `hour`: same properties as the final fires, geometry from the hotspots so far.
// A fire with no detection yet is left out.
export function perimetersAt(finalFires, byFire, hour) {
  const features = [];
  for (const fire of finalFires.features) {
    const list = byFire.get(Number(fire.properties.fire_id));
    if (!list) { if (fire.properties.t_start <= hour) features.push(fire); continue; }
    let n = 0;
    while (n < list.length && list[n].t <= hour) n++;
    if (!n) continue;
    const ring = bufferedHull(list.slice(0, n).map((h) => h.p));
    features.push({ ...fire, geometry: { type: "Polygon", coordinates: [ring] } });
  }
  return { type: "FeatureCollection", features };
}
