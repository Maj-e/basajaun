"""Tests for the combined risk score + evacuation estimate (W3-B11)."""
import json

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import Point, box, mapping

import risk_score as rs
import validate

C = rs.cfg()


@pytest.mark.parametrize("points, level", [
    ({"F": 1, "P": 0, "S": 0, "W": 0}, "low"),        # a fire alone
    ({"F": 1, "P": 1, "S": 1, "W": 0}, "medium"),     # smoke + people
    ({"F": 1, "P": 0, "S": 0, "W": 1}, "high"),       # fire + strong wind
    ({"F": 1, "P": 1, "S": 1, "W": 1}, "extreme"),    # people + fire + smoke + strong wind: the most
    ({"F": 2, "P": 2, "S": 2, "W": 0}, "high"),       # high score without wind
])
def test_combinations(points, level):
    assert rs.risk_level(points) == level


def test_levels_never_go_down_with_more_factors():
    order = rs.LEVELS.index
    base = {"F": 1, "P": 0, "S": 0, "W": 0}
    for extra in ({"P": 1}, {"P": 1, "S": 1}, {"P": 1, "S": 1, "W": 1}):
        assert order(rs.risk_level({**base, **extra})) >= order(rs.risk_level(base))


def test_factor_points():
    assert rs.factor_points(150, 3, 500, None, 10, C) == {"F": 2, "P": 0, "S": 0, "W": 0}
    assert rs.factor_points(10, 25, 2_000, 500, 22, C) == {"F": 2, "P": 1, "S": 1, "W": 1}
    assert rs.factor_points(10, 3, 20_000, 15_000, 35, C) == {"F": 1, "P": 2, "S": 2, "W": 2}
    assert rs.factor_points(10, 3, 0, None, None, C)["W"] == 0  # no weather: no wind factor


def test_score_percent():
    assert rs.score_percent({"F": 2, "P": 2, "S": 2, "W": 2}) == 100
    assert rs.score_percent({"F": 1, "P": 0, "S": 0, "W": 0}) == 12


@pytest.fixture
def episode(tmp_path):
    """One fire at (-5.0, 36.5); a village inside its 6 h spread (2 km east); a town 4 km west (warning zone)."""
    west, north, res = -5.2, 36.7, 0.005
    data = np.zeros((80, 80), dtype="float32")
    def put(lon, lat, people):
        data[int((north - lat) / res), int((lon - west) / res)] = people
    put(-4.976, 36.5, 800)      # ~2.1 km east: in the spread, outside the 1 km buffer
    put(-5.045, 36.5, 5_000)    # ~4 km west: warning only
    put(-5.0, 36.5, 50)         # in the fire
    with rasterio.open(tmp_path / "population.tif", "w", driver="GTiff", height=80, width=80, count=1,
                       dtype="float32", crs="EPSG:4326", transform=from_origin(west, north, res, res)) as dst:
        dst.write(data, 1)
    fire = Point(-5.0, 36.5).buffer(0.003)
    (tmp_path / "fires.geojson").write_text(json.dumps({"type": "FeatureCollection", "updated_at": "x", "features": [
        {"type": "Feature", "geometry": mapping(fire),
         "properties": {"fire_id": 1, "frp_max": 120.0, "n_hotspots": 5, "t_start": 491850.0, "t_end": 491852.0}}]}))
    (tmp_path / "spread.geojson").write_text(json.dumps({"type": "FeatureCollection", "updated_at": "x", "features": [
        {"type": "Feature", "geometry": mapping(box(-5.0, 36.49, -4.97, 36.51)), "properties": {"fire_id": 1}}]}))
    (tmp_path / "weather.geojson").write_text(json.dumps({"type": "FeatureCollection", "updated_at": "x", "features": [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [-5.0, 36.5]},
         "properties": {"t": 491850.0 + h, "speed": 32.0, "direction": 270.0}} for h in range(3)]}))
    alerts = [
        {"fire_id": 1, "type": "population", "risk": "high", "since": "2026-02-09T18:00:00Z", "message": "x",
         "pop_1km": 50, "pop_5km": 5_850, "pop_10km": 5_850, "wind_toward_population": False,
         "center": [-5.0, 36.5], "color": "#d7301f"},
        {"fire_id": 1, "type": "smoke", "risk": "low", "since": "2026-02-09T18:00:00Z", "message": "x",
         "smoke_people": 800, "wind_kmh": 32.0, "pop_1km": 50, "pop_5km": 5_850, "pop_10km": 5_850,
         "wind_toward_population": False, "center": [-5.0, 36.5], "color": "#fdcc8a"},
    ]
    (tmp_path / "alerts.json").write_text(json.dumps({"updated_at": "x", "alerts": alerts}))
    return tmp_path


def test_run_scores_and_evacuates(episode):
    assert rs.run(episode)
    p = json.loads((episode / "fires.geojson").read_text())["features"][0]["properties"]
    assert p["risk_level"] == "extreme"                      # fire + people + smoke + strong wind
    assert set(p["risk_factors"]) == {"fire", "people", "smoke", "strong wind"}
    assert p["evacuate_people"] == pytest.approx(850, abs=1)  # fire (50) + village in the 6 h spread (800)
    assert p["warn_people"] == pytest.approx(5_000, abs=1)    # town 4 km west


def test_outputs_pass_the_contract(episode):
    rs.run(episode)
    registry = validate.load_registry()
    for name in ("fire_risk", "evacuation"):
        path = episode / f"{name}.geojson"
        assert validate.validate_file(path, registry, episode.parent) == [], name
    risk = json.loads((episode / "fire_risk.geojson").read_text())["features"][0]["properties"]
    assert risk["color"] == rs.LEVEL_STYLE["extreme"]["color"]


def test_skips_without_population(tmp_path, capsys):
    (tmp_path / "fires.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": []}))
    assert rs.run(tmp_path) is False
    assert "[SKIP]" in capsys.readouterr().out
