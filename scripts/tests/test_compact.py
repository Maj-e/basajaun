"""compact.py: lighter geometry, same features and properties."""
import json

from compact import compact_file, compact_geometry


def test_point_is_rounded_to_five_decimals():
    g = compact_geometry({"type": "Point", "coordinates": [-7.124822922359398, 41.13596404010658]}, None)
    assert g == {"type": "Point", "coordinates": [-7.12482, 41.13596]}


def test_polygon_is_simplified_and_stays_a_polygon():
    # A circle-like ring with many vertices a few metres apart
    import math
    ring = [[-7 + 0.01 * math.cos(a / 100 * 2 * math.pi), 41 + 0.01 * math.sin(a / 100 * 2 * math.pi)] for a in range(100)]
    ring.append(ring[0])
    g = compact_geometry({"type": "Polygon", "coordinates": [ring]}, 2e-4)
    assert g["type"] == "Polygon"
    assert 8 < len(g["coordinates"][0]) < len(ring)


def test_file_keeps_features_and_properties(tmp_path):
    path = tmp_path / "fires.geojson"
    doc = {"type": "FeatureCollection", "updated_at": "2026-11-15T00:00:00Z", "features": [
        {"type": "Feature", "properties": {"fire_id": 1, "area_km2": 3.09},
         "geometry": {"type": "Polygon", "coordinates": [[[0.123456789, 0], [1, 0], [1, 1], [0.123456789, 0]]]}}]}
    path.write_text(json.dumps(doc, indent=2))
    before, after = compact_file(path)
    out = json.loads(path.read_text())
    assert after < before
    assert out["updated_at"] == doc["updated_at"]
    assert out["features"][0]["properties"] == {"fire_id": 1, "area_km2": 3.09}
