"""Population layer from WorldPop (W3-B3).

Input: WorldPop "Population counts, 1 km, UN adjusted" GeoTIFFs in data/raw/, one per country,
named worldpop_<anything>.tif. The demo area crosses the Chile–Argentina border, so download both:
    https://data.worldpop.org/GIS/Population/Global_2000_2020_1km_UNadj/2020/CHL/chl_ppp_2020_1km_Aggregated_UNadj.tif
    https://data.worldpop.org/GIS/Population/Global_2000_2020_1km_UNadj/2020/ARG/arg_ppp_2020_1km_Aggregated_UNadj.tif
and save them as data/raw/worldpop_chl.tif and data/raw/worldpop_arg.tif.

Outputs (web/data/processed/):
    population.tif  people per cell, clipped to the BBOX  -> exposure.py (W3-B1)
    population.png  density coloured with the manifest legend, transparent where nobody lives
                    -> "population" image layer; make_manifest.py reads the corners from population.tif
"""
from __future__ import annotations

import math
import warnings
from pathlib import Path

import numpy as np
import rasterio
from rasterio.errors import NotGeoreferencedWarning
from rasterio.merge import merge

from config import BBOX, PROCESSED, RAW

NODATA = -99999.0
# Density colour ramp (people/km²), log scale from 10 to 1000 — same ends as the manifest legend
RAMP = ["#fee5d9", "#fcae91", "#fb6a4a", "#de2d26", "#a50f15"]
DENSITY_MIN, DENSITY_MAX = 10.0, 1000.0
SHOW_FROM = 1.0     # people/km² below this are left transparent
ALPHA = 210
KM_PER_DEG = 111.32


def find_sources(raw_dir: Path = RAW) -> list[Path]:
    return sorted(raw_dir.glob("worldpop_*.tif"))


def clip_to_bbox(sources: list[Path], bbox=BBOX) -> tuple[np.ndarray, dict]:
    """Merge the country rasters and clip them to the BBOX. Returns (counts 2-D array, rasterio profile)."""
    datasets = [rasterio.open(p) for p in sources]
    try:
        data, transform = merge(datasets, bounds=bbox, nodata=NODATA)
        profile = datasets[0].profile.copy()
    finally:
        for ds in datasets:
            ds.close()
    profile.update(driver="GTiff", height=data.shape[1], width=data.shape[2], count=1,
                   dtype="float32", transform=transform, nodata=NODATA, compress="lzw")
    return data[0].astype("float32"), profile


def density_per_km2(counts: np.ndarray, transform) -> np.ndarray:
    """People per km² from people per cell, using each row's cell area (cells shrink towards the poles)."""
    res_x, res_y = transform.a, -transform.e
    rows = np.arange(counts.shape[0])
    lat = transform.f - (rows + 0.5) * res_y
    cell_km2 = (res_x * KM_PER_DEG) * (res_y * KM_PER_DEG) * np.cos(np.radians(lat))
    return counts / cell_km2[:, None]


def _hex_to_rgb(color: str) -> np.ndarray:
    return np.array([int(color[i:i + 2], 16) for i in (1, 3, 5)], dtype=float)


def colorize(density: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """RGBA uint8 image (4, rows, cols): log-scaled ramp, transparent where invalid or below SHOW_FROM."""
    stops = np.stack([_hex_to_rgb(c) for c in RAMP])                         # (n, 3)
    with np.errstate(divide="ignore", invalid="ignore"):
        pos = (np.log10(np.clip(density, DENSITY_MIN, DENSITY_MAX)) - math.log10(DENSITY_MIN)) / (
            math.log10(DENSITY_MAX) - math.log10(DENSITY_MIN))
    pos = np.nan_to_num(pos) * (len(RAMP) - 1)
    low = np.clip(np.floor(pos).astype(int), 0, len(RAMP) - 2)
    frac = (pos - low)[..., None]
    rgb = stops[low] * (1 - frac) + stops[low + 1] * frac                     # (rows, cols, 3)
    shown = valid & (density >= SHOW_FROM)
    alpha = np.where(shown, ALPHA, 0)
    return np.dstack([rgb, alpha]).round().astype("uint8").transpose(2, 0, 1)


def write_png(rgba: np.ndarray, path: Path) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", NotGeoreferencedWarning)  # plain picture: corners live in the manifest
        with rasterio.open(path, "w", driver="PNG", width=rgba.shape[2], height=rgba.shape[1],
                           count=4, dtype="uint8") as dst:
            dst.write(rgba)


def run(raw_dir: Path = RAW, out_dir: Path = PROCESSED, bbox=BBOX) -> bool:
    sources = find_sources(raw_dir)
    if not sources:
        print(f"[SKIP] no WorldPop file in {raw_dir} (worldpop_*.tif): see the download links in population.py.")
        return False

    counts, profile = clip_to_bbox(sources, bbox)
    valid = counts != NODATA
    out_dir.mkdir(parents=True, exist_ok=True)
    tif_path, png_path = out_dir / "population.tif", out_dir / "population.png"
    with rasterio.open(tif_path, "w", **profile) as dst:
        dst.write(counts, 1)

    density = density_per_km2(np.where(valid, counts, 0.0), profile["transform"])
    write_png(colorize(density, valid), png_path)

    total = float(counts[valid].sum())
    print(f"[SAVED] {tif_path} ({counts.shape[1]}×{counts.shape[0]} cells, {total:,.0f} people)")
    print(f"[SAVED] {png_path} ({png_path.stat().st_size / 1024:.0f} KB) from {', '.join(p.name for p in sources)}")
    return True


def main() -> None:
    run()


if __name__ == "__main__":
    main()
