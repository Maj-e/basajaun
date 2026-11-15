// Entry point: loads the data, wires the modules, handles controls and presenter keys.
import { map, mapReady, mapError, updateSatellite, onSatelliteDate, setBasemap } from "./map.js";
import { CONFIG } from "./config.js";
import { state, setState, subscribe } from "./state.js";
import { layers, manifest, loadData, addToMap, setHour, setLayerVisible, setHotspotFire, renderLayerList, prefetchLayers } from "./layers/loader.js";
import { createTimeline } from "./timeline.js";
import { computeStory, dayOf } from "./story.js";
import { renderReadouts } from "./readouts.js";
import { loadAlerts, renderAlerts, setAlertLabels, setFirePlaces, setAlertHandlers, showAlertFire } from "./alerts.js";

const $ = (id) => document.getElementById(id);
const H = 3600 * 1000;
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const presenter = new URLSearchParams(location.search).get("demo") === "1";
const fmtDay = (d, opts = {}) => new Date(`${d}T00:00:00Z`).toLocaleString("en", { day: "numeric", month: "short", timeZone: "UTC", ...opts });
const PADDING = CONFIG.framePadding;

// [[west, south], [east, north]] of a Polygon or MultiPolygon, for fitBounds.
function boundsOf(geometry) {
  let west = Infinity, south = Infinity, east = -Infinity, north = -Infinity;
  const visit = (node) => {
    if (typeof node[0] === "number") {
      west = Math.min(west, node[0]); east = Math.max(east, node[0]);
      south = Math.min(south, node[1]); north = Math.max(north, node[1]);
    } else node.forEach(visit);
  };
  visit(geometry.coordinates);
  return Number.isFinite(west) ? [[west, south], [east, north]] : null;
}

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

