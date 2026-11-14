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
        "active": True,
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
                  "dist_road_km", "dist_water_km", "dist_fire_station_km",
                  "dist_water_point_km", "gw_body", "gw_vulnerability", "gw_chemical_status"],
    },
    {
        "id": "spread",
        "name": "6h spread estimate",
        "file": "processed/spread.geojson",
        "type": "fill",
        "temporal": False,
        "active": True,
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
        "active": True,
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
        "active": True,
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
        "id": "wind_particles",
        "name": "Wind (particles)",
        "file": "processed/weather.geojson",
        "type": "particles",
        "temporal": True,
        "active": False,
        # Surface wind at 10 m: the front end reads u / v (m/s) per grid point and hour
        "color": "#bae6fd",
        "legend": [{"color": "#bae6fd", "text": "Surface wind (10 m), faster = brighter"}],
    },
    {
        "id": "water",
        "name": "Water",
        "file": "processed/water.geojson",
        "type": "fill",
        "temporal": False,
        "active": True,
        "popup": ["name", "kind"],
        "legend": [{"color": "#3d8bd4", "text": "Lakes, reservoirs"}],
    },
    {
        "id": "rivers",
        "name": "Rivers",
        "file": "processed/rivers.geojson",
        "type": "line",
        "temporal": False,
        "active": True,  # water is active: rivers were drawn (wrongly) inside it
        "popup": ["name"],
        "legend": [{"color": "#3d8bd4", "text": "Rivers"}],
    },
    {
        "id": "roads",
        "name": "Roads",
        "file": "processed/roads.geojson",
        "type": "line",
        "temporal": False,
        "active": True,
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
        "active": True,
        "popup": ["name"],
        "legend": [{"color": "#2b8cbe", "text": "Fire station"}],
    },
    {
        "id": "water_points",
        "name": "Water points for firefighting",
        "file": "processed/water_points.geojson",
        "type": "circle",
        "temporal": False,
        "active": True,
        "popup": ["name", "kind"],
        # Colors match osm.WATER_POINT_COLORS
        "legend": [
            {"color": "#0077b6", "text": "Firefighting tank / suction point"},
            {"color": "#00b4d8", "text": "Hydrant"},
            {"color": "#48cae4", "text": "Water tank"},
            {"color": "#90e0ef", "text": "Well"},
            {"color": "#ade8f4", "text": "Spring"},
            {"color": "#caf0f8", "text": "Water point"},
        ],
    },
    {
        "id": "groundwater",
        "name": "Groundwater (ash leachate risk)",
        "file": "processed/groundwater.geojson",
        "type": "fill",
        "temporal": False,
        "active": True,
        "popup": ["name", "vulnerability", "chemical_status", "at_risk_chemical", "geology"],
        # Colors match groundwater.STYLE
        "legend": [
            {"color": "#8e44ad", "text": "High vulnerability (karst / poor or at-risk chemical status)"},
            {"color": "#5b8def", "text": "Medium (porous aquifer)"},
            {"color": "#9fb8c9", "text": "Low"},
        ],
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
