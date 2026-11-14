// Timeline strip (fires per day) + playback engine.
// The engine owns state.hour; it pauses by itself on the story beats, like the presenter would.
import { state, setState } from "./state.js";

const H = 3600 * 1000;
const NS = "http://www.w3.org/2000/svg";
const $ = (id) => document.getElementById(id);
const svgEl = (tag, attrs) => { const n = document.createElementNS(NS, tag); for (const k in attrs) n.setAttribute(k, attrs[k]); return n; };

export function createTimeline({ days, counts, story, start, end, playFrom }) {
  const svg = $("chart"), W = 1400, Hc = 96, top = 22;
  const span = end - start;
  const x = (t) => ((t - start) / span) * W;
  const maxDay = Math.max(1, ...days.map((d) => counts[d]));
  const bw = W / days.length;

  // Bars: idle under the playhead's future, lit in its past (clip-path)
  const defs = svgEl("defs", {}), clip = svgEl("clipPath", { id: "played" }), clipRect = svgEl("rect", { x: 0, y: 0, width: 0, height: Hc });
  clip.appendChild(clipRect); defs.appendChild(clip); svg.appendChild(defs);
  svg.appendChild(svgEl("line", { x1: 0, x2: W, y1: Hc - 0.5, y2: Hc - 0.5, stroke: "#26344b", "stroke-width": 1, "vector-effect": "non-scaling-stroke" }));
  const idle = svgEl("g", {}), lit = svgEl("g", { "clip-path": "url(#played)" });
  days.forEach((d, i) => {
    const h = Math.max(2, (counts[d] / maxDay) * (Hc - top));
    const a = { x: i * bw + 3, y: Hc - h, width: bw - 6, height: h, rx: 3 };
    idle.appendChild(svgEl("rect", { ...a, fill: "#33251f" }));
    lit.appendChild(svgEl("rect", { ...a, fill: story.peak && i === story.peak.index ? "#f9a957" : "#c95b17" }));
  });
  svg.append(idle, lit);

  const mark = (t, label, color, side) => {
    svg.appendChild(svgEl("line", { x1: x(t), x2: x(t), y1: 2, y2: Hc, stroke: color, "stroke-width": 1, "stroke-dasharray": "3 3", "vector-effect": "non-scaling-stroke" }));
    const lab = document.createElement("div");
    lab.className = `strip-mark ${side}`;
    lab.textContent = label;
    lab.style.left = `${(x(t) / W) * 100}%`;
    lab.style.color = color;
    $("strip").appendChild(lab);
  };
  if (story.spark) mark(story.spark.t, "Spark", "#ffd9a8", "left");
  if (story.peak) mark(story.peak.end - 12, `Peak · ${story.peak.count}`, "#f9a957", "right");
  const head = svgEl("line", { x1: 0, x2: 0, y1: 0, y2: Hc, stroke: "#e8edf5", "stroke-width": 2, "vector-effect": "non-scaling-stroke" });
  svg.appendChild(head);
  const month = (d) => new Date(`${d}T00:00:00Z`).toLocaleString("en", { month: "short", timeZone: "UTC" });
  $("days").style.gridTemplateColumns = `repeat(${days.length}, 1fr)`;
  $("days").innerHTML = days.map((d, i) => `<span>${Number(d.slice(8))}${i === 0 ? ` <small>${month(d)}</small>` : ""}</span>`).join("");

  // Hover tooltip and scrubbing
  const tip = $("tip");
  const tAt = (e) => { const r = svg.getBoundingClientRect(); return start + ((e.clientX - r.left) / r.width) * span; };
  svg.addEventListener("pointermove", (e) => {
    const i = Math.min(days.length - 1, Math.max(0, Math.floor((tAt(e) - start) / 24)));
    tip.hidden = false;
    tip.textContent = `${Number(days[i].slice(8))} ${month(days[i])} · ${counts[days[i]]} fires`;
    tip.style.left = `${e.clientX - svg.getBoundingClientRect().left}px`;
    if (e.buttons === 1) seek(tAt(e));
  });
  svg.addEventListener("pointerleave", () => (tip.hidden = true));
  svg.addEventListener("pointerdown", (e) => { setPlaying(false); seek(tAt(e)); });

  // ---------- Engine ----------
  let seenSpark = false, seenPeak = false, holdUntil = 0, last = performance.now();
  function seek(t) {
    const hour = Math.min(Math.max(t, start), end - 0.01);
    seenSpark = story.spark ? hour >= story.spark.t : true;
    seenPeak = story.peak ? hour >= story.peak.end : true;
    holdUntil = 0;
    setState({ hour });
  }
  function setPlaying(playing) {
    setState({ playing });
    $("b-play").setAttribute("aria-label", playing ? "Pause" : "Play");
    $("i-play").innerHTML = playing ? '<path d="M4 2.5h3v11H4zM9 2.5h3v11H9z" fill="currentColor"/>' : '<path d="M4 2.5v11l9-5.5z" fill="currentColor"/>';
  }
  function frame(now) {
    const dt = Math.min(0.1, (now - last) / 1000); last = now;
    if (state.playing && now >= holdUntil) {
      let hour = state.hour;
      const next = hour + dt * state.speed;
      if (story.spark && !seenSpark && hour < story.spark.t && next >= story.spark.t) { hour = story.spark.t; seenSpark = true; holdUntil = now + 3500; }
      else if (story.peak && !seenPeak && hour < story.peak.end && next >= story.peak.end) { hour = story.peak.end; seenPeak = true; holdUntil = now + 3500; }
      else hour = next;
      if (hour >= end) { hour = playFrom; seenSpark = story.spark ? playFrom >= story.spark.t : true; seenPeak = story.peak ? playFrom >= story.peak.end : true; holdUntil = now + 1500; }
      setState({ hour });
    }
    requestAnimationFrame(frame);
  }

  // Clock + playhead follow state.hour
  function render(hour) {
    const d = new Date(hour * H);
    $("c-date").textContent = `${d.getUTCDate()} ${month(d.toISOString().slice(0, 10))} ${d.getUTCFullYear()}`;
    $("c-time").textContent = `${String(d.getUTCHours()).padStart(2, "0")}:${String(d.getUTCMinutes()).padStart(2, "0")} UTC`;
    head.setAttribute("x1", x(hour)); head.setAttribute("x2", x(hour));
    clipRect.setAttribute("width", Math.max(0, x(hour)));
  }

  return {
    render, seek, setPlaying,
    toggle: () => setPlaying(!state.playing),
    restart: () => { seek(playFrom); setPlaying(true); },
    jumpPeak: () => { if (story.peak) { setPlaying(false); seek(story.peak.end); } },
    jumpSpark: () => { if (story.spark) { setPlaying(false); seek(story.spark.t); } },
    step: (h) => { setPlaying(false); seek(state.hour + h); },
    start: () => requestAnimationFrame(frame),
  };
}
