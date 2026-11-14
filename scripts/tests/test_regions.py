"""Tests for region assignment (W3-B6). Synthetic polygons, no download."""
import json

import geopandas as gpd
import pandas as pd
from shapely.geometry import box

import regions
import validate

UPDATED = "2026-02-14T08:00:00Z"


def hotspot_at(lon, lat):
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": {"id": f"{lon},{lat}"},
    }


def two_regions():
    # West half and east half of the square (-72, -36) .. (-70, -34)
    west = box(-72, -36, -71, -34)
    east = box(-71, -36, -70, -34)
    return gpd.GeoDataFrame(
        {"country": ["Chile", "Argentina"], "region": ["Maule", "Mendoza"]},
        geometry=[west, east],
        crs="EPSG:4326",
    )


def test_repair_text_fixes_double_encoded_utf8():
    assert regions.repair_text("RegiÃ³n Metropolitana de Santiago") == "Región Metropolitana de Santiago"
    assert regions.repair_text("Chile") == "Chile"
    assert regions.repair_text(None) is None


def test_iso_of_skips_unreliable_codes():
    assert regions.iso_of(pd.Series({"ISO_A3": "-99", "ADM0_A3": "CHL"})) == "CHL"
    assert regions.iso_of(pd.Series({"ISO_A3": "ARG"})) == "ARG"
    assert regions.iso_of(pd.Series({"ISO_A3": "-99", "ADM0_A3": None})) is None


def test_annotate_assigns_the_polygon_that_contains_the_point(tmp_path):
    path = tmp_path / "hotspots.geojson"
    path.write_text(json.dumps({
        "type": "FeatureCollection",
        "updated_at": UPDATED,
        "features": [hotspot_at(-71.5, -35.0), hotspot_at(-70.5, -35.0), hotspot_at(0, 0)],
    }), encoding="utf-8")

    regions.annotate_hotspots(two_regions(), path)

    props = [feature["properties"] for feature in json.loads(path.read_text(encoding="utf-8"))["features"]]
    assert [(p["country"], p["region"]) for p in props] == [
        ("Chile", "Maule"),
        ("Argentina", "Mendoza"),
        (None, None),
    ]


def test_a_point_on_the_shared_edge_is_kept_once(tmp_path):
    path = tmp_path / "hotspots.geojson"
    path.write_text(json.dumps({
        "type": "FeatureCollection",
        "features": [hotspot_at(-71.0, -35.0)],
    }), encoding="utf-8")
    regions.annotate_hotspots(two_regions(), path)
    features = json.loads(path.read_text(encoding="utf-8"))["features"]
    assert len(features) == 1
    assert features[0]["properties"]["region"] in {"Maule", "Mendoza"}


def test_write_regions_carries_style(tmp_path):
    destination = tmp_path / "regions.geojson"
    regions.write_regions(two_regions(), destination)
    written = json.loads(destination.read_text(encoding="utf-8"))
    assert written["features"][0]["properties"]["color"] == regions.PALETTE[0]
    assert written["features"][0]["properties"]["opacity"] == 0.35
    assert written["features"][1]["geometry"]["type"] == "Polygon"


def test_main_skips_without_hotspots(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(regions, "PROCESSED", tmp_path)
    regions.main()
    assert "[SKIP]" in capsys.readouterr().out
    assert not (tmp_path / "regions.geojson").exists()


def test_schema_accepts_country_and_region(tmp_path):
    feature = {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [-70.6483, -33.4569]},
        "properties": {
            "id": "VIIRS_N20_20260214_0742_-33.4569_-70.6483",
            "sensor": "VIIRS", "satellite": "NOAA-20",
            "timestamp_utc": UPDATED, "date": "2026-02-14", "t": 493927.7,
            "confidence": "high", "frp": 18.4, "brightness_k": 342.1, "day_night": "N",
            "resolution_m": 375, "detected_by": ["VIIRS"], "fire_id": None,
            "color": "#d7301f", "radius": 6.2, "border": "#222222",
            "country": "Chile", "region": None,
        },
    }
    path = tmp_path / "hotspots.geojson"
    path.write_text(json.dumps({
        "type": "FeatureCollection", "updated_at": UPDATED, "features": [feature],
    }), encoding="utf-8")
    registry = validate.load_registry()
    assert validate.validate_file(path, registry, tmp_path) == []

    feature["properties"]["country"] = 12
    path.write_text(json.dumps({
        "type": "FeatureCollection", "updated_at": UPDATED, "features": [feature],
    }), encoding="utf-8")
    assert validate.validate_file(path, registry, tmp_path) != []
