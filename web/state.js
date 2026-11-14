// State shared by every module (filters, calendar, timeline, layers).
// Read it through `state`, change it with `setState`, react to changes with `subscribe`.
export const state = {
  date: null,                          // selected "YYYY-MM-DD"
  range: null,                         // ["YYYY-MM-DD", "YYYY-MM-DD"] or null
  sensors: ["MODIS", "VIIRS"],
  confidences: ["low", "medium", "high"],
  hour: null,                          // playback time (t, hours since 1970)
  layers: {},                          // layer id → visible (true / false)
};

const listeners = [];

export function subscribe(fn) {
  listeners.push(fn);
}

export function setState(changes) {
  Object.assign(state, changes);
  listeners.forEach((fn) => fn(state));
}
