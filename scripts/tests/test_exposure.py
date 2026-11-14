import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import Point, mapping

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from exposure import (
    classify_base_risk,
    compute_alerts,
    is_wind_blowing_toward_target,
    upgrade_risk_one_level,
)


def _create_synthetic_population_tif(path: Path) -> None:
    """
    Create a 20x20 1 km-ish synthetic population GeoTIFF around (-70.65, -33.45).
    Places a dense town (2,500 people) ~3 km north of (-70.65, -33.46).
    """
    data = np.zeros((20, 20), dtype=np.float32)
    # Row 6, Col 10 corresponds to lon=-70.65, lat=-33.43 (~3.3 km north of -33.46)
    data[6, 10] = 2500.0
    # Row 9, Col 10 corresponds to lon=-70.65, lat=-33.46 (right on fire 1)
    data[9, 10] = 150.0

    transform = from_origin(west=-70.75, north=-33.37, xsize=0.01, ysize=0.01)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=20,
        width=20,
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=transform,
        nodata=0.0,
    ) as dst:
        dst.write(data, 1)


def test_risk_classification_rules():
    assert classify_base_risk(pop_1km=1000, pop_5km=1000, pop_10km=1000, frp_max=10.0) == "critical"
    assert classify_base_risk(pop_1km=50, pop_5km=12000, pop_10km=15000, frp_max=120.0) == "critical"
    # High pop_5km but frp_max < 100 -> high, not critical
    assert classify_base_risk(pop_1km=50, pop_5km=12000, pop_10km=15000, frp_max=80.0) == "high"
    assert classify_base_risk(pop_1km=0, pop_5km=1500, pop_10km=2000, frp_max=20.0) == "high"
    assert classify_base_risk(pop_1km=0, pop_5km=50, pop_10km=250, frp_max=20.0) == "medium"
    assert classify_base_risk(pop_1km=0, pop_5km=10, pop_10km=50, frp_max=20.0) == "low"


def test_wind_direction_toward_target():
    # Fire at (-70.65, -33.46), town due North at (-70.65, -33.43)
    # Wind blowing FROM South (180 deg) blows TOWARD North (0 deg) -> True
    assert is_wind_blowing_toward_target(-70.65, -33.46, -70.65, -33.43, 180.0, 25.0) is True
    # Wind blowing FROM North (0 deg) blows TOWARD South (180 deg) -> False
    assert is_wind_blowing_toward_target(-70.65, -33.46, -70.65, -33.43, 0.0, 30.0) is False
    # Wind blowing toward North, but speed < 20 km/h -> False
    assert is_wind_blowing_toward_target(-70.65, -33.46, -70.65, -33.43, 180.0, 15.0) is False
    assert upgrade_risk_one_level("high") == "critical"
    assert upgrade_risk_one_level("critical") == "critical"


def test_compute_alerts_with_wind_upgrade_and_contract_shape(tmp_path: Path):
    tif_path = tmp_path / "population.tif"
    _create_synthetic_population_tif(tif_path)

    fires = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": mapping(Point(-70.645, -33.465).buffer(0.002)),
                "properties": {
                    "fire_id": 10,
                    "start": "2026-02-14T07:42:00Z",
                    "frp_max": 60.0,
                },
            },
            {
                "type": "Feature",
                "geometry": mapping(Point(-70.740, -33.550).buffer(0.002)),
                "properties": {
                    "fire_id": 20,
                    "start": "2026-02-14T09:00:00Z",
                    "frp_max": 15.0,
                },
            },
        ],
    }

    # Wind blowing FROM South (185 deg) at 28 km/h -> pushes Fire 10 toward town at (-70.65, -33.43)
    meteo = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [-70.65, -33.46]},
                "properties": {
                    "t": 493927.7,
                    "wind_speed": 28.0,
                    "wind_direction": 185.0,
                },
            }
        ],
    }

    output = compute_alerts(fires, tif_path, meteo)

    # Check root object contract
    assert "updated_at" in output
    assert isinstance(output["alerts"], list)
    assert len(output["alerts"]) == 2

    # Fire 10 starts as 'high' (pop_5km >= 1000) and upgrades to 'critical' due to wind
    top_alert = output["alerts"][0]
    assert top_alert["fire_id"] == 10
    assert top_alert["risk"] == "critical"
    assert top_alert["color"] == "#a50f15"
    assert top_alert["wind_toward_population"] is True
    assert top_alert["pop_5km"] >= 2500

    # Fire 20 is far from population -> 'low'
    second_alert = output["alerts"][1]
    assert second_alert["fire_id"] == 20
    assert second_alert["risk"] == "low"
    assert second_alert["wind_toward_population"] is False

# --- weather.py keys + skip when inputs are missing ---------------------------------

import json  # noqa: E402

import exposure  # noqa: E402
import validate  # noqa: E402

FIRE_NEAR_TOWN = {
    "type": "FeatureCollection",
    "features": [{
        "type": "Feature",
        "geometry": mapping(Point(-70.645, -33.465).buffer(0.002)),
        "properties": {"fire_id": 10, "start": "2026-02-14T07:42:00Z", "frp_max": 60.0},
    }],
}

# Same wind as above, written the way weather.py writes it (speed / direction)
WEATHER = {
    "type": "FeatureCollection",
    "updated_at": "2026-02-14T08:00:00Z",
    "features": [{
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [-70.65, -33.46]},
        "properties": {"t": 493927.7, "speed": 28.0, "direction": 185.0},
    }],
}


def test_wind_from_weather_py_keys_escalates_risk(tmp_path: Path):
    tif_path = tmp_path / "population.tif"
    _create_synthetic_population_tif(tif_path)
    [alert] = compute_alerts(FIRE_NEAR_TOWN, tif_path, WEATHER)["alerts"]
    assert alert["wind_toward_population"] is True
    assert alert["risk"] == "critical"


def test_run_exposure_reads_weather_geojson_and_writes_valid_alerts(tmp_path: Path):
    _create_synthetic_population_tif(tmp_path / "population.tif")
    (tmp_path / "fires.geojson").write_text(json.dumps(FIRE_NEAR_TOWN))
    (tmp_path / "weather.geojson").write_text(json.dumps(WEATHER))

    alerts_path = exposure.run_exposure(tmp_path)

    alerts = json.loads(alerts_path.read_text())["alerts"]
    [alert] = [a for a in alerts if a["type"] == "population"]
    assert alert["wind_toward_population"] is True
    assert validate.validate_file(alerts_path, validate.load_registry(), tmp_path) == []


def test_run_exposure_skips_without_population(tmp_path: Path, capsys):
    (tmp_path / "fires.geojson").write_text(json.dumps(FIRE_NEAR_TOWN))
    assert exposure.run_exposure(tmp_path) is None
    assert "[SKIP]" in capsys.readouterr().out
    assert not (tmp_path / "alerts.json").exists()


def test_run_exposure_skips_without_fires(tmp_path: Path, capsys):
    _create_synthetic_population_tif(tmp_path / "population.tif")
    assert exposure.run_exposure(tmp_path) is None
    assert "W2-B2" in capsys.readouterr().out
