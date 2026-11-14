// The two header readouts, computed from the hotspots at the playback hour.
import { CONFIG } from "./config.js";

const $ = (id) => document.getElementById(id);

export function renderReadouts(features, hour, firstDay) {
  const trail = CONFIG.trailHours;
  let active = 0, strongest = 0, total = 0;
  for (const f of features) {
    const { t, frp } = f.properties;
    if (t > hour) continue;
    total++;
    if (t > hour - trail) { active++; if (Number.isFinite(frp)) strongest = Math.max(strongest, frp); }
  }
  $("r-active").textContent = active.toLocaleString("en");
  $("r-total").textContent = `${total.toLocaleString("en")} since ${firstDay}`;
  $("r-frp").innerHTML = `${Math.round(strongest).toLocaleString("en")}<small>MW</small>`;
}
