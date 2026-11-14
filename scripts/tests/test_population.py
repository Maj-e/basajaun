"""Tests for the WorldPop population layer (W3-B3). Synthetic rasters, no download."""
import json

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

import make_manifest
import population
import validate

RES = 0.25  # degrees per cell (coarse on purpose)
BBOX = (-72.0, -36.0, -70.0, -34.0)


def write_country(path, west, north, counts):
    counts = np.asarray(counts, dtype="float32")
    with rasterio.open(path, "w", driver="GTiff", height=counts.shape[0], width=counts.shape[1], count=1,
                       dtype="float32", crs="EPSG:4326", transform=from_origin(west, north, RES, RES),
                       nodata=population.NODATA) as dst:
        dst.write(counts, 1)


@pytest.fixture
def raw(tmp_path):
    """Two 'countries' side by side: west half and east half of a region larger than the BBOX."""
    raw = tmp_path / "raw"
    raw.mkdir()
    west = np.zeros((12, 6))           # -73.0 .. -71.5, -33.0 .. -36.0
    west[5, 4] = 5_000_000             # a city inside the BBOX (~7,900 people/km² in these big cells)
    east = np.full((12, 6), population.NODATA)
    east[4:8, 0:2] = 0                 # empty land inside the BBOX
    east[6, 1] = 2_000
    write_country(raw / "worldpop_west.tif", -73.0, -33.0, west)
    write_country(raw / "worldpop_east.tif", -71.5, -33.0, east)
    return raw


def test_skips_without_worldpop(tmp_path, capsys):
    assert population.run(tmp_path, tmp_path / "out", BBOX) is False
    assert "[SKIP]" in capsys.readouterr().out
    assert not (tmp_path / "out").exists()


def test_clips_merges_and_keeps_counts(raw, tmp_path):
    out = tmp_path / "out"
    assert population.run(raw, out, BBOX)
    with rasterio.open(out / "population.tif") as src:
        assert src.bounds == pytest.approx(BBOX)
        counts = src.read(1)
        assert src.nodata == population.NODATA
    assert counts.shape == (8, 8)
    assert counts[counts != population.NODATA].sum() == pytest.approx(5_002_000)  # both countries kept


def test_png_is_transparent_where_nobody_lives(raw, tmp_path):
    out = tmp_path / "out"
    population.run(raw, out, BBOX)
    with rasterio.open(out / "population.png") as png:
        rgba = png.read()
    assert rgba.shape == (4, 8, 8)
    alpha = rgba[3]
    assert (alpha > 0).sum() == 2                  # only the city and the small town show
    city = rgba[:3, 1, 0]                          # cell -34.25..-34.5 °S, -72.0..-71.75 °W
    assert alpha[1, 0] == population.ALPHA
    assert tuple(city) == tuple(int(population.RAMP[-1][i:i + 2], 16) for i in (1, 3, 5))


def test_colorize_follows_the_legend_ends():
    density = np.array([[5.0, 10.0, 1000.0, 50_000.0]])
    rgba = population.colorize(density, np.ones_like(density, dtype=bool))
    first, last = population._hex_to_rgb(population.RAMP[0]), population._hex_to_rgb(population.RAMP[-1])
    assert tuple(rgba[:3, 0, 1]) == tuple(first.astype(int))
    assert tuple(rgba[:3, 0, 2]) == tuple(last.astype(int))
    assert tuple(rgba[:3, 0, 3]) == tuple(last.astype(int))  # above the top: clipped


def test_density_accounts_for_latitude():
    transform = from_origin(-71.0, 0.5, 1.0, 1.0)          # one 1° row at the equator
    at_equator = population.density_per_km2(np.array([[1000.0]]), transform)[0, 0]
    transform60 = from_origin(-71.0, -59.5, 1.0, 1.0)      # one 1° row around 60°S
    at_60 = population.density_per_km2(np.array([[1000.0]]), transform60)[0, 0]
    assert at_60 == pytest.approx(at_equator * 2, rel=0.02)  # cells are half as wide at 60°


def test_manifest_takes_corners_from_population_tif(raw, tmp_path):
    data_dir = tmp_path / "data"
    population.run(raw, data_dir / "processed", BBOX)
    manifest = make_manifest.build_manifest(data_dir, subdir="processed")
    [layer] = [layer for layer in manifest["layers"] if layer["id"] == "population"]
    assert layer["corners"] == [[-72.0, -34.0], [-70.0, -34.0], [-70.0, -36.0], [-72.0, -36.0]]

    (data_dir / "manifest.json").write_text(json.dumps(manifest))
    assert validate.validate_file(data_dir / "manifest.json", validate.load_registry(), data_dir) == []
