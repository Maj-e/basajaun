"""Shrink the episode's GeoJSON files so the page downloads and parses less.

Same features, same properties, same contract: only the geometry gets lighter.
- Coordinates rounded to 5 decimals (~1 m), far below the 375 m / 1 km satellite pixels.
- Polygons and lines simplified with a tolerance per layer (outlines drawn from
  375 m pixels, or estimates, do not need vertices every few metres).
- Written without indentation or spaces.

Runs after the scripts that write geometry, before make_manifest. Idempotent.
`--all` compacts every episode folder and the static files (no download needed).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from shapely.geometry import mapping, shape

from config import PROCESSED, WEB_DATA

DECIMALS = 5
# Simplification tolerance in degrees (1e-4 ≈ 10 m). Layers not listed are only rounded.
TOLERANCE = {
    "fires.geojson": 2e-4,        # outline of 375 m / 1 km pixels
    "spread.geojson": 5e-4,       # 6 h spread estimate
    "fire_risk.geojson": 2e-4,
    "evacuation.geojson": 2e-4,
    "regions.geojson": 1e-3,      # administrative borders, seen at regional zoom
    "groundwater.geojson": 5e-4,
    "rivers.geojson": 1e-4,
    "roads.geojson": 5e-5,
    "water.geojson": 1e-4,
    "land.geojson": 5e-4,         # world land outline under the base maps
}


def _round(coords):
    if isinstance(coords, (int, float)):
        return round(coords, DECIMALS)
    return [_round(c) for c in coords]


def compact_geometry(geometry: dict | None, tolerance: float | None) -> dict | None:
    if not geometry:
        return geometry
    if tolerance and geometry["type"] not in ("Point", "MultiPoint"):
        simplified = shape(geometry).simplify(tolerance, preserve_topology=True)
        if not simplified.is_empty:
            geometry = mapping(simplified)
    # mapping() returns tuples; rebuild plain lists with rounded numbers
    return {"type": geometry["type"], "coordinates": _round(geometry["coordinates"])}


def compact_file(path: Path) -> tuple[int, int]:
    before = path.stat().st_size
    doc = json.loads(path.read_text(encoding="utf-8"))
    if doc.get("type") != "FeatureCollection":
        return before, before
    tolerance = TOLERANCE.get(path.name)
    for feature in doc.get("features", []):
        feature["geometry"] = compact_geometry(feature.get("geometry"), tolerance)
    path.write_text(json.dumps(doc, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    return before, path.stat().st_size


def compact_folder(folder: Path) -> None:
    for path in sorted(folder.glob("*.geojson")):
        before, after = compact_file(path)
        if after < before:
            print(f"  {path.relative_to(WEB_DATA)}: {before // 1024} → {after // 1024} KB")


def main() -> None:
    if "--all" in sys.argv:
        folders = [WEB_DATA / "processed", WEB_DATA / "static", *sorted((WEB_DATA / "episodes").glob("*/"))]
    else:
        folders = [PROCESSED]
    for folder in folders:
        if folder.is_dir():
            compact_folder(folder)


if __name__ == "__main__":
    main()
