// Estado compartido por todos los módulos (filtros, calendario, línea de tiempo, capas).
// Se lee con `state`, se cambia con `setState`, se reacciona con `subscribe`.
export const state = {
  fecha: null,                          // "AAAA-MM-DD" seleccionada
  rango: null,                          // ["AAAA-MM-DD", "AAAA-MM-DD"] o null
  sensores: ["MODIS", "VIIRS"],
  confianzas: ["baja", "media", "alta"],
  hora: null,                           // hora de la reproducción (t, horas desde 1970)
  capas: {},                            // id de capa → visible (true / false)
};

const listeners = [];

export function subscribe(fn) {
  listeners.push(fn);
}

export function setState(cambios) {
  Object.assign(state, cambios);
  listeners.forEach((fn) => fn(state));
}
