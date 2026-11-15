// Alerts (W3-F2, typed in W3-F5), from alerts.json written by scripts/exposure.py (W3-B1, W3-B8).
// One fire can have several alerts, one per type (population, smoke, wind, contamination), each with a message.
// Panel on the right: filter chips per type + the most severe alerts. On the map (box "Alerts on the map"):
// one ring per type around the fire, concentric so they never hide each other. No file → nothing is shown.
import { map } from "./map.js";
import { CONFIG } from "./config.js";
import { keepInView, layers } from "./layers/loader.js";

const H = 3600 * 1000;
const RANK = { critical: 0, high: 1, medium: 2, low: 3 };
const MAX_SHOWN = 30; // large episodes can have hundreds of alerts: list and map the most severe
const ICON = {
  population: '<path d="M8 7.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Zm-4.5 6c0-2.5 2-4.2 4.5-4.2s4.5 1.7 4.5 4.2Z"/>',
  smoke: '<path d="M4.5 12.5h7a2.6 2.6 0 0 0 .3-5.2A3.6 3.6 0 0 0 5 6.6a2.9 2.9 0 0 0-.5 5.9Z"/>',
  wind: '<path d="M2 6h7.5a2 2 0 1 0-2-2M2 9.5h10a2 2 0 1 1-2 2M2 13h5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>',
  contamination: '<path d="M8 2.2S4 7 4 9.8a4 4 0 0 0 8 0C12 7 8 2.2 8 2.2Z"/>',
};
const TYPES = {
  population: { label: "Population", color: "#ff6b6b", ring: 22 },
  smoke: { label: "Smoke", color: "#c3b1e1", ring: 30 },
  contamination: { label: "Water", color: "#5aa9ff", ring: 38 },
  wind: { label: "Wind", color: "#7fe3f0", ring: 46 },
};
const typeOf = (a) => TYPES[a.type] ? a.type : "population";
const icon = (t) => `<svg class="alert-icon" viewBox="0 0 16 16" aria-hidden="true" fill="currentColor">${ICON[t]}</svg>`;
const $ = (id) => document.getElementById(id);
const fmtPop = (n) => `≈${Math.round(n).toLocaleString("en")}`;
const fmtTime = (t) => {
  const d = new Date(t * H);
  return `${d.getUTCDate()} ${d.toLocaleString("en", { month: "short", timeZone: "UTC" })} · ${String(d.getUTCHours()).padStart(2, "0")}:${String(d.getUTCMinutes()).padStart(2, "0")} UTC`;
};

// Readable risk colors on the dark panel (the data's own colors are map colors, too dark for text)
const RISK_COLOR = { critical: "#ff5a52", high: "#ff9a3c", medium: "#f2c94c", low: "#8aa0b8" };

// Where each fire is: the region most of its hotspots fall in ("Cataluña/Catalunya" → "Cataluña")
const places = new Map();
export function setFirePlaces(hotspots) {
  const tally = new Map();
  for (const f of hotspots) {
    const { fire_id: id, region, country } = f.properties;
    if (id === null || id === undefined || !(region || country)) continue;
    let name = String(region || country).split("/")[0].trim();
    if (name === name.toUpperCase()) name = name.toLowerCase().replace(/(^|[\s-])\p{L}/gu, (c) => c.toUpperCase()); // "COIMBRA" → "Coimbra"
    if (!tally.has(id)) tally.set(id, new Map());
    const t = tally.get(id);
    t.set(name, (t.get(name) ?? 0) + 1);
  }
  places.clear();
  for (const [id, t] of tally) places.set(Number(id), [...t].sort((a, b) => b[1] - a[1])[0][0]);
  shownKey = null;
}

let alerts = [];
let detailFire = null; // fire shown in the detail view (null = the list)
let handlers = { select: () => {}, clear: () => {} }; // wired by app.js: isolate a fire / back to the whole area
let shownKey = null;
let lastArgs = null;
const markers = new Map();
const selected = new Set(); // empty = all types

