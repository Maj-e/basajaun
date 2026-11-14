"""Generate the episode's manifest.json listing only the layers whose data file exists.

Default episode: web/data/manifest.json for the files in web/data/processed/. Other episodes
(EPISODE=<id>, see web/data/episodes.json): web/data/episodes/<id>/manifest.json.

Every layer the project knows is declared once in LAYERS below. A layer appears
in the manifest only when its file is present under web/data/, so the front end
never asks for a missing file.

Adding a layer = its script writes the file + one entry in LAYERS
(`active: False` until it has been checked on the published URL).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import rasterio

from config import BBOX, MANIFEST, PROCESSED, WEB_DATA

DATA_DIR = WEB_DATA  # manifest `file` paths are relative to web/data/
EPISODE_SUBDIR = PROCESSED.relative_to(WEB_DATA).as_posix()  # "processed" or "episodes/<id>"

_west, _south, _east, _north = BBOX
# Image corners: top-left, top-right, bottom-right, bottom-left
BBOX_CORNERS = [[_west, _north], [_east, _north], [_east, _south], [_west, _south]]

LAYERS: list[dict] = [
    {
        "id": "hotspots",
        "name": "Fire hotspots",
        "file": "processed/hotspots.geojson",
        "type": "circle",
        "temporal": True,
        "active": True,
        "popup": ["sensor", "satellite", "timestamp_utc", "confidence", "frp", "country", "region"],
        "legend": [
            {"color": "#d7301f", "text": "High confidence"},
            {"color": "#fc8d59", "text": "Medium confidence"},
            {"color": "#fdcc8a", "text": "Low confidence"},
        ],
    },
    {
        "id": "regions",
        "name": "Regions",
        "file": "processed/regions.geojson",
        "type": "fill",
        "temporal": False,
        "active": False,
        "popup": ["country", "region"],
    },
    {
        "id": "fires",
        "name": "Fires",
        "file": "processed/fires.geojson",
        "type": "fill",
        "temporal": False,
        "active": True,
        "popup": ["fire_id", "start", "end", "n_hotspots", "frp_max", "area_km2",
                  "slope_deg", "landcover",
                  "dist_road_km", "dist_water_km", "dist_fire_station_km"],
    },
    {
        "id": "spread",
        "name": "6h spread estimate",
        "file": "processed/spread.geojson",
        "type": "fill",
        "temporal": False,
        "active": False,
        "popup": ["fire_id", "horizon_hours", "wind_speed_kmh", "wind_to_deg", "slope_deg",
                  "spread_km", "area_km2"],
    },
    {
        "id": "population",
        "name": "Population density",
        "file": "processed/population.png",
        "type": "image",
        "corners": BBOX_CORNERS,
        "temporal": False,
        "active": False,
        "legend": [
            {"color": "#fee5d9", "text": "< 10 people/km²"},
            {"color": "#a50f15", "text": "> 1000 people/km²"},
        ],
    },
    {
        "id": "wind",
        "name": "Wind",
        "file": "processed/weather.geojson",
        "type": "arrows",
        "temporal": True,
        "active": False,
        "popup": ["timestamp_utc", "speed", "direction"],
        "legend": [
            {"color": "#91cf60", "text": "< 15 km/h"},
            {"color": "#fee08b", "text": "15–30 km/h"},
            {"color": "#fc8d59", "text": "30–45 km/h"},
            {"color": "#d7301f", "text": "≥ 45 km/h"},
        ],
    },
    {
        "id": "weather",
        "name": "Weather",
        "file": "processed/weather.geojson",
        "type": "circle",
        "temporal": True,
        "active": True,
        "popup": ["timestamp_utc", "temperature", "humidity", "rain", "speed"],
    },
    {
        "id": "water",
        "name": "Water",
        "file": "processed/water.geojson",
        "type": "fill",
        "temporal": False,
        "active": False,
        "popup": ["name", "kind"],
        "legend": [{"color": "#3d8bd4", "text": "Lakes, reservoirs, rivers"}],
    },
    {
        "id": "roads",
        "name": "Roads",
        "file": "processed/roads.geojson",
        "type": "line",
        "temporal": False,
        "active": False,
        "popup": ["name", "highway"],
        # Colors match osm.ROAD_STYLE
        "legend": [
            {"color": "#f2a541", "text": "Primary"},
            {"color": "#f6c667", "text": "Secondary"},
            {"color": "#f9dfa0", "text": "Tertiary"},
            {"color": "#b08968", "text": "Track"},
            {"color": "#9c8b7a", "text": "Path"},
        ],
    },
    {
        "id": "fire_stations",
        "name": "Fire stations",
        "file": "processed/fire_stations.geojson",
        "type": "circle",
        "temporal": False,
        "active": False,
        "popup": ["name"],
        "legend": [{"color": "#2b8cbe", "text": "Fire station"}],
    },
]


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def file_updated(path: Path) -> str:
    """`updated_at` of a data file: its own `updated_at` field if it has one, else its modification time."""
    if path.suffix in {".json", ".geojson"}:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("updated_at"), str):
                return data["updated_at"]
        except json.JSONDecodeError:
            pass
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return mtime.strftime("%Y-%m-%dT%H:%M:%SZ")


def image_corners(png: Path) -> list[list[float]] | None:
    """Exact corners of an image layer from the GeoTIFF it was drawn from (same name, .tif), if present."""
    tif = png.with_suffix(".tif")
    if not tif.is_file():
        return None
    with rasterio.open(tif) as src:
        w, s, e, n = src.bounds
    return [[round(x, 6), round(y, 6)] for x, y in ((w, n), (e, n), (e, s), (w, s))]


def build_manifest(data_dir: Path = DATA_DIR, layers: list[dict] = LAYERS,
                   subdir: str = EPISODE_SUBDIR) -> dict:
    """LAYERS files are written as processed/<name>; they are looked up in `subdir` (the episode's folder)."""
    present = []
    for template in layers:
        layer = {**template, "file": f"{subdir}/{Path(template['file']).name}"}
        path = data_dir / layer["file"]
        if path.is_file():
            entry = {**layer, "updated_at": file_updated(path)}
            if layer["type"] == "image":
                entry["corners"] = image_corners(path) or layer["corners"]
            present.append(entry)
    return {"updated_at": utc_now(), "layers": present}


def main() -> None:
    manifest = build_manifest()
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    listed = {layer["id"]: layer for layer in manifest["layers"]}
    for layer in LAYERS:
        if layer["id"] in listed:
            state = "active" if layer["active"] else "disabled"
            print(f"  + {layer['id']:<14} {listed[layer['id']]['file']} ({state})")
        else:
            print(f"  - {layer['id']:<14} {EPISODE_SUBDIR}/{Path(layer['file']).name} not found, skipped")
    print(f"[SAVED] {MANIFEST} ({len(listed)}/{len(LAYERS)} layers)")


if __name__ == "__main__":
    main()
