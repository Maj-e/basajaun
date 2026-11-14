import math

import pytest
import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from fires import cluster_fires, fire_style
from weather import wind_style


def _make_hotspot(hid: str, lon: float, lat: float, t: float, ts: str, frp: float) -> dict:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": {
            "id": hid,
            "lat": lat,
            "lon": lon,
            "sensor": "VIIRS",
            "satellite": "N20",
            "timestamp_utc": ts,
            "date": ts[:10],
            "t": t,
            "confidence": "nominal",
            "frp": frp,
            "brightness_k": 340.0,
            "day_night": "D",
            "resolution_m": 375,
            "detected_by": ["VIIRS"],
            "fire_id": None,
            "color": "#ff6600",
            "radius": 6,
            "border": "#ffffff",
        },
    }


def test_cluster_fires_groups_nearby_and_separates_noise(tmp_path: Path) -> None:
    hotspots = [
        _make_hotspot("h1", -71.0000, -35.0000, 100.0, "2026-02-05T04:00:00Z", 25.0),
        _make_hotspot("h2", -71.0015, -35.0010, 101.0, "2026-02-05T05:00:00Z", 120.0),
        _make_hotspot("h3", -71.8000, -37.2000, 250.0, "2026-02-11T12:00:00Z", 10.0),
    ]
    in_file = tmp_path / "hotspots.geojson"
    out_file = tmp_path / "fires.geojson"
    in_file.write_text(json.dumps({"type": "FeatureCollection", "features": hotspots}), encoding="utf-8")

    cluster_fires(in_file, out_file, update_hotspots=True)

    fires_fc = json.loads(out_file.read_text(encoding="utf-8"))
    assert "updated_at" in fires_fc
    assert len(fires_fc["features"]) == 1
    props = fires_fc["features"][0]["properties"]
    assert props["fire_id"] == 1
    assert props["n_hotspots"] == 2
    assert props["frp_max"] == 120.0
    assert props["start"] == "2026-02-05T04:00:00Z"
    assert props["end"] == "2026-02-05T05:00:00Z"
    assert props["area_km2"] > 0.7
    assert props["color"] == "#a50f15"

    updated_hotspots = json.loads(in_file.read_text(encoding="utf-8"))["features"]
    assert updated_hotspots[0]["properties"]["fire_id"] == 1
    assert updated_hotspots[1]["properties"]["fire_id"] == 1
    assert updated_hotspots[2]["properties"]["fire_id"] is None


def test_cluster_fires_handles_empty_input(tmp_path: Path) -> None:
    in_file = tmp_path / "empty.geojson"
    out_file = tmp_path / "fires_empty.geojson"
    in_file.write_text(json.dumps({"type": "FeatureCollection", "features": []}), encoding="utf-8")

    cluster_fires(in_file, out_file, update_hotspots=False)
    fires_fc = json.loads(out_file.read_text(encoding="utf-8"))
    assert "updated_at" in fires_fc
    assert fires_fc["features"] == []


def test_fire_and_wind_styles() -> None:
    assert fire_style(150.0, 3) == ("#a50f15", 0.45)
    assert fire_style(40.0, 2) == ("#de2d26", 0.38)
    assert fire_style(10.0, 2) == ("#fb6a4a", 0.30)
    assert wind_style(50.0) == ("#d7301f", 1.35)
    assert wind_style(10.0) == ("#91cf60", 0.75)


