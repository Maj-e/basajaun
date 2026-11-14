// Punto de entrada: conecta los módulos. Cada wave agrega aquí su import (loader, filtros, calendario…).
import { map, mapaListo } from "./map.js";
import { CONFIG } from "./config.js";

const estado = document.getElementById("estado");

mapaListo.then(() => {
  estado.textContent = CONFIG.dataBase.includes("sample") ? "Datos de ejemplo" : "Datos reales";
});

map.on("error", (e) => {
  console.error(e.error);
  estado.textContent = "Error al cargar el mapa";
});
