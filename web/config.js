// Front-end configuration. The demo area is chosen by B2 (W0-B2): update `bbox` here once it is decided.
export const CONFIG = {
  // west, south, east, north — provisional (central Chile)
  bbox: [-72.0, -38.0, -70.0, -33.0],
  // Data root: the `file` paths in the manifest are relative to this folder
  dataRoot: "data/",
  // Layer manifest: data/sample/manifest.json until the backend publishes data/manifest.json
  manifest: "data/sample/manifest.json",
  // Free vector basemap, no API key
  basemap: "https://tiles.openfreemap.org/styles/positron",
};
