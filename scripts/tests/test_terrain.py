"""Tests for slope and land cover per fire (W5-B3). Synthetic rasters, no download."""
import json

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

import terrain

RES = 0.01
WEST, NORTH = -71.0, -35.0
HEIGHT = WIDTH = 20


def write_tif(path, array, nodata):
    array = np.asarray(array)
    with rasterio.open(path, "w", driver="GTiff", height=array.shape[0], width=array.shape[1], count=1,
                       dtype=array.dtype, crs="EPSG:4326", transform=from_origin(WEST, NORTH, RES, RES),
                       nodata=nodata) as dst:
        dst.write(array, 1)


def fire_collection():
    # Inset from the raster edge so the sampled cells use a central difference.
    west, east = WEST + 4 * RES, WEST + 16 * RES
    north, south = NORTH - 4 * RES, NORTH - 16 * RES
    ring = [[west, south], [east, south], [east, north], [west, north], [west, south]]
    return {"type": "FeatureCollection", "updated_at": "2026-02-14T08:00:00Z", "features": [{
        "type": "Feature",
        "geometry": {"type": "Polygon", "coordinates": [ring]},
        "properties": {"fire_id": 1, "dist_road_km": 1.5},
    }]}


@pytest.fixture
def raw(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    lat = NORTH - (HEIGHT / 2.0) * RES
    dx = RES * terrain.M_PER_DEG * np.cos(np.radians(lat))
    cols = np.arange(WIDTH, dtype="float32")
    elev = np.broadcast_to(cols * dx * np.tan(np.radians(10.0)), (HEIGHT, WIDTH)).copy()
    write_tif(raw / "copernicus_test.tif", elev, nodata=-9999.0)
    write_tif(raw / "worldcover_test.tif", np.full((HEIGHT, WIDTH), 10, dtype="uint8"), nodata=0)
    return raw


def test_skips_without_rasters(tmp_path, capsys):
    processed = tmp_path / "processed"
    processed.mkdir()
    fires = processed / "fires.geojson"
    fires.write_text(json.dumps(fire_collection()))
    assert terrain.run(tmp_path / "empty", processed) is False
    assert "[SKIP]" in capsys.readouterr().out
    assert "slope_deg" not in json.loads(fires.read_text())["features"][0]["properties"]


def test_slope_and_landcover_and_keeps_other_properties(raw, tmp_path):
    processed = tmp_path / "processed"
    processed.mkdir()
    fires = processed / "fires.geojson"
    fires.write_text(json.dumps(fire_collection()))
    assert terrain.run(raw, processed) is True
    props = json.loads(fires.read_text())["features"][0]["properties"]
    assert props["slope_deg"] == pytest.approx(10.0, abs=0.2)
    assert props["landcover"] == "Tree cover"
    assert props["fire_id"] == 1
    assert props["dist_road_km"] == 1.5