// Alerts on the map: only when the box is ticked; the list on the right is always there
export function setAlertLabels(on) {
  document.body.classList.toggle("alert-labels", on);
}

// Requested as soon as the module loads, in parallel with the manifest and the layers
const alertsRequest = fetch(CONFIG.alerts).then((r) => (r.ok ? r.json() : null)).catch(() => null);

export async function loadAlerts() {
  try {
    const data = await alertsRequest;
    if (!data) return [];
    alerts = (Array.isArray(data) ? data : data.alerts ?? [])
      .filter((a) => a.since && Array.isArray(a.center))
      .map((a) => ({ ...a, t: Date.parse(a.since) / H, kind: typeOf(a), key: `${a.fire_id}-${typeOf(a)}` }));
  } catch {
    alerts = [];
  }
  $("alerts").hidden = !alerts.length;
  // The header folds the whole panel (filters + list), remembered per visitor
  const fold = (folded) => {
    $("alerts-body").hidden = folded;
    $("alerts").classList.toggle("folded", folded);
    $("alerts-toggle").setAttribute("aria-expanded", String(!folded));
  };
  let folded = false;
  try { folded = localStorage.getItem("ulinautas-alerts") === "folded"; } catch { /* storage blocked */ }
  fold(folded);
  $("alerts-toggle").onclick = () => {
    folded = !folded;
    fold(folded);
    try { localStorage.setItem("ulinautas-alerts", folded ? "folded" : "open"); } catch { /* fine */ }
  };
  renderFilters();
  return alerts;
}

// Filter chips: one per type present in the episode
let counts = {}; // alerts per type at the current hour (before the type filter)
function renderFilters() {
  const present = Object.keys(TYPES).filter((t) => alerts.some((a) => a.kind === t));
  const el = $("alerts-filters");
  if (!el) return;
  el.hidden = present.length < 2;
  el.innerHTML = `<button type="button" data-type="" aria-pressed="${!selected.size}">All</button>` +
    present.map((t) => `<button type="button" data-type="${t}" aria-pressed="${selected.has(t)}" style="--c:${TYPES[t].color}">${icon(t)}${TYPES[t].label}<span class="n">${counts[t] ?? 0}</span></button>`).join("");
  el.querySelectorAll("button").forEach((b) => (b.onclick = () => {
    const t = b.dataset.type;
    if (!t) selected.clear(); else if (selected.has(t)) selected.delete(t); else selected.add(t);
    shownKey = null;
    renderFilters();
    if (lastArgs) renderAlerts(...lastArgs);
  }));
}

function marker(a) {
  const ty = TYPES[a.kind];
  const el = document.createElement("div");
  el.className = `alert-mark risk-${a.risk}`;
  el.style.setProperty("--c", ty.color);
  el.style.setProperty("--r", `${ty.ring}px`);
  el.innerHTML = `<button type="button" class="halo" aria-label="${ty.label} alert: ${a.message ?? ""}"></button>` +
    (a.kind === "population" ? `<span class="label">${a.message ?? `${fmtPop(a.pop_5km)} people within 5 km`}</span>` : "");
  el.querySelector(".halo").onclick = () => keepInView(new maplibregl.Popup({ offset: ty.ring + 6, maxWidth: "300px" }).setLngLat(a.center).setHTML(
    `<strong style="color:${ty.color}">${ty.label} · ${a.risk}</strong>` +
    `<p class="popup-msg">${a.message ?? ""}</p>` +
    `<table class="popup"><tr><th>Within 1 km</th><td>${fmtPop(a.pop_1km)} people</td></tr>` +
    `<tr><th>Within 5 km</th><td>${fmtPop(a.pop_5km)} people</td></tr>` +
    `<tr><th>Within 10 km</th><td>${fmtPop(a.pop_10km)} people</td></tr>` +
    `<tr><th>Since</th><td>${fmtTime(a.t)}</td></tr></table>`).addTo(map));
  return new maplibregl.Marker({ element: el }).setLngLat(a.center);
}

