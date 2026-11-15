// Alerts (W3-F2, typed in W3-F5), from alerts.json written by scripts/exposure.py (W3-B1, W3-B8).
// One fire can have several alerts, one per type (population, smoke, wind, contamination), each with a message.
// Panel on the right: filter chips per type + the most severe alerts. On the map (box "Alerts on the map"):
// one ring per type around the fire, concentric so they never hide each other. No file → nothing is shown.
import { map } from "./map.js";
import { CONFIG } from "./config.js";

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

let alerts = [];
let shownKey = null;
let lastArgs = null;
const markers = new Map();
const selected = new Set(); // empty = all types

// Alerts on the map: only when the box is ticked; the list on the right is always there
export function setAlertLabels(on) {
  document.body.classList.toggle("alert-labels", on);
}

export async function loadAlerts() {
  try {
    const r = await fetch(CONFIG.alerts);
    if (!r.ok) return [];
    const data = await r.json();
    alerts = (Array.isArray(data) ? data : data.alerts ?? [])
      .filter((a) => a.since && Array.isArray(a.center))
      .map((a) => ({ ...a, t: Date.parse(a.since) / H, kind: typeOf(a), key: `${a.fire_id}-${typeOf(a)}` }));
  } catch {
    alerts = [];
  }
  $("alerts").hidden = !alerts.length;
  $("alerts-toggle").onclick = () => {
    const list = $("alerts-list");
    list.hidden = !list.hidden;
    $("alerts-toggle").setAttribute("aria-expanded", String(!list.hidden));
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
  el.querySelector(".halo").onclick = () => new maplibregl.Popup({ offset: ty.ring + 6 }).setLngLat(a.center).setHTML(
    `<strong style="color:${ty.color}">${ty.label} · ${a.risk}</strong>` +
    `<p class="popup-msg">${a.message ?? ""}</p>` +
    `<table class="popup"><tr><th>Within 1 km</th><td>${fmtPop(a.pop_1km)} people</td></tr>` +
    `<tr><th>Within 5 km</th><td>${fmtPop(a.pop_5km)} people</td></tr>` +
    `<tr><th>Within 10 km</th><td>${fmtPop(a.pop_10km)} people</td></tr>` +
    `<tr><th>Since</th><td>${fmtTime(a.t)}</td></tr></table>`).addTo(map);
  return new maplibregl.Marker({ element: el }).setLngLat(a.center);
}

// Alerts that have started at `hour`, belong to the current scope (inScope(alert) → boolean) and match the filters
export function renderAlerts(hour, inScope) {
  lastArgs = [hour, inScope];
  if (!alerts.length) return;
  const started = alerts.filter((a) => a.t <= hour && inScope(a));
  const active = started
    .filter((a) => !selected.size || selected.has(a.kind))
    .sort((a, b) => RANK[a.risk] - RANK[b.risk] || (b.pop_5km ?? 0) - (a.pop_5km ?? 0));
  const key = active.map((a) => a.key).join(",") + "|" + started.length;
  if (key === shownKey) return;
  shownKey = key;

  // Counts per type on the chips
  const newCounts = {};
  started.forEach((a) => (newCounts[a.kind] = (newCounts[a.kind] ?? 0) + 1));
  if (JSON.stringify(newCounts) !== JSON.stringify(counts)) { counts = newCounts; renderFilters(); }

  // One row per fire: worst risk first, its types as icons, the most severe message, details on demand
  const fires = new Map();
  for (const a of active) {
    if (!fires.has(a.fire_id)) fires.set(a.fire_id, []);
    fires.get(a.fire_id).push(a);
  }
  const groups = [...fires.values()];
  const top = groups.slice(0, MAX_SHOWN);
  $("alerts-count").textContent = active.length;
  if ($("mb-alerts")) $("mb-alerts").textContent = active.length;
  $("alerts-title").textContent = active.length ? `${groups.length} fire${groups.length > 1 ? "s" : ""} · ` : "";
  $("alerts-toggle").classList.toggle("has-critical", active.some((a) => a.risk === "critical"));
  $("alerts-list").innerHTML = groups.length
    ? top.map((g) => {
      const lead = g[0];
      const kinds = [...new Set(g.map((a) => a.kind))];
      return `<li class="fire-row" data-fire="${lead.fire_id}">
        <button type="button" class="fire-head" aria-expanded="false">
          <span class="risk"><em style="color:${lead.color}">${lead.risk}</em>${kinds.map((k) => `<span class="type" style="--c:${TYPES[k].color}" title="${TYPES[k].label}">${icon(k)}</span>`).join("")}</span>
          <span class="who">${lead.message ?? `${fmtPop(lead.pop_5km)} people within 5 km`}</span>
          <span class="when">since ${fmtTime(Math.min(...g.map((a) => a.t)))}${g.length > 1 ? ` · ${g.length} alerts` : ""}</span>
        </button>
        <ul class="fire-details" hidden>${g.map((a) => `<li style="--c:${TYPES[a.kind].color}">${icon(a.kind)}<span><b>${TYPES[a.kind].label}</b> · ${a.risk} — ${a.message ?? ""}</span></li>`).join("")}</ul>
      </li>`;
    }).join("") +
      (groups.length > MAX_SHOWN ? `<li class="none">+ ${groups.length - MAX_SHOWN} more fires · zoom in to see them</li>` : "")
    : `<li class="none">No alert at this time</li>`;
  $("alerts-list").querySelectorAll(".fire-row").forEach((row) => {
    const g = fires.get(Number(row.dataset.fire)) ?? fires.get(row.dataset.fire);
    const head = row.querySelector(".fire-head");
    head.onclick = () => {
      const details = row.querySelector(".fire-details");
      details.hidden = !details.hidden;
      head.setAttribute("aria-expanded", String(!details.hidden));
      if (!details.hidden) map?.flyTo({ center: g[0].center, zoom: 10 });
    };
    // Hovering a row makes its rings stand out on the map
    row.onmouseenter = () => g.forEach((a) => markers.get(a.key)?.getElement().classList.add("hot"));
    row.onmouseleave = () => g.forEach((a) => markers.get(a.key)?.getElement().classList.remove("hot"));
  });

  if (!map) return;
  const shownAlerts = top.flat();
  const onMap = new Set(shownAlerts.filter((a) => a.risk === "critical" || a.risk === "high").map((a) => a.key));
  for (const [k, m] of markers) if (!onMap.has(k)) { m.remove(); markers.delete(k); }
  for (const a of shownAlerts) if (onMap.has(a.key) && !markers.has(a.key)) markers.set(a.key, marker(a).addTo(map));
}