def test_spread_projection_generates_downwind_ellipse(tmp_path: Path) -> None:
    from spread import generate_spread

    fires_file = tmp_path / "fires.geojson"
    weather_file = tmp_path / "weather.geojson"
    spread_file = tmp_path / "spread.geojson"

    fires_file.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "updated_at": "2026-02-14T12:00:00Z",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[-71.01, -35.01], [-71.00, -35.01], [-71.00, -35.00], [-71.01, -35.00], [-71.01, -35.01]]],
                        },
                        "properties": {
                            "fire_id": 1,
                            "start": "2026-02-14T06:00:00Z",
                            "end": "2026-02-14T12:00:00Z",
                            "n_hotspots": 4,
                            "frp_max": 85.0,
                            "area_km2": 1.0,
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    weather_file.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "updated_at": "2026-02-14T12:00:00Z",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [-71.0, -35.0]},
                        "properties": {"t": 492000.0, "speed": 30.0, "direction": 180.0},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    out = generate_spread(fires_file, weather_file, spread_file)
    assert "updated_at" in out
    assert len(out["features"]) == 1
    props = out["features"][0]["properties"]
    assert props["fire_id"] == 1
    assert props["horizon_hours"] == 6
    assert props["wind_to_deg"] == 0.0
    assert props["spread_km"] > 2.0
    assert props["area_km2"] > 1.0


def test_surface_wind_uv_points_where_the_wind_blows() -> None:
    from weather import wind_uv

    # 36 km/h = 10 m/s. Meteorological direction = where it comes FROM.
    assert wind_uv(36.0, 270.0) == pytest.approx((10.0, 0.0), abs=0.01)   # west wind blows east
    assert wind_uv(36.0, 0.0) == pytest.approx((0.0, -10.0), abs=0.01)    # north wind blows south
    assert wind_uv(36.0, 90.0) == pytest.approx((-10.0, 0.0), abs=0.01)   # east wind blows west
    u, v = wind_uv(36.0, 225.0)                                           # south-west wind blows north-east
    assert u > 0 and v > 0 and math.hypot(u, v) == pytest.approx(10.0, abs=0.02)
    assert wind_uv(0.0, 123.0) == (0.0, 0.0) or wind_uv(0.0, 123.0) == (-0.0, -0.0)


def test_wind_particles_layer_reads_weather_and_is_off() -> None:
    import make_manifest

    [layer] = [l for l in make_manifest.LAYERS if l["id"] == "wind_particles"]
    assert layer["type"] == "particles" and layer["temporal"] and not layer["active"]
    assert layer["file"].endswith("weather.geojson")


@pytest.mark.parametrize("lon, lat, epsg", [
    (-71.0, -35.0, "EPSG:32719"),   # Chile
    (-5.0, 36.5, "EPSG:32630"),     # Sierra Bermeja (Málaga)
    (-118.5, 34.1, "EPSG:32611"),   # Los Angeles
    (2.2, 41.4, "EPSG:32631"),      # Barcelona
])
def test_spread_uses_the_fires_own_utm_zone(lon, lat, epsg) -> None:
    from spread import utm_crs_for

    assert utm_crs_for(lon, lat) == epsg


def test_spread_area_matches_the_drawn_polygon_outside_chile(tmp_path: Path) -> None:
    """The old fixed Chile UTM zone made a Málaga fire's ellipse and area about twice too big."""
    import geopandas as gpd
    from shapely.geometry import shape
    from spread import generate_spread

    fire = {"type": "Feature", "properties": {"fire_id": 1, "end": "2021-09-09T12:00:00Z", "frp_max": 85.0},
            "geometry": {"type": "Polygon", "coordinates": [[[-5.01, 36.49], [-5.0, 36.49], [-5.0, 36.5], [-5.01, 36.5], [-5.01, 36.49]]]}}
    weather = {"type": "Feature", "geometry": {"type": "Point", "coordinates": [-5.0, 36.5]},
               "properties": {"t": 452628.0, "speed": 20.0, "direction": 270.0}}
    (tmp_path / "fires.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": [fire]}))
    (tmp_path / "weather.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": [weather]}))
    out = generate_spread(tmp_path / "fires.geojson", tmp_path / "weather.geojson", tmp_path / "spread.geojson")

    [feature] = out["features"]
    polygon = gpd.GeoSeries([shape(feature["geometry"])], crs="EPSG:4326")
    real_km2 = polygon.to_crs(polygon.estimate_utm_crs()).area.iloc[0] / 1e6
    assert feature["properties"]["area_km2"] == pytest.approx(real_km2, rel=0.01)
