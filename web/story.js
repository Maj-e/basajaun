// Story beats of the demo (docs/demo-script.md), computed from the data — never hard-coded.
// spark = strongest hotspot; peak = day with the most fires.
import { map } from "./map.js";

const H = 3600 * 1000;
export const dayOf = (t) => new Date(t * H).toISOString().slice(0, 10);
const dayStart = (day) => Date.parse(`${day}T00:00:00Z`) / H;
export const fmtTime = (t) => {
  const d = new Date(t * H);
  return `${d.getUTCDate()} ${d.toLocaleString("en", { month: "short", timeZone: "UTC" })} · ${String(d.getUTCHours()).padStart(2, "0")}:${String(d.getUTCMinutes()).padStart(2, "0")} UTC`;
};

export function computeStory(features, days, counts) {
  const story = {};
  const withFrp = features.filter((f) => Number.isFinite(f.properties.frp));
  if (withFrp.length) {
    const s = withFrp.reduce((a, b) => (b.properties.frp > a.properties.frp ? b : a));
    const t = s.properties.t, start = Math.floor(t / 24) * 24;
    const before = withFrp.filter((f) => f.properties.t < start).map((f) => f.properties.frp);
    const prevMax = before.length ? Math.max(...before) : null;
    story.spark = {
      t, frp: s.properties.frp, lngLat: s.geometry.coordinates,
      ratio: prevMax ? Math.round(s.properties.frp / prevMax) : null,
      prevDays: Math.round((start - dayStart(days[0])) / 24),
    };
  }
  if (days.length && days.some((d) => counts[d] > 0)) {
    const i = days.reduce((best, d, k) => (counts[d] > counts[days[best]] ? k : best), 0);
    story.peak = { day: days[i], index: i, count: counts[days[i]], prevCount: i > 0 ? counts[days[i - 1]] : null, end: dayStart(days[i]) + 24 - 0.01 };
  }
  return story;
}

let sparkMarkers = null, sparkFor = null;
function buildSparkMarkers(spark) {
  const ring = document.createElement("div");
  ring.className = "spark-ring";
  const note = document.createElement("div");
  note.className = "callout";
  const ratio = spark.ratio && spark.ratio > 1 && spark.prevDays > 0
    ? ` — ${spark.ratio}× the strongest fire of the previous ${spark.prevDays} days` : "";
  note.innerHTML = `<b>The spark · ${fmtTime(spark.t)}</b><span class="big">${Math.round(spark.frp).toLocaleString("en")} MW</span> fire intensity${ratio}`;
  return [
    new maplibregl.Marker({ element: ring }).setLngLat(spark.lngLat),
    new maplibregl.Marker({ element: note, anchor: "left", offset: [42, 0] }).setLngLat(spark.lngLat),
  ];
}

// Show the beats that belong to the current playback hour.
export function renderStory(story, hour) {
  if (map && sparkFor !== story.spark) {
    // The story changed (new visible area): drop the old spark callout
    sparkMarkers?.forEach((m) => m.remove());
    sparkMarkers = story.spark ? buildSparkMarkers(story.spark) : null;
    sparkFor = story.spark;
  }
  if (sparkMarkers) {
    const on = hour >= story.spark.t && hour < story.spark.t + 18;
    sparkMarkers.forEach((m) => (on ? m.addTo(map) : m.remove()));
  }
  const banner = document.getElementById("peak-banner");
  if (story.peak && story.peak.count > 0) {
    const start = story.peak.end - 24;
    banner.hidden = !(hour >= start && hour < story.peak.end + 8);
  } else banner.hidden = true;
}

export function fillPeakBanner(story) {
  if (!story.peak || !story.peak.count) return;
  const d = new Date(`${story.peak.day}T00:00:00Z`);
  document.getElementById("peak-count").textContent = `${story.peak.count} fires`;
  document.getElementById("peak-text").textContent = `on ${d.getUTCDate()} ${d.toLocaleString("en", { month: "short", timeZone: "UTC" })}` +
    (story.peak.prevCount !== null ? `, up from ${story.peak.prevCount} the day before` : "");
}
