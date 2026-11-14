"""Mean slope and dominant vegetation per fire (W5-B3).

Inputs, in data/raw/ (not versioned):
    copernicus_*.tif   Copernicus DEM GLO-30, one 1° tile per file
    worldcover_*.tif   ESA WorldCover 2021, one 3° tile per file

Writes onto each feature of web/data/processed/fires.geojson, leaving every
other property in place:
    slope_deg   mean slope in degrees, from the DEM
    landcover   majority WorldCover class name
Missing rasters are skipped, so `make data` still finishes.
spread.py reads slope_deg; without that key the ellipse keeps using 0.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from rasterio.features import geometry_mask
from rasterio.merge import merge
from shapely.geometry import box, mapping, shape

from config import PROCESSED, RAW

COVER = {
    10: "Tree cover",
    20: "Shrubland",
    30: "Grassland",
    40: "Cropland",
    50: "Built-up",
    60: "Bare / sparse vegetation",
    70: "Snow and ice",
    80: "Permanent water bodies",
    90: "Herbaceous wetland",
    95: "Mangroves",
    100: "Moss and lichen",
}
M_PER_DEG = 111_320.0
# Extra degrees around each fire so the slope gradient has a cell outside the polygon.
PAD_DEG = 0.01


def find(pattern: str, raw_dir: Path) -> list[Path]:
    return sorted(raw_dir.glob(pattern))


def read_window(paths: list[Path], bounds: tuple[float, float, float, float]) -> tuple[np.ndarray, dict] | None:
    """Merge only the tiles that touch this rectangle and return that window."""
    chosen = []
    for path in paths:
        with rasterio.open(path) as src:
            if box(*src.bounds).intersects(box(*bounds)):
                chosen.append(path)
    if not chosen:
        return None
    datasets = [rasterio.open(path) for path in chosen]
    try:
        data, transform = merge(datasets, bounds=bounds)
        profile = datasets[0].profile.copy()
    finally:
        for src in datasets:
            src.close()
    if data.size == 0 or data.shape[1] == 0 or data.shape[2] == 0:
        return None
    profile.update(height=data.shape[1], width=data.shape[2], transform=transform)
    return data[0], profile


def slope_degrees(elev: np.ndarray, transform, nodata) -> np.ndarray:
    """Slope in degrees. One pixel size is enough: a fire spans a fraction of a degree."""
    valid = np.ones(elev.shape, dtype=bool) if nodata is None else (elev != nodata)
    res_x, res_y = abs(transform.a), abs(transform.e)
    lat = transform.f - (elev.shape[0] / 2.0) * res_y
    dx = res_x * M_PER_DEG * np.cos(np.radians(lat))
    dy = res_y * M_PER_DEG
    dz_dy, dz_dx = np.gradient(np.nan_to_num(np.where(valid, elev, np.nan), nan=0.0), dy, dx)
    slope = np.degrees(np.arctan(np.hypot(dz_dx, dz_dy)))
    slope[~valid] = np.nan
    return slope


def _inside(values: np.ndarray, transform, polygon) -> np.ndarray:
    """True where the cell center falls inside the fire polygon."""
    return geometry_mask([mapping(polygon)], out_shape=values.shape, transform=transform, invert=True)


def mean_inside(values: np.ndarray, transform, polygon) -> float | None:
    sample = values[_inside(values, transform, polygon) & np.isfinite(values)]
    if sample.size == 0:
        return None
    return float(np.mean(sample))


def majority(codes: np.ndarray, transform, polygon) -> str | None:
    sample = codes[_inside(codes, transform, polygon)]
    sample = sample[sample != 0]
    if sample.size == 0:
        return None
    uniq, counts = np.unique(sample, return_counts=True)
    return COVER.get(int(uniq[counts.argmax()]))


def annotate(fires_path: Path, dem_paths: list[Path], cover_paths: list[Path]) -> tuple[int, int]:
    fc = json.loads(fires_path.read_text(encoding="utf-8"))
    slopes = covers = 0
    for feature in fc.get("features", []):
        polygon = shape(feature["geometry"])
        minx, miny, maxx, maxy = polygon.bounds
        window = (minx - PAD_DEG, miny - PAD_DEG, maxx + PAD_DEG, maxy + PAD_DEG)
        props = feature["properties"]
        if dem_paths:
            got = read_window(dem_paths, window)
            if got is not None:
                elev, profile = got
                slope = slope_degrees(elev, profile["transform"], profile.get("nodata"))
                value = mean_inside(slope, profile["transform"], polygon)
                if value is not None:
                    props["slope_deg"] = round(value, 1)
                    slopes += 1
        if cover_paths:
            got = read_window(cover_paths, window)
            if got is not None:
                codes, profile = got
                name = majority(codes, profile["transform"], polygon)
                if name is not None:
                    props["landcover"] = name
                    covers += 1
    fc["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    fires_path.write_text(json.dumps(fc, separators=(",", ":")), encoding="utf-8")
    return slopes, covers


def run(raw_dir: Path = RAW, processed_dir: Path = PROCESSED) -> bool:
    fires_path = processed_dir / "fires.geojson"
    dem_paths, cover_paths = find("copernicus_*.tif", raw_dir), find("worldcover_*.tif", raw_dir)
    if not fires_path.is_file():
        print(f"[SKIP] {fires_path} not found yet (waiting for W2-B2).")
        return False
    if not dem_paths and not cover_paths:
        print(f"[SKIP] no Copernicus or WorldCover GeoTIFF in {raw_dir}.")
        return False
    slopes, covers = annotate(fires_path, dem_paths, cover_paths)
    print(f"[UPDATED] {fires_path}: slope on {slopes} fires, landcover on {covers} fires "
          f"(dem {len(dem_paths)}, worldcover {len(cover_paths)})")
    return True


if __name__ == "__main__":
    run()
