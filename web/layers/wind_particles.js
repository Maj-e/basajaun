// Lightweight wind particle overlay for MapLibre ("Windy-lite"), ported from Miguel's TerraFlow (ui/js/wind_particles.js).
// Bilinear-sampled u/v field + a light curl so paths bend smoothly instead of snapping cell to cell.
// Drawn on its own <canvas> above the map; the map stays interactive (pointer-events: none).
// Reduced motion: no animation, a still image of short streaks redrawn when the map or the hour changes.

const PARTICLE_COUNT = 420;
const MAX_AGE = 110;
const STILL_STEPS = 14; // trail length of the still image (reduced motion)

export class WindParticles {
  constructor(canvas, map, { color = "#bae6fd", reduceMotion = false } = {}) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.map = map;
    this.grid = null; // { nx, ny, west, south, east, north, U[][], V[][] } — row 0 = south
    this.particles = [];
    this.enabled = false;
    this.raf = null;
    this.reduceMotion = reduceMotion;
    this.rgb = hexToRgb(color);
    this._onResize = () => { this.resize(); if (this.reduceMotion) this._drawStill(); };
    window.addEventListener("resize", this._onResize);
    this.resize();
    // Moving the map invalidates the trails: fade them (animated) or redraw the still image
    this.map.on("move", () => (this.reduceMotion ? this._drawStill() : this._fade()));
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) this.stop();
      else if (this.enabled) this.start();
    });
  }

  resize() {
    const dpr = window.devicePixelRatio || 1;
    const w = this.canvas.clientWidth || window.innerWidth;
    const h = this.canvas.clientHeight || window.innerHeight;
    this.canvas.width = Math.floor(w * dpr);
    this.canvas.height = Math.floor(h * dpr);
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    this.width = w;
    this.height = h;
  }

  /**
   * @param {{nx, ny, west, south, east, north, cells: {u, v}[]}} field  cells south → north, then west → east; m/s
   * @param {{keepParticles?: boolean}} options  keep the particles when only the hour changes (no jump)
   */
  setField(field, { keepParticles = false } = {}) {
    const cells = field?.cells ?? [];
    if (!cells.length) { this.grid = null; return; }
    const { nx, ny, west, south, east, north } = field;
    const U = Array.from({ length: ny }, () => Array(nx).fill(0));
    const V = Array.from({ length: ny }, () => Array(nx).fill(0));
    cells.forEach((cell, i) => {
      const r = Math.floor(i / nx), c = i % nx;
      if (r < ny) { U[r][c] = cell.u; V[r][c] = cell.v; }
    });
    this.grid = { nx, ny, west, south, east, north, U, V };
    if (!keepParticles || !this.particles.length) this.particles = Array.from({ length: PARTICLE_COUNT }, () => this._spawn());
    if (this.reduceMotion && this.enabled) this._drawStill();
  }

  setEnabled(on) {
    this.enabled = !!on;
    this.canvas.style.opacity = on ? "1" : "0";
    if (on) this.start();
    else this.stop();
  }

  _spawn() {
    const b = this.map.getBounds();
    return {
      lon: b.getWest() + Math.random() * (b.getEast() - b.getWest()),
      lat: b.getSouth() + Math.random() * (b.getNorth() - b.getSouth()),
      age: Math.random() * 100,
      phase: Math.random() * Math.PI * 2, // per-particle phase for soft turbulence
    };
  }

  _sample(lon, lat) {
    const g = this.grid;
    if (!g) return { u: 0, v: 0 };
    const { nx, ny, west, south, east, north, U, V } = g;
    const fx = Math.max(0, Math.min(nx - 1, ((lon - west) / Math.max(east - west, 1e-9)) * (nx - 1)));
    const fy = Math.max(0, Math.min(ny - 1, ((lat - south) / Math.max(north - south, 1e-9)) * (ny - 1)));
    const x0 = Math.floor(fx), y0 = Math.floor(fy);
    const x1 = Math.min(x0 + 1, nx - 1), y1 = Math.min(y0 + 1, ny - 1);
    const tx = fx - x0, ty = fy - y0;
    const lerp = (a, b, t) => a * (1 - t) + b * t;
    return {
      u: lerp(lerp(U[y0][x0], U[y0][x1], tx), lerp(U[y1][x0], U[y1][x1], tx), ty),
      v: lerp(lerp(V[y0][x0], V[y0][x1], tx), lerp(V[y1][x0], V[y1][x1], tx), ty),
    };
  }

  // One step for one particle: draws the segment, moves the particle, respawns it when old or off-screen
  _step(p, t, scale, bounds) {
    const uv = this._sample(p.lon, p.lat);
    const curl = 0.22 * Math.sin(p.phase + t * 0.7 + p.lon * 8 + p.lat * 8); // light curl on a coarse 5×5 grid
    const u = uv.u * Math.cos(curl) - uv.v * Math.sin(curl);
    const v = uv.u * Math.sin(curl) + uv.v * Math.cos(curl);
    const speed = Math.hypot(u, v) || 0.01;
    const stepPx = 1.1 + Math.min(speed, 12) * 0.35; // screen-space step ~ constant across zoom
    const nextLon = p.lon + (u / speed) * stepPx * scale;
    const nextLat = p.lat + (v / speed) * stepPx * scale;
    const a = this.map.project([p.lon, p.lat]);
    const z = this.map.project([nextLon, nextLat]);
    const [r, g, b] = this.rgb;
    this.ctx.strokeStyle = `rgba(${r}, ${g}, ${b}, ${0.35 + Math.min(speed / 10, 1) * 0.55})`; // faster = brighter
    this.ctx.beginPath();
    this.ctx.moveTo(a.x, a.y);
    this.ctx.lineTo(z.x, z.y);
    this.ctx.stroke();
    p.lon = nextLon;
    p.lat = nextLat;
    p.age += 1;
    if (p.age > MAX_AGE || !bounds.contains([p.lon, p.lat])) Object.assign(p, this._spawn());
  }

  _scale() {
    return 0.00009 * Math.pow(2, 11.5 - this.map.getZoom()); // readable motion at every zoom
  }

  _fade() {
    // Erase trails without painting a dark veil over the basemap
    this.ctx.save();
    this.ctx.globalCompositeOperation = "destination-out";
    this.ctx.fillStyle = "rgba(0, 0, 0, 0.14)";
    this.ctx.fillRect(0, 0, this.width, this.height);
    this.ctx.restore();
  }

  _frame() {
    if (!this.enabled || !this.grid) { this.raf = null; return; }
    this._fade();
    this.ctx.lineWidth = 1.25;
    this.ctx.lineCap = "round";
    const t = performance.now() * 0.001, scale = this._scale(), bounds = this.map.getBounds();
    for (const p of this.particles) this._step(p, t, scale, bounds);
    this.raf = requestAnimationFrame(() => this._frame());
  }

  // Reduced motion: a still image of short streaks, no animation loop
  _drawStill() {
    if (!this.enabled || !this.grid) return;
    this.ctx.clearRect(0, 0, this.width, this.height);
    this.ctx.lineWidth = 1.25;
    this.ctx.lineCap = "round";
    const scale = this._scale(), bounds = this.map.getBounds();
    this.particles = Array.from({ length: PARTICLE_COUNT }, () => ({ ...this._spawn(), age: 0 }));
    for (const p of this.particles) for (let i = 0; i < STILL_STEPS; i++) this._step(p, 0, scale, bounds);
  }

  start() {
    if (!this.enabled) return;
    if (this.reduceMotion) { this._drawStill(); return; }
    if (!this.raf) this.raf = requestAnimationFrame(() => this._frame());
  }

  stop() {
    if (this.raf) cancelAnimationFrame(this.raf);
    this.raf = null;
    this.ctx.clearRect(0, 0, this.width, this.height);
  }
}

function hexToRgb(hex) {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex ?? "");
  const n = m ? parseInt(m[1], 16) : 0xbae6fd;
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}
