"""Tests for the GeoJSON compactor (smaller files for the browser)."""
import json

import compact

LONG = [[-7.136589818557351, 42.03496144338319], [-7.137163251667416, 42.03490980115287],
        [-7.137165000000001, 42.03491000000001], [-7.1366, 42.0351], [-7.136589818557351, 42.03496144338319]]


def write(path, geometry, **props):
    doc = {"type": "FeatureCollection", "updated_at": "2026-11-15T10:00:00Z",
           "features": [{"type": "Feature", "geometry": geometry, "properties": {"fire_id": 1, "frp": 3.123456789, **props}}]}
    path.write_text(json.dumps(doc, indent=2))
    return doc


def test_coordinates_are_rounded_and_file_gets_smaller(tmp_path):
    path = tmp_path / "spread.geojson"
    write(path, {"type": "Polygon", "coordinates": [LONG]})
    before, after = compact.compact_file(path)
    assert after < before
    doc = json.loads(path.read_text())
    ring = doc["features"][0]["geometry"]["coordinates"][0]
    assert all(len(str(c).split(".")[1]) <= 5 for p in ring for c in p)
    assert ring[0] == ring[-1]  # still closed
    assert "\n" not in path.read_text()


def test_properties_and_updated_at_are_untouched(tmp_path):
    path = tmp_path / "x.geojson"
    write(path, {"type": "Point", "coordinates": [-7.1379123456, 42.0529987654]})
    compact.compact_file(path)
    doc = json.loads(path.read_text())
    assert doc["updated_at"] == "2026-11-15T10:00:00Z"
    assert doc["features"][0]["properties"]["frp"] == 3.123456789
    assert doc["features"][0]["geometry"]["coordinates"] == [-7.13791, 42.053]


def test_repeated_points_after_rounding_are_dropped_but_a_ring_stays_valid():
    ring = [[0.0, 0.0], [0.000001, 0.000001], [0.0, 1.0], [1.0, 1.0], [0.0, 0.0]]
    out = compact.compact_geojson({"features": [{"geometry": {"type": "Polygon", "coordinates": [ring]}}]})
    kept = out["features"][0]["geometry"]["coordinates"][0]
    assert kept == [[0.0, 0.0], [0.0, 1.0], [1.0, 1.0], [0.0, 0.0]]


def test_a_collapsing_ring_keeps_its_points():
    tiny = [[0.0, 0.0], [0.000001, 0.0], [0.000001, 0.000001], [0.0, 0.0]]
    out = compact.compact_geojson({"features": [{"geometry": {"type": "Polygon", "coordinates": [tiny]}}]})
    assert len(out["features"][0]["geometry"]["coordinates"][0]) >= 4


def test_already_compact_file_is_left_alone(tmp_path):
    path = tmp_path / "hotspots.geojson"
    path.write_text(json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [-7.1379, 42.0529]}, "properties": {}}]},
        separators=(",", ":")))
    text = path.read_text()
    assert compact.compact_file(path) == (len(text), len(text))
    assert path.read_text() == text
