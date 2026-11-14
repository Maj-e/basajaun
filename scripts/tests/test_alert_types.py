"""Tests for the typed alerts (W3-B8): wind, smoke, water contamination."""
import math

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import Point, box, mapping

import alert_types as at
import validate

T0 = 491850.0  # hours since 1970
FIRE_LON, FIRE_LAT = -5.0, 36.5


def population_tif(path, town_lon, town_lat, people=20_000):
    """0.01° grid around the fire, empty except one town cell."""
    west, north, res = -5.3, 36.8, 0.01
    data = np.zeros((60, 60), dtype="float32")
    row, col = int((north - town_lat) / res), int((town_lon - west) / res)
    data[row, col] = people
    with rasterio.open(path, "w", driver="GTiff", height=60, width=60, count=1, dtype="float32",
                       crs="EPSG:4326", transform=from_origin(west, north, res, res)) as dst:
        dst.write(data, 1)
    return path


def fires(gw_vulnerability=None):
    props = {"fire_id": 1, "t_start": T0, "t_end": T0 + 3, "start": "2026-02-09T18:00:00Z"}
    if gw_vulnerability:
        props.update(gw_vulnerability=gw_vulnerability, gw_body="Sierra X")
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": mapping(Point(FIRE_LON, FIRE_LAT).buffer(0.005)), "properties": props}]}


def population_alert():
    return {"fire_id": 1, "type": "population", "risk": "high", "since": "2026-02-09T18:00:00Z",
            "message": "x", "pop_1km": 10, "pop_5km": 500, "pop_10km": 2000,
            "wind_toward_population": False, "center": [FIRE_LON, FIRE_LAT], "color": "#d7301f"}


def weather(speed, direction, hours=4):
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [FIRE_LON + 0.01, FIRE_LAT]},
         "properties": {"t": T0 + h, "speed": speed, "direction": direction}} for h in range(hours)]}


def by_type(alerts, kind):
    return [a for a in alerts if a["type"] == kind]


def test_compass():
    assert [at.compass(d) for d in (0, 44, 46, 90, 225, 359)] == ["N", "NE", "NE", "E", "SW", "N"]


@pytest.mark.parametrize("speed, risk", [(20, None), (30, "high"), (44.9, "high"), (45, "critical")])
def test_wind_risk(speed, risk):
    assert at.wind_risk(speed, at.thresholds()) == risk


def test_strong_wind_alert(tmp_path):
    tif = population_tif(tmp_path / "pop.tif", -5.2, 36.7, people=0)
    alerts = at.typed_alerts(fires(), [population_alert()], tif, weather(38, 270))
    [wind] = by_type(alerts, "wind")
    assert wind["risk"] == "high" and wind["wind_kmh"] == 38
    assert "38 km/h from W" in wind["message"]
    assert wind["pop_5km"] == 500 and wind["center"] == [FIRE_LON, FIRE_LAT]  # panel keeps working


def test_no_wind_alert_below_threshold(tmp_path):
    tif = population_tif(tmp_path / "pop.tif", -5.2, 36.7, people=0)
    assert by_type(at.typed_alerts(fires(), [population_alert()], tif, weather(12, 270)), "wind") == []


def test_smoke_reaches_the_town_downwind(tmp_path):
    # Town 10 km east of the fire; a west wind (from 270°) blows the smoke east onto it
    tif = population_tif(tmp_path / "pop.tif", FIRE_LON + 0.11, FIRE_LAT, people=20_000)
    [smoke] = by_type(at.typed_alerts(fires(), [population_alert()], tif, weather(20, 270)), "smoke")
    assert smoke["smoke_people"] == 20_000 and smoke["risk"] == "high"
    assert "from W" in smoke["message"]


def test_no_smoke_when_the_wind_blows_away_from_the_town(tmp_path):
    tif = population_tif(tmp_path / "pop.tif", FIRE_LON + 0.11, FIRE_LAT, people=20_000)
    # East wind (from 90°) blows the smoke west, away from the town
    assert by_type(at.typed_alerts(fires(), [population_alert()], tif, weather(20, 90)), "smoke") == []


def test_smoke_sector_points_downwind():
    sector = at.smoke_sector(Point(0, 0), 270.0, 10_000, 30.0)  # west wind -> smoke goes east
    assert sector.contains(Point(8_000, 0)) and not sector.contains(Point(-8_000, 0))
    assert not sector.contains(Point(0, 8_000))  # 90° off the axis: outside ±30°


def test_contamination_under_the_fire(tmp_path):
    tif = population_tif(tmp_path / "pop.tif", -5.2, 36.7, people=0)
    [c] = by_type(at.typed_alerts(fires("high"), [population_alert()], tif, weather(10, 270)), "contamination")
    assert c["risk"] == "high" and c["gw_vulnerability"] == "high" and "under the fire" in c["message"]


def test_contamination_in_the_spread(tmp_path):
    tif = population_tif(tmp_path / "pop.tif", -5.2, 36.7, people=0)
    spread = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": mapping(box(FIRE_LON, FIRE_LAT - 0.02, FIRE_LON + 0.1, FIRE_LAT + 0.02)),
         "properties": {"fire_id": 1}}]}
    groundwater = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": mapping(box(FIRE_LON + 0.05, FIRE_LAT - 0.1, FIRE_LON + 0.2, FIRE_LAT + 0.1)),
         "properties": {"name": "Karst Y", "vulnerability": "high"}}]}
    [c] = by_type(at.typed_alerts(fires(), [population_alert()], tif, weather(10, 270), spread, groundwater),
                  "contamination")
    assert c["gw_body"] == "Karst Y" and "6 h spread" in c["message"]


def test_low_vulnerability_aquifer_is_no_alert(tmp_path):
    tif = population_tif(tmp_path / "pop.tif", -5.2, 36.7, people=0)
    assert by_type(at.typed_alerts(fires("low"), [population_alert()], tif, weather(10, 270)), "contamination") == []


def test_every_typed_alert_passes_the_contract(tmp_path):
    import json
    tif = population_tif(tmp_path / "pop.tif", FIRE_LON + 0.11, FIRE_LAT, people=60_000)
    alerts = [population_alert()] + at.typed_alerts(fires("high"), [population_alert()], tif, weather(50, 270))
    assert {a["type"] for a in alerts} == {"population", "wind", "smoke", "contamination"}
    path = tmp_path / "processed" / "alerts.json"
    path.parent.mkdir()
    path.write_text(json.dumps({"updated_at": "2026-02-14T08:00:00Z", "alerts": alerts}))
    assert validate.validate_file(path, validate.load_registry(), tmp_path) == []


def test_calm_wind_gives_no_smoke_sector(tmp_path):
    tif = population_tif(tmp_path / "pop.tif", FIRE_LON + 0.11, FIRE_LAT, people=20_000)
    assert by_type(at.typed_alerts(fires(), [population_alert()], tif, weather(3, 270)), "smoke") == []


def test_smoke_only_reaches_as_far_as_the_wind_carries_it(tmp_path):
    # Town 10 km downwind: 6 km/h × 2 h = 12 km reaches it, 4.5 km/h is calm, a farther town at 20 km is out of reach
    near = population_tif(tmp_path / "near.tif", FIRE_LON + 0.11, FIRE_LAT, people=20_000)
    far = population_tif(tmp_path / "far.tif", FIRE_LON + 0.22, FIRE_LAT, people=20_000)
    assert by_type(at.typed_alerts(fires(), [population_alert()], near, weather(6, 270)), "smoke")
    assert not by_type(at.typed_alerts(fires(), [population_alert()], far, weather(6, 270)), "smoke")
