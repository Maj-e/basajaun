// Population alerts (W3-F2), from alerts.json written by scripts/exposure.py (W3-B1).
// On the map: a halo + label on critical and high alerts once they start. On the right: a collapsed panel with the count and the list.
// No file → nothing is shown (never placeholder numbers).
import { map } from "./map.js";
import { CONFIG } from "./config.js";

const H = 3600 * 1000;
const RANK = { critical: 0, high: 1, medium: 2, low: 3 };
const $ = (id) => document.getElementById(id);
const fmtPop = (n) => `≈${Math.round(n).toLocaleString("en")}`;
const fmtTime = (t) => {
  const d = new Date(t * H);
  return `${d.getUTCDate()} ${d.toLocaleString("en", { month: "short", timeZone: "UTC" })} · ${String(d.getUTCHours()).padStart(2, "0")}:${String(d.getUTCMinutes()).padStart(2, "0")} UTC`;
};

let alerts = [];
let shownKey = null;
const markers = new Map();
const MAX_SHOWN = 30; // large episodes (e.g. a whole country) can have hundreds of alerts: list and map the most severe
let labelsOn = false;

// Alerts on the map (circle + "≈N people within 5 km"): only when the box is ticked; the list on the right is always there
export function setAlertLabels(on) {
  labelsOn = on;
  document.body.classList.toggle("alert-labels", on);
}

export async function loadAlerts() {
  try {
    const r = await fetch(CONFIG.alerts);
    if (!r.ok) return [];
    const data = await r.json();
    alerts = (Array.isArray(data) ? data : data.alerts ?? [])
      .filter((a) => a.since && Array.isArray(a.center))
      .map((a) => ({ ...a, t: Date.parse(a.since) / H }));
  } catch {
    alerts = [];
  }
  $("alerts").hidden = !alerts.length;
  $("alerts-toggle").onclick = () => {
    const list = $("alerts-list");
    list.hidden = !list.hidden;
    $("alerts-toggle").setAttribute("aria-expanded", String(!list.hidden));
  };
  return alerts;
}

function marker(a) {
  const el = document.createElement("div");
  el.className = `alert-mark risk-${a.risk}`;
  el.style.setProperty("--c", a.color);
  el.innerHTML = `<button type="button" class="halo" aria-label="${a.risk} alert: ${fmtPop(a.pop_5km)} people within 5 km"></button><span class="label">${fmtPop(a.pop_5km)} people within 5 km</span>`;
  el.querySelector(".halo").onclick = () => new maplibregl.Popup({ offset: 30 }).setLngLat(a.center).setHTML(
    `<strong style="color:${a.color};text-transform:uppercase">${a.risk} alert</strong>` +
    `<table class="popup"><tr><th>Within 1 km</th><td>${fmtPop(a.pop_1km)} people</td></tr>` +
    `<tr><th>Within 5 km</th><td>${fmtPop(a.pop_5km)} people</td></tr>` +
    `<tr><th>Within 10 km</th><td>${fmtPop(a.pop_10km)} people</td></tr>` +
    `<tr><th>Since</th><td>${fmtTime(a.t)}</td></tr>` +
    (a.wind_toward_population ? `<tr><th>Wind</th><td>toward people</td></tr>` : "") + `</table>`).addTo(map);
  return new maplibregl.Marker({ element: el }).setLngLat(a.center);
}

// Alerts that have started at `hour` and belong to the current scope (inScope(alert) → boolean).
export function renderAlerts(hour, inScope) {
  if (!alerts.length) return;
  const active = alerts
    .filter((a) => a.t <= hour && inScope(a))
    .sort((a, b) => RANK[a.risk] - RANK[b.risk] || b.pop_5km - a.pop_5km);
  const key = active.map((a) => a.fire_id).join(",");
  if (key === shownKey) return;
  shownKey = key;

  $("alerts-count").textContent = active.length;
  $("alerts-toggle").classList.toggle("has-critical", active.some((a) => a.risk === "critical"));
  const top = active.slice(0, MAX_SHOWN);
  $("alerts-list").innerHTML = active.length
    ? top.map((a) => `
      <li><button type="button" data-fire="${a.fire_id}">
        <span class="risk" style="--c:${a.color}">${a.risk}</span>
        <span class="who"><b>${fmtPop(a.pop_5km)}</b> people within 5 km</span>
        <span class="when">since ${fmtTime(a.t)}${a.wind_toward_population ? " · wind toward people" : ""}</span>
      </button></li>`).join("") +
      (active.length > MAX_SHOWN ? `<li class="none">+ ${active.length - MAX_SHOWN} more · zoom in to see them</li>` : "")
    : `<li class="none">No alert at this time</li>`;
  $("alerts-list").querySelectorAll("[data-fire]").forEach((b) => (b.onclick = () => {
    const a = active.find((x) => String(x.fire_id) === b.dataset.fire);
    map?.flyTo({ center: a.center, zoom: 10 });
  }));

  if (!map) return;
  const onMap = new Set(top.filter((a) => a.risk === "critical" || a.risk === "high").map((a) => a.fire_id));
  for (const [id, m] of markers) if (!onMap.has(id)) { m.remove(); markers.delete(id); }
  for (const a of active) if (onMap.has(a.fire_id) && !markers.has(a.fire_id)) markers.set(a.fire_id, marker(a).addTo(map));
}
