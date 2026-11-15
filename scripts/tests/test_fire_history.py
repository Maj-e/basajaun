"""fire_history.py: fires as they were over time (snapshots), and the zones derived from them."""
import json

from shapely.geometry import shape

import fire_history
import spread


def hotspot(t, lon, lat, frp=10.0, fire_id=1):
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {"fire_id": fire_id, "t": t, "frp": frp}}


def fire(points, fire_id=1):
    """A fire built like fires.py does: hull + 500 m of its hotspots."""
    ts = [p["properties"]["t"] for p in points]
    geom = fire_history.hull_at([tuple(p["geometry"]["coordinates"]) for p in points])
    return {"type": "Feature", "geometry": json.loads(json.dumps(geom.__geo_interface__)),
            "properties": {"fire_id": fire_id, "t_start": min(ts), "t_end": max(ts), "frp_max": 10.0,
                           "n_hotspots": len(points), "start": "2025-08-15T00:00:00Z", "end": "2025-08-16T00:00:00Z"}}


POINTS = [hotspot(100.0, -7.0, 42.0), hotspot(101.0, -7.01, 42.0), hotspot(112.0, -7.05, 42.05), hotspot(121.0, -7.1, 42.1)]


def test_boundaries_cover_start_steps_and_end():
    assert fire_history.boundaries(100.0, 121.0, 6.0) == [100.0, 106.0, 112.0, 118.0, 121.0]
    assert fire_history.boundaries(100.0, 100.0) == [100.0]


def test_snapshots_grow_and_the_last_is_the_final_polygon():
    fc = {"type": "FeatureCollection", "features": [fire(POINTS)]}
    snaps = fire_history.snapshots(fc, {"type": "FeatureCollection", "features": POINTS})[1]
    areas = [s["geometry"].area for s in snaps]
    assert areas == sorted(areas) and areas[0] < areas[-1]
    assert snaps[0]["n_hotspots"] == 1 and snaps[-1]["n_hotspots"] == 4
    assert snaps[-1]["t_until"] is None and all(s["t_until"] for s in snaps[:-1])
    assert snaps[-1]["active_until"] == 121.0 + fire_history.ACTIVE_HOURS
    assert snaps[-1]["geometry"].equals(shape(fc["features"][0]["geometry"]))
    # Consecutive snapshots tile the time axis
    assert all(a["t_until"] == b["t_from"] for a, b in zip(snaps, snaps[1:]))


def test_without_hotspots_a_fire_has_one_final_snapshot():
    fc = {"type": "FeatureCollection", "features": [fire(POINTS)]}
    snaps = fire_history.snapshots(fc, None)[1]
    assert len(snaps) == 1 and snaps[0]["t_until"] is None


def test_spread_has_one_projection_per_snapshot(tmp_path):
    fc = {"type": "FeatureCollection", "features": [fire(POINTS)]}
    (tmp_path / "fires.geojson").write_text(json.dumps(fc))
    (tmp_path / "hotspots.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": POINTS}))
    out = spread.generate_spread(tmp_path / "fires.geojson", tmp_path / "none.geojson", tmp_path / "spread.geojson")
    props = [f["properties"] for f in out["features"]]
    assert len(props) == 5 and props[-1]["last"] and not props[0]["last"]
    assert props[-1]["t_until"] == 121.0 + 24.0
    assert [p["t_start"] for p in props] == sorted(p["t_start"] for p in props)
    assert props[0]["area_km2"] < props[-1]["area_km2"]
