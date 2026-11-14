// Configuración del front. La zona de demo la define B2 (W0-B2): cambiar BBOX aquí cuando esté elegida.
export const CONFIG = {
  // oeste, sur, este, norte — provisional
  bbox: [-72.0, -38.0, -70.0, -33.0],
  // Raíz de los datos: las rutas `archivo` del manifest son relativas a esta carpeta
  dataRoot: "data/",
  // Manifest de capas: data/sample/manifest.json hasta que el backend publique data/manifest.json
  manifest: "data/sample/manifest.json",
  // Fondo de carta vectorial gratuito, sin clave
  basemap: "https://tiles.openfreemap.org/styles/positron",
};
