import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dedup import deduplicate_hotspots


def _make_feature(hotspot_id: str, sensor: str, lon: float, lat: float, t_hours: float) -> dict:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": {
            "id": hotspot_id,
            "sensor": sensor,
            "satellite": "NOAA-20" if sensor == "VIIRS" else "Terra",
            "timestamp_utc": "2026-02-14T12:00:00Z",
            "date": "2026-02-14",
            "t": t_hours,
            "confidence": "high",
            "frp": 45.0,
            "brightness_k": 340.0,
            "day_night": "D",
            "resolution_m": 375 if sensor == "VIIRS" else 1000,
            "detected_by": [sensor],
            "fire_id": None,
            "color": "#d7301f",
            "radius": 7.5,
            "border": "#222222" if sensor == "VIIRS" else "#ffffff",
        },
    }


def test_merges_modis_within_1km_and_60min():
    # ~300 m apart and 0.5 h (30 min) apart -> should merge into VIIRS
    viirs = _make_feature("V1", "VIIRS", -70.6483, -33.4569, 492000.0)
    modis_close = _make_feature("M1", "MODIS", -70.6460, -33.4569, 492000.5)

    geojson = {
        "type": "FeatureCollection",
        "updated_at": "2026-02-14T13:00:00Z",
        "features": [viirs, modis_close],
    }

    result, merged = deduplicate_hotspots(geojson)

    assert merged == 1
    assert len(result["features"]) == 1
    assert result["features"][0]["properties"]["id"] == "V1"
    assert result["features"][0]["properties"]["detected_by"] == ["MODIS", "VIIRS"]


def test_keeps_modis_when_outside_time_or_distance_threshold():
    viirs = _make_feature("V1", "VIIRS", -70.6483, -33.4569, 492000.0)
    # Close in space (~200 m), but 1.5 hours (90 min) apart -> keep both
    modis_late = _make_feature("M_LATE", "MODIS", -70.6470, -33.4569, 492001.5)
    # Same timestamp, but ~5 km away -> keep both
    modis_far = _make_feature("M_FAR", "MODIS", -70.7000, -33.4569, 492000.0)

    geojson = {
        "type": "FeatureCollection",
        "updated_at": "2026-02-14T13:00:00Z",
        "features": [viirs, modis_late, modis_far],
    }

    result, merged = deduplicate_hotspots(geojson)

    assert merged == 0
    assert len(result["features"]) == 3
    assert result["features"][0]["properties"]["detected_by"] == ["VIIRS"]