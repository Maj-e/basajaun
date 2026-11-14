"""Tests for the contract validator (W1-B4)."""
import copy
import json

import pytest

import validate

UPDATED = "2026-02-14T08:00:00Z"

HOTSPOT = {
    "type": "Feature",
    "geometry": {"type": "Point", "coordinates": [-70.6483, -33.4569]},
    "properties": {
        "id": "VIIRS_N20_20260214_0742_-33.4569_-70.6483",
        "sensor": "VIIRS",
        "satellite": "NOAA-20",
        "datetime_utc": "2026-02-14T07:42:00Z",
        "date": "2026-02-14",
        "t": 493927.7,
        "confidence": "high",
        "frp": 18.4,
        "brightness_k": 342.1,
        "daynight": "N",
        "resolution_m": 375,
        "detected_by": ["VIIRS"],
        "fire_id": None,
        "color": "#d7301f",
        "radius": 6.2,
        "stroke": "#222222",
    },
}


@pytest.fixture(scope="module")
def registry():
    return validate.load_registry()


@pytest.fixture
def data_dir(tmp_path):
    (tmp_path / "processed").mkdir()
    return tmp_path


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content), encoding="utf-8")
    return path


def hotspots(*features):
    return {"type": "FeatureCollection", "updated": UPDATED, "features": list(features)}


def manifest(*layers):
    return {"updated": UPDATED, "layers": list(layers)}


def hotspot_layer(file="processed/hotspots.geojson", **extra):
    return {"id": "hotspots", "name": "Fire hotspots", "file": file, "type": "circle",
            "temporal": True, "enabled": True, **extra}


# --- hotspots -----------------------------------------------------------------

def test_valid_hotspots_pass(registry, data_dir):
    path = write(data_dir / "processed/hotspots.geojson", hotspots(HOTSPOT))
    assert validate.validate_file(path, registry, data_dir) == []


def test_daily_hotspot_files_use_hotspot_schema():
    assert validate.schema_for(validate.Path("hotspots_2026-02-14.geojson")) == "hotspots.schema.json"


@pytest.mark.parametrize("field, value", [
    ("confidence", "alta"),        # Spanish value instead of the contract enum
    ("sensor", "GOES"),
    ("color", "red"),              # not a hex color
    ("datetime_utc", "2026-02-14 07:42"),
    ("t", "493927.7"),             # string instead of number
])
def test_bad_hotspot_field_fails(registry, data_dir, field, value):
    bad = copy.deepcopy(HOTSPOT)
    bad["properties"][field] = value
    path = write(data_dir / "processed/hotspots.geojson", hotspots(bad))
    errors = validate.validate_file(path, registry, data_dir)
    assert any(field in e for e in errors), errors


def test_missing_hotspot_field_fails(registry, data_dir):
    bad = copy.deepcopy(HOTSPOT)
    del bad["properties"]["frp"]
    path = write(data_dir / "processed/hotspots.geojson", hotspots(bad))
    assert any("'frp' is a required property" in e for e in validate.validate_file(path, registry, data_dir))


def test_missing_updated_fails(registry, data_dir):
    fc = hotspots(HOTSPOT)
    del fc["updated"]
    path = write(data_dir / "processed/hotspots.geojson", fc)
    assert validate.validate_file(path, registry, data_dir)


# --- daily summary / alerts ---------------------------------------------------

def test_daily_summary(registry, data_dir):
    good = {"updated": UPDATED,
            "2026-02-14": {"hotspots": 3, "frp_total": 40.5, "modis": 1, "viirs": 2, "no_data": False}}
    path = write(data_dir / "processed/daily_summary.json", good)
    assert validate.validate_file(path, registry, data_dir) == []

    good["2026-02-15"] = {"focos": 0, "frp_total": 0, "modis": 0, "viirs": 0, "no_data": True}
    write(path, good)
    assert validate.validate_file(path, registry, data_dir)


def test_alerts(registry, data_dir):
    alert = {"fire_id": 12, "risk": "critical", "since": "2026-02-14T07:42:00Z", "pop_1km": 800,
             "pop_5km": 23400, "pop_10km": 51000, "wind_toward_population": False,
             "center": [-70.65, -33.46], "color": "#a50f15"}
    path = write(data_dir / "processed/alerts.json", {"updated": UPDATED, "alerts": [alert]})
    assert validate.validate_file(path, registry, data_dir) == []

    write(path, {"updated": UPDATED, "alerts": [{**alert, "risk": "critico"}]})
    assert validate.validate_file(path, registry, data_dir)

    write(path, [alert])  # old bare-list format: no room for `updated`
    assert validate.validate_file(path, registry, data_dir)


# --- manifest -----------------------------------------------------------------

def test_valid_manifest_pass(registry, data_dir):
    write(data_dir / "processed/hotspots.geojson", hotspots(HOTSPOT))
    path = write(data_dir / "manifest.json", manifest(hotspot_layer()))
    assert validate.validate_file(path, registry, data_dir) == []


def test_manifest_missing_file_fails(registry, data_dir):
    path = write(data_dir / "manifest.json", manifest(hotspot_layer()))
    assert any("does not exist" in e for e in validate.validate_file(path, registry, data_dir))


def test_manifest_unknown_type_fails(registry, data_dir):
    write(data_dir / "processed/hotspots.geojson", hotspots(HOTSPOT))
    path = write(data_dir / "manifest.json", manifest(hotspot_layer(type="heatmap")))
    assert validate.validate_file(path, registry, data_dir)


def test_manifest_image_needs_corners(registry, data_dir):
    (data_dir / "processed/population.png").write_bytes(b"png")
    layer = {"id": "population", "name": "Population", "file": "processed/population.png",
             "type": "image", "temporal": False, "enabled": False}
    path = write(data_dir / "manifest.json", manifest(layer))
    assert any("corners" in e for e in validate.validate_file(path, registry, data_dir))


def test_manifest_duplicate_ids_fail(registry, data_dir):
    write(data_dir / "processed/hotspots.geojson", hotspots(HOTSPOT))
    path = write(data_dir / "manifest.json", manifest(hotspot_layer(), hotspot_layer()))
    assert any("duplicate id" in e for e in validate.validate_file(path, registry, data_dir))


def test_temporal_layer_needs_t(registry, data_dir):
    no_t = copy.deepcopy(HOTSPOT)
    del no_t["properties"]["t"]
    write(data_dir / "processed/hotspots.geojson", hotspots(no_t))
    path = write(data_dir / "manifest.json", manifest(hotspot_layer()))
    assert any("numeric 't'" in e for e in validate.validate_file(path, registry, data_dir))


# --- other files --------------------------------------------------------------

def test_generic_geojson_layer(registry, data_dir):
    weather = {"type": "FeatureCollection", "updated": UPDATED, "features": [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [-71, -35]},
         "properties": {"t": 493927.0, "speed": 12.0, "rotation": 90.0}}]}
    path = write(data_dir / "processed/weather.geojson", weather)
    assert validate.validate_file(path, registry, data_dir) == []


def test_unknown_json_file_fails(registry, data_dir):
    path = write(data_dir / "processed/alertas.json", [])
    assert any("not a contract file" in e for e in validate.validate_file(path, registry, data_dir))


def test_invalid_json_fails(registry, data_dir):
    path = data_dir / "processed/hotspots.geojson"
    path.write_text("{not json", encoding="utf-8")
    assert any("invalid JSON" in e for e in validate.validate_file(path, registry, data_dir))