// ---------- Map panel: one panel, two tabs (Layers, Alerts), foldable ----------
// Desktop: left column between the header and the timeline. Mobile: bottom sheet above the timeline, folded at first.
// The panel's room follows the real header and timeline heights (CSS variables).
const panel = (() => {
  const tabs = () => [...document.querySelectorAll('#panel [role="tab"]')].filter((t) => !t.hidden);
  const mobile = matchMedia("(max-width: 760px)");
  let folded = mobile.matches;
  const fold = (on) => {
    folded = on;
    $("panel").classList.toggle("folded", on);
    $("panel-body").hidden = on;
    $("panel-fold").setAttribute("aria-expanded", String(!on));
    $("panel-fold").setAttribute("aria-label", on ? "Show the panel" : "Hide the panel");
  };
  const select = (tab) => {
    tabs().forEach((t) => {
      const on = t === tab;
      t.setAttribute("aria-selected", String(on));
      t.tabIndex = on ? 0 : -1;
      $(t.getAttribute("aria-controls")).hidden = !on;
    });
  };
  document.querySelectorAll('#panel [role="tab"]').forEach((t) => {
    // Tapping the open tab folds the panel; any tab unfolds it
    t.onclick = () => { if (t.getAttribute("aria-selected") === "true" && !folded) fold(true); else { select(t); fold(false); } };
    // WAI-ARIA tabs: arrows move between tabs, Home / End to the first / last
    t.onkeydown = (e) => {
      const list = tabs(), i = list.indexOf(t);
      const next = { ArrowRight: list[(i + 1) % list.length], ArrowLeft: list[(i - 1 + list.length) % list.length], Home: list[0], End: list.at(-1) }[e.key];
      if (!next) return;
      e.preventDefault();
      select(next); fold(false); next.focus();
    };
  });
  $("panel-fold").onclick = () => fold(!folded);
  fold(folded);
  const measure = () => {
    const root = document.documentElement.style;
    root.setProperty("--tl-h", `${$("timeline").offsetHeight}px`);
    root.setProperty("--head-h", `${document.querySelector(".head .title").getBoundingClientRect().bottom}px`);
  };
  new ResizeObserver(measure).observe($("timeline"));
  new ResizeObserver(measure).observe(document.querySelector(".head"));
  return {
    show: (name) => { const t = $(`tab-${name}`); if (t && !t.hidden) { select(t); fold(false); } },
  };
})();

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
  let scoped = features; // the hotspots the figures are computed on (whole area, visible area, or one fire)
  let isolatedFireId = null; // set while a fire polygon is isolated; viewport scope stays paused
  let alertScope = () => true; // which alerts belong to the current scope
  await loadAlerts();
  setFirePlaces(features);
  const start = Date.parse(`${days[0]}T00:00:00Z`) / H;
  const end = Date.parse(`${days.at(-1)}T00:00:00Z`) / H + 24;
  // Open three days before the peak (demo script), or at the start
  const playFrom = story.peak ? Math.max(start, story.peak.end + 0.01 - 24 * 4) : start;

  // Episode selector: switching reloads the page on that episode (keeps ?demo=1)
  const pick = $("episode-select");
  pick.innerHTML = CONFIG.episodes.map((e) => `<option value="${e.id}"${e.id === CONFIG.episode.id ? " selected" : ""}>${e.name}</option>`).join("");
  pick.parentElement.hidden = CONFIG.episodes.length < 2;
  // WCAG 3.2.2: choosing an option never reloads the page by itself (arrow keys would reload on every step); Open does
  $("episode-go").onclick = () => {
    if (pick.value === CONFIG.episode.id) return;
    const q = new URLSearchParams(location.search);
    q.set("episode", pick.value);
    location.search = q.toString();
  };
  $("caption-scope").textContent = `MODIS + VIIRS merged · ${CONFIG.areaName} · ${fmtDay(days[0])} – ${fmtDay(days.at(-1), { year: "numeric" })}`;
  const generated = manifest.updated_at ? ` · generated ${new Date(manifest.updated_at).toLocaleString("en", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "UTC" })} UTC` : "";
  $("status").textContent = (CONFIG.manifest.includes("sample") ? "Sample data" : "Data") + generated;
  renderLayerList($("layer-list"), setLayerVisible);

  const timeline = createTimeline({ days, counts, story, start, end, playFrom });
  subscribe((s) => {
    timeline.render(s.hour);
    renderReadouts(scoped, s.hour, fmtDay(days[0]));
    renderAlerts(s.hour, (a) => alertScope(a));
    setHour(s.hour);
    updateSatellite(s.satellite, dayOf(s.hour));
  });

  // Recount hotspots per day. The precomputed summary is the whole area; any narrower scope counts its own features.
  function countsFor(list, useSummary) {
    if (useSummary) return counts;
    const c = Object.fromEntries(days.map((d) => [d, 0]));
    list.forEach((f) => { const d = dayOf(f.properties.t); if (d in c) c[d] += 1; });
    return c;
  }

  function publishScope(list, narrowed, text) {
    scoped = list;
    const c = countsFor(list, !narrowed);
    story = computeStory(scoped, days, c);
    timeline.setData(c, story);
      $("scope").classList.toggle("visible-area", narrowed);
    $("scope-text").textContent = text;
    $("scope-reset").hidden = !narrowed;
    setState({}); // re-render readouts and story for the new scope
  }

  // Figures follow the visible area: zoom on a zone and the readouts, timeline and peak are recomputed for it.
  // A selected fire owns the figures until it is cleared; the camera move from fitBounds must not replace them.
  function applyScope() {
    if (isolatedFireId != null) return;
    const bounds = map.getBounds();
    const visible = features.filter((f) => bounds.contains(f.geometry.coordinates));
    const whole = visible.length === features.length;
    const list = whole ? features : visible;
    alertScope = whole ? () => true : (a) => bounds.contains(a.center);
    publishScope(list, !whole, whole ? "Figures for the whole area"
      : `Figures for the visible area · ${visible.length.toLocaleString("en")} of ${features.length.toLocaleString("en")} fires`);
  }

  function showWholeArea() {
    isolatedFireId = null;
    alertScope = () => true;
    setHotspotFire(null);
    showAlertFire(null);
    publishScope(features, false, "Figures for the whole area");
    map?.fitBounds(CONFIG.view, { padding: PADDING });
  }

  function isolateFire(id, geometry) {
    if (isolatedFireId === id) { showWholeArea(); return; }
    isolatedFireId = id;
    panel.show("alerts"); // the fire's detail is in the Alerts tab
    alertScope = (a) => Number(a.fire_id) === id;
    setHotspotFire(id);
    showAlertFire(id);
    const list = features.filter((f) => Number(f.properties.fire_id) === id);
    publishScope(list, true, `Figures for fire ${id} · ${list.length.toLocaleString("en")} hotspots`);
    const bounds = geometry && boundsOf(geometry);
    if (bounds) map.fitBounds(bounds, { padding: PADDING });
  }

  let scopeTimer = null;
  const scheduleScope = () => { clearTimeout(scopeTimer); scopeTimer = setTimeout(applyScope, 150); };
  $("scope-reset").onclick = () => showWholeArea();
  // Alert panel: picking a fire isolates it on the map (and opens its detail); Back returns to the whole area
  setAlertHandlers({
    select: (id, center) => {
      const stored = layers.get("fires")?.data?.features?.find((f) => Number(f.properties.fire_id) === id);
      if (isolatedFireId !== id) isolateFire(id, stored?.geometry);
      if (!stored?.geometry && center) map?.flyTo({ center, zoom: 10 });
    },
    clear: () => showWholeArea(),
  });

  mapReady.then(() => {
    addToMap();
    setHour(state.hour);
    map.once("idle", prefetchLayers);
    map.on("moveend", scheduleScope);
    const fireLayers = ["fires", "fires-outline"].filter((id) => map.getLayer(id));
    if (fireLayers.length) map.on("click", (e) => {
      const hits = map.queryRenderedFeatures(e.point, { layers: fireLayers });
      if (!hits.length) return;
      const id = Number(hits[0].properties.fire_id);
      if (!Number.isFinite(id)) return;
      const stored = layers.get("fires")?.data?.features?.find((f) => Number(f.properties.fire_id) === id);
      isolateFire(id, stored?.geometry ?? hits[0].geometry);
    });
  }).catch(() => {
    const el = $("map-error");
    el.hidden = false;
    el.innerHTML = `<b>Map unavailable</b>This browser could not start the map (WebGL is disabled or unsupported). The timeline and figures still work. Try another browser or enable hardware acceleration.`;
    console.error(mapError);
  });

  // Controls
  $("b-play").onclick = timeline.toggle;
  $("b-peak").onclick = timeline.jumpPeak;
  document.querySelectorAll("[data-speed]").forEach((b) => (b.onclick = () => {
    setState({ speed: Number(b.dataset.speed) });
    document.querySelectorAll("[data-speed]").forEach((o) => o.setAttribute("aria-pressed", String(o === b)));
  }));
  // Timeline: open on every load, can be folded down to the clock and the play controls
  const foldTimeline = (folded) => {
    document.body.classList.toggle("tl-folded", folded);
    $("tl-fold").setAttribute("aria-expanded", String(!folded));
    $("tl-fold").title = folded ? "Show the chart" : "Hide the chart";
    $("tl-fold").setAttribute("aria-label", $("tl-fold").title);
  };
  let tlFolded = false;
  $("tl-fold").onclick = () => foldTimeline((tlFolded = !tlFolded));
  // Demo disclaimer (W5-F2): once per visitor, never in presenter mode
  const presenterMode = new URLSearchParams(location.search).get("demo") === "1";
  let dismissed = false;
  try { dismissed = localStorage.getItem("ulinautas-demo-banner") === "closed"; } catch { /* storage blocked: show it */ }
  $("demo-banner").hidden = presenterMode || dismissed;
  $("demo-banner-close").onclick = () => {
    $("demo-banner").hidden = true;
    try { localStorage.setItem("ulinautas-demo-banner", "closed"); } catch { /* fine, it just shows again next time */ }
  };
  $("labels-toggle").onchange = (e) => setAlertLabels(e.target.checked);
  // Base map picker (W3-F7): Topo (default) / Satellite / Dark
  const baseSwitch = $("basemap-switch");
  CONFIG.basemaps.options.forEach((b) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = b.name;
    btn.dataset.basemap = b.id;
    btn.setAttribute("aria-pressed", String(b.id === state.basemap));
    btn.onclick = () => {
      setState({ basemap: b.id });
      setBasemap(b.id);
      baseSwitch.querySelectorAll("button").forEach((o) => o.setAttribute("aria-pressed", String(o === btn)));
    };
    baseSwitch.append(btn);
  });
  $("satellite-toggle").onchange = (e) => {
    setState({ satellite: e.target.checked });
    if (!e.target.checked) $("sat-badge").hidden = true;
  };
  // Honest about which day the image shows (it keeps the last fully loaded day while the next one loads)
  onSatelliteDate((date) => {
    $("sat-badge").hidden = !state.satellite;
    $("sat-badge").textContent = `Satellite image · ${fmtDay(date)} · NASA VIIRS`;
  });

  // Presenter keys (docs/demo-script.md). WCAG 2.1.4: single-key shortcuts can be turned off (remembered per visitor),
  // never fire with a modifier, and leave Space and the arrows to whatever control has focus (buttons, slider, map).
  let shortcuts = true;
  try { shortcuts = localStorage.getItem("ulinautas-shortcuts") !== "off"; } catch { /* storage blocked: on */ }
  $("shortcuts-toggle").checked = shortcuts;
  $("shortcuts-toggle").onchange = (e) => {
    shortcuts = e.target.checked;
    try { localStorage.setItem("ulinautas-shortcuts", shortcuts ? "on" : "off"); } catch { /* fine */ }
  };
  window.addEventListener("keydown", (e) => {
    if (!shortcuts || e.ctrlKey || e.altKey || e.metaKey) return;
    if (e.target.closest?.("input, textarea, select, [contenteditable]")) return;
    const owned = e.target.closest?.("button, a[href], summary, [role=slider], #map");
    if (owned && (e.code === "Space" || e.key.startsWith("Arrow"))) return;
    const k = e.key.toLowerCase();
    if (e.code === "Space") { e.preventDefault(); timeline.toggle(); }
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
