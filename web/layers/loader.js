// Cargador genérico de capas (W1-F1).
// Lee el manifest y crea cada capa activa según su `tipo`, con el estilo que ya trae cada Feature.
// Agregar una capa = un archivo de datos + una entrada en el manifest: este archivo no cambia.
import { map } from "../map.js";
import { CONFIG } from "../config.js";

// Un constructor por tipo de capa. Un tipo nuevo (ej. "flechas" en W3-F1) = una entrada más aquí.
const TIPOS = {
  circle: (capa) => {
    agregarGeojson(capa);
    map.addLayer({
      id: capa.id,
      type: "circle",
      source: capa.id,
      paint: {
        "circle-color": ["coalesce", ["get", "color"], "#888888"],
        "circle-radius": ["coalesce", ["get", "radio"], 5],
        "circle-stroke-color": ["coalesce", ["get", "borde"], "#ffffff"],
        "circle-stroke-width": 1.5,
        "circle-opacity": ["coalesce", ["get", "opacidad"], 0.9],
      },
    });
    return [capa.id];
  },

  fill: (capa) => {
    agregarGeojson(capa);
    map.addLayer({
      id: capa.id,
      type: "fill",
      source: capa.id,
      paint: {
        "fill-color": ["coalesce", ["get", "color"], "#888888"],
        "fill-opacity": ["coalesce", ["get", "opacidad"], 0.35],
      },
    });
    map.addLayer({
      id: `${capa.id}-contorno`,
      type: "line",
      source: capa.id,
      paint: { "line-color": ["coalesce", ["get", "color"], "#888888"], "line-width": 1.5 },
    });
    return [capa.id, `${capa.id}-contorno`];
  },

  line: (capa) => {
    agregarGeojson(capa);
    map.addLayer({
      id: capa.id,
      type: "line",
      source: capa.id,
      paint: {
        "line-color": ["coalesce", ["get", "color"], "#888888"],
        "line-width": ["coalesce", ["get", "grosor"], 1.5],
      },
    });
    return [capa.id];
  },

  image: (capa) => {
    map.addSource(capa.id, { type: "image", url: url(capa.archivo), coordinates: capa.esquinas });
    map.addLayer({ id: capa.id, type: "raster", source: capa.id, paint: { "raster-opacity": 0.6 } });
    return [capa.id];
  },
};

const url = (archivo) => CONFIG.dataRoot + archivo;

function agregarGeojson(capa) {
  map.addSource(capa.id, { type: "geojson", data: url(capa.archivo) });
}

// Capas efectivamente cargadas: id → { capa, layers }. Lo usarán el panel de capas y los filtros.
export const capas = new Map();

export async function cargarCapas() {
  const respuesta = await fetch(CONFIG.manifest);
  if (!respuesta.ok) throw new Error(`Manifest no disponible (${respuesta.status})`);
  const manifest = await respuesta.json();

  for (const capa of manifest.capas.filter((c) => c.activa)) {
    const crear = TIPOS[capa.tipo];
    if (!crear) {
      console.warn(`Tipo de capa desconocido: "${capa.tipo}" (${capa.id})`);
      continue;
    }
    const layers = crear(capa);
    capas.set(capa.id, { capa, layers });
    if (capa.popup?.length) activarPopup(capa, layers[0]);
  }

  map.addControl(new Leyenda([...capas.values()].map((c) => c.capa)), "bottom-right");
  return manifest;
}

function activarPopup(capa, layerId) {
  map.on("mouseenter", layerId, () => (map.getCanvas().style.cursor = "pointer"));
  map.on("mouseleave", layerId, () => (map.getCanvas().style.cursor = ""));
  map.on("click", layerId, (e) => {
    const props = e.features[0].properties;
    const filas = capa.popup
      .filter((campo) => props[campo] !== undefined)
      .map((campo) => `<tr><th>${campo}</th><td>${props[campo]}</td></tr>`)
      .join("");
    new maplibregl.Popup()
      .setLngLat(e.lngLat)
      .setHTML(`<strong>${capa.nombre}</strong><table class="popup">${filas}</table>`)
      .addTo(map);
  });
}

// Leyenda generada desde el manifest, como control de MapLibre.
class Leyenda {
  constructor(capasConLeyenda) {
    this.capas = capasConLeyenda.filter((c) => c.leyenda?.length);
  }
  onAdd() {
    this.el = document.createElement("div");
    this.el.className = "maplibregl-ctrl leyenda";
    this.el.innerHTML = this.capas
      .map(
        (c) =>
          `<h3>${c.nombre}</h3>` +
          c.leyenda.map((l) => `<div><span style="background:${l.color}"></span>${l.texto}</div>`).join("")
      )
      .join("");
    if (!this.capas.length) this.el.hidden = true;
    return this.el;
  }
  onRemove() {
    this.el.remove();
  }
}
