// Punto de entrada: conecta los módulos. Cada wave agrega aquí su import (filtros, calendario…).
import { map, mapaListo } from "./map.js";
import { CONFIG } from "./config.js";
import { capas, cargarCapas } from "./layers/loader.js";

const estado = document.getElementById("estado");

mapaListo
  .then(cargarCapas)
  .then(() => {
    estado.textContent = CONFIG.manifest.includes("sample") ? "Datos de ejemplo" : "Datos reales";
  })
  .catch((err) => {
    console.error(err);
    estado.textContent = "Datos no disponibles";
  });

// Solo se señalan los errores de nuestras capas (no los de una tesela del fondo de mapa).
map.on("error", (e) => {
  if (e.sourceId && capas.has(e.sourceId)) {
    console.error(e.error);
    estado.textContent = `Capa no disponible: ${capas.get(e.sourceId).capa.nombre}`;
  }
});
