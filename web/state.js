// State shared by every module (timeline, layers, readouts, story).
// Read it through `state`, change it with `setState`, react to changes with `subscribe`.
export const state = {
  hour: null,          // playback time (t, hours since 1970)
  playing: false,
  speed: 8,            // playback hours per second
  satellite: false,    // NASA daily imagery under the fires
  layers: {},          // layer id → visible (true / false)
};

const listeners = [];

export function subscribe(fn) {
  listeners.push(fn);
}

export function setState(changes) {
  Object.assign(state, changes);
  listeners.forEach((fn) => fn(state, changes));
}
