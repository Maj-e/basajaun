"""Generate web/data/manifest.json listing only the layers whose data file exists.

Every layer the project knows is declared once in LAYERS below. A layer appears
in the manifest only when its file is present under web/data/, so the front end
never asks for a missing file.

Adding a layer = its script writes the file + one entry in LAYERS
(`enabled: False` until it has been checked on the published URL).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from config import BBOX, PROCESSED

DATA_DIR = PROCESSED.parent  # web/data/ — manifest `file` paths are relative to it
MANIFEST = DATA_DIR / "manifest.json"

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
        "enabled": True,
        "popup": ["sensor", "satellite", "datetime_utc", "confidence", "frp"],
        "legend": [
            {"color": "#d7301f", "label": "High confidence"},
            {"color": "#fc8d59", "label": "Medium confidence"},
            {"color": "#fdcc8a", "label": "Low confidence"},
        ],
    },
    {
        "id": "fires",
        "name": "Fires",
        "file": "processed/fires.geojson",
        "type": "fill",
        "temporal": False,
        "enabled": False,
        "popup": ["fire_id", "start", "end", "n_hotspots", "frp_max", "area_km2"],
    },
    {
        "id": "population",
        "name": "Population density",
        "file": "processed/population.png",
        "type": "image",
        "corners": BBOX_CORNERS,
        "temporal": False,
        "enabled": False,
        "legend": [
            {"color": "#fee5d9", "label": "< 10 people/km²"},
            {"color": "#a50f15", "label": "> 1000 people/km²"},
        ],
    },
    {
        "id": "wind",
        "name": "Wind",
        "file": "processed/weather.geojson",
        "type": "arrows",
        "temporal": True,
        "enabled": False,
        "popup": ["datetime_utc", "speed", "direction"],
        "legend": [
            {"color": "#91cf60", "label": "< 15 km/h"},
            {"color": "#fee08b", "label": "15–30 km/h"},
            {"color": "#fc8d59", "label": "30–45 km/h"},
            {"color": "#d7301f", "label": "≥ 45 km/h"},
        ],
    },
    {
        "id": "weather",
        "name": "Weather",
        "file": "processed/weather.geojson",
        "type": "circle",
        "temporal": True,
        "enabled": False,
        "popup": ["datetime_utc", "temperature", "humidity", "rain", "speed"],
    },
    {
        "id": "water",
        "name": "Water",
        "file": "processed/water.geojson",
        "type": "fill",
        "temporal": False,
        "enabled": False,
    },
    {
        "id": "roads",
        "name": "Roads",
        "file": "processed/roads.geojson",
        "type": "line",
        "temporal": False,
        "enabled": False,
    },
    {
        "id": "fire_stations",
        "name": "Fire stations",
        "file": "processed/fire_stations.geojson",
        "type": "circle",
        "temporal": False,
        "enabled": False,
    },
]


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def file_updated(path: Path) -> str:
    """`updated` of a data file: its own `updated` field if it has one, else its modification time."""
    if path.suffix in {".json", ".geojson"}:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("updated"), str):
                return data["updated"]
        except json.JSONDecodeError:
            pass
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return mtime.strftime("%Y-%m-%dT%H:%M:%SZ")


def build_manifest(data_dir: Path = DATA_DIR, layers: list[dict] = LAYERS) -> dict:
    present = []
    for layer in layers:
        path = data_dir / layer["file"]
        if path.is_file():
            present.append({**layer, "updated": file_updated(path)})
    return {"updated": utc_now(), "layers": present}


def main() -> None:
    manifest = build_manifest()
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    listed = {layer["id"] for layer in manifest["layers"]}
    for layer in LAYERS:
        if layer["id"] in listed:
            state = "enabled" if layer["enabled"] else "disabled"
            print(f"  + {layer['id']:<14} {layer['file']} ({state})")
        else:
            print(f"  - {layer['id']:<14} {layer['file']} not found, skipped")
    print(f"[SAVED] {MANIFEST} ({len(listed)}/{len(LAYERS)} layers)")


if __name__ == "__main__":
    main()