// app.js tells the panel what to do when a fire is picked here, and which fire the map has isolated
export function setAlertHandlers(h) { handlers = { ...handlers, ...h }; }
export function showAlertFire(id) {
  detailFire = id === null || id === undefined ? null : Number(id);
  shownKey = null;
  if (lastArgs) renderAlerts(...lastArgs);
}

const typeIcons = (kinds) => kinds.map((k) => `<span class="type" style="--c:${TYPES[k].color}" title="${TYPES[k].label}">${icon(k)}</span>`).join("");
const badge = (risk) => `<em class="badge" style="--risk:${RISK_COLOR[risk]}">${risk}</em>`;
const num = (n) => Math.round(n).toLocaleString("en");

// Alerts that have started at `hour`, belong to the current scope (inScope(alert) → boolean) and match the filters
export function renderAlerts(hour, inScope) {
  lastArgs = [hour, inScope];
  if (!alerts.length) return;
  const started = alerts.filter((a) => a.t <= hour && inScope(a));
  const active = started
    .filter((a) => !selected.size || selected.has(a.kind))
    .sort((a, b) => RANK[a.risk] - RANK[b.risk] || (b.pop_5km ?? 0) - (a.pop_5km ?? 0));
  const key = `${detailFire}|` + active.map((a) => a.key).join(",") + "|" + started.length;
  if (key === shownKey) return;
  shownKey = key;

  // Counts per type on the chips
  const newCounts = {};
  started.forEach((a) => (newCounts[a.kind] = (newCounts[a.kind] ?? 0) + 1));
  if (JSON.stringify(newCounts) !== JSON.stringify(counts)) { counts = newCounts; renderFilters(); }

  // One row per fire, worst risk first
  const fires = new Map();
  for (const a of active) {
    if (!fires.has(a.fire_id)) fires.set(a.fire_id, []);
    fires.get(a.fire_id).push(a);
  }
  const groups = [...fires.values()];
  const top = groups.slice(0, MAX_SHOWN);
  const critical = groups.filter((g) => g[0].risk === "critical").length;
  if ($("mb-alerts")) $("mb-alerts").textContent = groups.length;
  $("alerts").classList.toggle("detail", detailFire !== null);

  let onMapAlerts;
  if (detailFire !== null) {
    // ---------- Detail of one fire: the list waits behind the Back button ----------
    const own = started.filter((a) => Number(a.fire_id) === detailFire)
      .sort((a, b) => RANK[a.risk] - RANK[b.risk]);
    const place = places.get(detailFire) ?? "Fire";
    $("alerts-title").textContent = "1 fire selected";
    $("alerts-count").hidden = true; // the risk is next to the fire's name
    $("alerts-toggle").classList.remove("has-critical");
    $("alerts-detail").innerHTML = renderDetail(detailFire, place, own);
    $("alerts-back").onclick = () => handlers.clear();
    onMapAlerts = own;
  } else {
    // ---------- List of fires ----------
    $("alerts-title").textContent = groups.length ? `${groups.length} fire${groups.length > 1 ? "s" : ""}` : "none now";
    $("alerts-count").hidden = false;
    $("alerts-count").textContent = critical ? `${critical} critical` : groups.length;
    $("alerts-count").title = `${active.length} alerts on ${groups.length} fires`;
    $("alerts-toggle").classList.toggle("has-critical", critical > 0);
    $("alerts-list").innerHTML = groups.length
      ? top.map((g) => {
        const lead = g[0];
        const kinds = [...new Set(g.map((a) => a.kind))];
        const people = g.find((a) => a.kind === "population");
        const what = people ? `<b class="ppl">${num(people.pop_5km)}</b> people within 5 km` : lead.message ?? "";
        return `<li><button type="button" class="fire-row" data-fire="${lead.fire_id}">
            <span class="r1"><span class="place">${places.get(Number(lead.fire_id)) ?? "Fire"}</span><span class="fid">#${lead.fire_id}</span>${badge(lead.risk)}</span>
            <span class="r2"><span class="what">${what}</span><span class="types">${typeIcons(kinds)}</span></span>
            <svg class="go" width="12" height="12" viewBox="0 0 12 12" aria-hidden="true"><path d="M4.5 2.5 8 6l-3.5 3.5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
          </button></li>`;
      }).join("") +
        (groups.length > MAX_SHOWN ? `<li class="none">+ ${groups.length - MAX_SHOWN} more fires · zoom in to see them</li>` : "")
      : `<li class="none">No alert at this time</li>`;
    $("alerts-list").querySelectorAll(".fire-row").forEach((row) => {
      const g = fires.get(Number(row.dataset.fire)) ?? fires.get(row.dataset.fire);
      row.onclick = () => handlers.select(Number(row.dataset.fire), g[0].center);
      // Hovering a row makes its rings stand out on the map
      row.onmouseenter = () => g.forEach((a) => markers.get(a.key)?.getElement().classList.add("hot"));
      row.onmouseleave = () => g.forEach((a) => markers.get(a.key)?.getElement().classList.remove("hot"));
    });
    onMapAlerts = top.flat();
  }

  if (!map) return;
  const onMap = new Set(onMapAlerts.filter((a) => a.risk === "critical" || a.risk === "high").map((a) => a.key));
  for (const [k, m] of markers) if (!onMap.has(k)) { m.remove(); markers.delete(k); }
  for (const a of onMapAlerts) if (onMap.has(a.key) && !markers.has(a.key)) markers.set(a.key, marker(a).addTo(map));
}

