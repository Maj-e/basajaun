// Entry point: loads the data, wires the modules, handles controls and presenter keys.
import { map, mapReady, mapError, updateSatellite } from "./map.js";
import { CONFIG } from "./config.js";
import { state, setState, subscribe } from "./state.js";
import { layers, manifest, loadData, addToMap, setHour, setLayerVisible, renderLegend, renderLayerList } from "./layers/loader.js";
import { createTimeline } from "./timeline.js";
import { computeStory, renderStory, fillPeakBanner, dayOf } from "./story.js";
import { renderReadouts } from "./readouts.js";

const $ = (id) => document.getElementById(id);
const H = 3600 * 1000;
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const presenter = new URLSearchParams(location.search).get("demo") === "1";
const fmtDay = (d, opts = {}) => new Date(`${d}T00:00:00Z`).toLocaleString("en", { day: "numeric", month: "short", timeZone: "UTC", ...opts });

// Fires per day: daily_summary.json when available, otherwise counted from the hotspots. Every day of the range is present.
// Requested right away, in parallel with the manifest and the layers
const summaryRequest = fetch(CONFIG.dailySummary).then((r) => (r.ok ? r.json() : null)).catch(() => null);

async function dailyCounts(features) {
  const counts = {};
  try {
    const summary = await summaryRequest;
    if (summary) {
      for (const [day, v] of Object.entries(summary)) if (/^\d{4}-\d{2}-\d{2}$/.test(day)) counts[day] = v.hotspots ?? 0;
    }
  } catch { /* fall back to counting below */ }
  if (!Object.keys(counts).length) features.forEach((f) => { const d = dayOf(f.properties.t); counts[d] = (counts[d] ?? 0) + 1; });
  const keys = Object.keys(counts).sort();
  const days = [];
  for (let t = Date.parse(`${keys[0]}T00:00:00Z`); t <= Date.parse(`${keys.at(-1)}T00:00:00Z`); t += 24 * H) {
    const d = new Date(t).toISOString().slice(0, 10);
    days.push(d);
    counts[d] ??= 0;
  }
  return { days, counts };
}

async function main() {
  try {
    await loadData();
  } catch (err) {
    console.error(err);
    $("status").textContent = "Data unavailable";
    $("status").classList.add("warn");
    return;
  }

  // The playback follows the first temporal point layer (the hotspots)
  const main = [...layers.values()].find((l) => l.layer.temporal && l.data?.features?.length);
  const features = main ? main.data.features : [];
  const { days, counts } = await dailyCounts(features);
  let story = computeStory(features, days, counts);
  let scoped = features; // the hotspots the figures are computed on (whole area or visible area)
  const start = Date.parse(`${days[0]}T00:00:00Z`) / H;
  const end = Date.parse(`${days.at(-1)}T00:00:00Z`) / H + 24;
  // Open three days before the peak (demo script), or at the start
  const playFrom = story.peak ? Math.max(start, story.peak.end + 0.01 - 24 * 4) : start;

  $("caption-scope").textContent = `MODIS + VIIRS merged · ${CONFIG.areaName} · ${fmtDay(days[0])} – ${fmtDay(days.at(-1), { year: "numeric" })}`;
  const generated = manifest.updated_at ? ` · generated ${new Date(manifest.updated_at).toLocaleString("en", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "UTC" })} UTC` : "";
  $("status").textContent = (CONFIG.manifest.includes("sample") ? "Sample data" : "Data") + generated;
  fillPeakBanner(story);
  renderLegend($("legend"));
  renderLayerList($("layer-list"), setLayerVisible);

  const timeline = createTimeline({ days, counts, story, start, end, playFrom });
  subscribe((s) => {
    timeline.render(s.hour);
    renderReadouts(scoped, s.hour, fmtDay(days[0]));
    renderStory(story, s.hour);
    setHour(s.hour);
    updateSatellite(s.satellite, dayOf(s.hour));
  });

  // Figures follow the visible area: zoom on a zone and the readouts, timeline, spark and peak are recomputed for it
  function applyScope() {
    const bounds = map.getBounds();
    const visible = features.filter((f) => bounds.contains(f.geometry.coordinates));
    const whole = visible.length === features.length;
    scoped = whole ? features : visible;
    const c = whole ? counts : Object.fromEntries(days.map((d) => [d, 0]));
    if (!whole) visible.forEach((f) => { const d = dayOf(f.properties.t); if (d in c) c[d] += 1; });
    story = computeStory(scoped, days, c);
    timeline.setData(c, story);
    fillPeakBanner(story);
    $("scope").classList.toggle("visible-area", !whole);
    $("scope-text").textContent = whole ? "Figures for the whole area"
      : `Figures for the visible area · ${visible.length.toLocaleString("en")} of ${features.length.toLocaleString("en")} fires`;
    $("scope-reset").hidden = whole;
    setState({}); // re-render readouts and story for the new scope
  }
  let scopeTimer = null;
  const scheduleScope = () => { clearTimeout(scopeTimer); scopeTimer = setTimeout(applyScope, 150); };
  $("scope-reset").onclick = () => map?.fitBounds(CONFIG.view, { padding: { top: 130, bottom: 200, left: 60, right: 60 } });

  mapReady.then(() => {
    addToMap();
    setHour(state.hour);
    map.on("moveend", scheduleScope);
  }).catch(() => {
    const el = $("map-error");
    el.hidden = false;
    el.innerHTML = `<b>Map unavailable</b>This browser could not start the map (WebGL is disabled or unsupported). The timeline and figures still work. Try another browser or enable hardware acceleration.`;
    console.error(mapError);
  });

  // Controls
  $("b-play").onclick = timeline.toggle;
  $("b-spark").onclick = timeline.jumpSpark;
  $("b-peak").onclick = timeline.jumpPeak;
  document.querySelectorAll("[data-speed]").forEach((b) => (b.onclick = () => {
    setState({ speed: Number(b.dataset.speed) });
    document.querySelectorAll("[data-speed]").forEach((o) => o.setAttribute("aria-pressed", String(o === b)));
  }));
  $("layers-toggle").onclick = () => {
    const panel = $("panel-layers");
    panel.hidden = !panel.hidden;
    $("layers-toggle").setAttribute("aria-expanded", String(!panel.hidden));
  };
  $("satellite-toggle").onchange = (e) => setState({ satellite: e.target.checked });

  // Presenter keys (docs/demo-script.md)
  window.addEventListener("keydown", (e) => {
    if (e.target.closest("input, textarea, select")) return;
    const k = e.key.toLowerCase();
    if (e.code === "Space") { e.preventDefault(); timeline.toggle(); }
    else if (k === "s") timeline.jumpSpark();
    else if (k === "p") timeline.jumpPeak();
    else if (k === "r") timeline.restart();
    else if (e.key === "ArrowRight") timeline.step(1);
    else if (e.key === "ArrowLeft") timeline.step(-1);
  });

  // Shared link loops on its own; ?demo=1 opens paused for the presenter; reduced motion opens on the peak
  if (reduceMotion && story.peak) timeline.seek(story.peak.end);
  else timeline.seek(playFrom);
  timeline.setPlaying(!presenter && !reduceMotion);
  timeline.start();
}

main();
