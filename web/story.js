// Story beat of the demo (docs/demo-script.md), computed from the data — never hard-coded.
// peak = day with the most fires (highlighted bar + "Peak" button on the timeline).

const H = 3600 * 1000;
export const dayOf = (t) => new Date(t * H).toISOString().slice(0, 10);
const dayStart = (day) => Date.parse(`${day}T00:00:00Z`) / H;
export const fmtTime = (t) => {
  const d = new Date(t * H);
  return `${d.getUTCDate()} ${d.toLocaleString("en", { month: "short", timeZone: "UTC" })} · ${String(d.getUTCHours()).padStart(2, "0")}:${String(d.getUTCMinutes()).padStart(2, "0")} UTC`;
};

export function computeStory(features, days, counts) {
  const story = {};
  if (days.length && days.some((d) => counts[d] > 0)) {
    const i = days.reduce((best, d, k) => (counts[d] > counts[days[best]] ? k : best), 0);
    story.peak = { day: days[i], index: i, count: counts[days[i]], end: dayStart(days[i]) + 24 - 0.01 };
  }
  return story;
}
