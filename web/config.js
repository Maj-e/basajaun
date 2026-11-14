// Configuración del front. La zona de demo la define B2 (W0-B2): cambiar BBOX aquí cuando esté elegida.
export const CONFIG = {
  // oeste, sur, este, norte — provisional
  bbox: [-72.0, -38.0, -70.0, -33.0],
  // Carpeta de datos, siempre relativa: data/sample/ hasta que el backend publique data/processed/
  dataBase: "data/sample/",
  // Fondo de carta vectorial gratuito, sin clave
  basemap: "https://tiles.openfreemap.org/styles/positron",
};