// One fire: who is exposed, what the alerts say, and the fire's own figures (only the computed ones)
function renderDetail(id, place, own) {
  const fire = layers.get("fires")?.data?.features?.find((f) => Number(f.properties.fire_id) === id)?.properties ?? {};
  const pop = own.find((a) => a.kind === "population");
  const has = (v) => v !== undefined && v !== null && v !== "";
  const facts = [
    ["To evacuate", fire.evacuate_people, (v) => `${num(v)} people`],
    ["To warn", fire.warn_people, (v) => `${num(v)} people`],
    ["Area", fire.area_km2, (v) => `${Number(v).toLocaleString("en", { maximumFractionDigits: 1 })} km²`],
    ["Peak intensity", fire.frp_max, (v) => `${num(v)} MW`],
    ["Hotspots", fire.n_hotspots, num],
    ["First detected", fire.t_start, fmtTime],
  ].filter(([, v]) => has(v));
  const rings = pop ? [["1 km", pop.pop_1km], ["5 km", pop.pop_5km], ["10 km", pop.pop_10km]].filter(([, v]) => has(v)) : [];
  return `<button type="button" class="back" id="alerts-back">
      <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true"><path d="M7.5 2.5 4 6l3.5 3.5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
      All fires</button>
    <div class="d-head"><h3>${place} <span class="fid">#${id}</span></h3>${own.length ? badge(own[0].risk) : ""}</div>
    ${rings.length ? `<div class="d-section"><h4>People nearby</h4><dl class="rings">${rings.map(([k, v]) => `<div><dt>within ${k}</dt><dd>${num(v)}</dd></div>`).join("")}</dl></div>` : ""}
    <div class="d-section"><h4>Alerts</h4>${own.length
      ? `<ul class="d-alerts">${own.map((a) => `<li style="--c:${TYPES[a.kind].color}">${icon(a.kind)}<div><b>${TYPES[a.kind].label}</b> ${badge(a.risk)}<p>${a.message ?? ""}</p><small>since ${fmtTime(a.t)}</small></div></li>`).join("")}</ul>`
      : `<p class="none">No alert for this fire at this time.</p>`}</div>
    ${facts.length ? `<div class="d-section"><h4>Fire</h4><dl class="facts">${facts.map(([k, v, f]) => `<div><dt>${k}</dt><dd>${f(v)}</dd></div>`).join("")}</dl></div>` : ""}`;
}
