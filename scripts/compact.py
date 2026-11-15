"""Make the episode's GeoJSON files smaller for the browser: 5-decimal coordinates, no indentation.

Why: some layers were written with 15-digit coordinates and pretty-printed (spread.geojson of the Galicia +
Castilla y León episode: 8 MB). 5 decimals are ~1 m, far below any satellite pixel, and the front end
does not care about whitespace.

Runs near the end of the pipeline (after every script that edits a GeoJSON in place), before make_manifest.
It never changes properties, feature order or `updated_at`; a file is only rewritten when it gets smaller.

    uv run scripts/compact.py            # the selected episode (EPISODE=<id> for another)
"""
from __future__ import annotations

import json
from pathlib import Path

from config import PROCESSED

DECIMALS = 5


def _round_position(position: list[float], decimals: int) -> list[float]:
    return [round(c, decimals) for c in position]


def _round_coordinates(coords, decimals: int, min_points: int = 0):
    """Round a Point / LineString / Polygon / Multi* coordinates array, dropping repeated consecutive points.

    `min_points` is the fewest points a line or ring may keep (2 for lines, 4 for rings); a shorter result
    means the shape collapsed, so the original is kept.
    """
    if not coords:
        return coords
    if isinstance(coords[0], (int, float)):
        return _round_position(coords, decimals)
    if isinstance(coords[0][0], (int, float)):  # a line or a ring: list of positions
        rounded = [_round_position(p, decimals) for p in coords]
        deduped = [p for i, p in enumerate(rounded) if i == 0 or p != rounded[i - 1]]
        return deduped if len(deduped) >= min_points else rounded
    return [_round_coordinates(part, decimals, min_points) for part in coords]


def _min_points(geometry_type: str) -> int:
    return 4 if geometry_type in {"Polygon", "MultiPolygon"} else 2


def compact_geojson(doc: dict, decimals: int = DECIMALS) -> dict:
    """The same FeatureCollection with rounded coordinates (properties untouched)."""
    for feature in doc.get("features", []):
        geometry = feature.get("geometry")
        if geometry and "coordinates" in geometry:
            geometry["coordinates"] = _round_coordinates(
                geometry["coordinates"], decimals, _min_points(geometry["type"]))
    return doc


def compact_file(path: Path, decimals: int = DECIMALS) -> tuple[int, int]:
    """Rewrite `path` compactly if that makes it smaller. Returns (size before, size after) in bytes."""
    before = path.stat().st_size
    doc = json.loads(path.read_text(encoding="utf-8"))
    text = json.dumps(compact_geojson(doc, decimals), separators=(",", ":"), ensure_ascii=False)
    after = len(text.encode("utf-8"))
    if after < before:
        path.write_text(text, encoding="utf-8")
        return before, after
    return before, before


def main(folder: Path = PROCESSED) -> None:
    files = sorted(folder.glob("*.geojson"))
    total_before = total_after = 0
    for path in files:
        before, after = compact_file(path)
        total_before += before
        total_after += after
        if after < before:
            print(f"  {path.name:<24} {before / 1e6:6.2f} MB -> {after / 1e6:6.2f} MB")
    print(f"[COMPACTED] {len(files)} GeoJSON files in {folder}: {total_before / 1e6:.1f} MB -> {total_after / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
