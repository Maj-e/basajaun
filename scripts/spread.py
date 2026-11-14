"""W5-B2: Project 6-hour wildfire spread ellipses from wind (weather.geojson) and optional slope."""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from pyproj import Transformer
from shapely import affinity
from shapely.geometry import Point, mapping, shape
import shapely

from config import PROCESSED

FIRES_PATH = PROCESSED / "fires.geojson"
WEATHER_PATH = PROCESSED / "weather.geojson"
SPREAD_PATH = PROCESSED / "spread.geojson"

WGS84_CRS = "EPSG:4326"


def utm_crs_for(lon: float, lat: float) -> str:
    """UTM zone of a point (EPSG:326xx north, 327xx south): distances and areas in true metres there.

    A fixed zone (the old EPSG:32719, Chile) distorts ellipses and areas for fires far from it,
    e.g. Sierra Bermeja (zone 30N) came out about twice its real area.
    """
    zone = min(60, max(1, int((lon + 180.0) // 6.0) + 1))
    return f"EPSG:{32600 + zone if lat >= 0 else 32700 + zone}"


_TRANSFORMERS: dict[str, tuple] = {}


def transformers_for(lon: float, lat: float) -> tuple:
    """(to_utm, to_wgs84) transform functions for the point's UTM zone, cached per zone."""
    crs = utm_crs_for(lon, lat)
    if crs not in _TRANSFORMERS:
        _TRANSFORMERS[crs] = (Transformer.from_crs(WGS84_CRS, crs, always_xy=True).transform,
                              Transformer.from_crs(crs, WGS84_CRS, always_xy=True).transform)
    return _TRANSFORMERS[crs]

DEFAULT_HORIZON_HOURS = 6.0


def _parse_iso_hours(ts: str) -> float:
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return dt.timestamp() / 3600.0


def _nearest_wind(lon: float, lat: float, target_t: float, weather_features: list[dict]) -> tuple[float, float]:
    """Return (speed_kmh, direction_from_deg) from the nearest weather grid point and hour."""
    if not weather_features:
        return 10.0, 225.0

    best_dist2 = float("inf")
    best_dt = float("inf")
    best_speed = 10.0
    best_dir = 225.0

    for feat in weather_features:
        coords = feat.get("geometry", {}).get("coordinates", [])
        if len(coords) < 2:
            continue
        props = feat.get("properties", {})
        speed = props.get("speed")
        direction = props.get("direction")
        t_val = props.get("t")
        if speed is None or direction is None or t_val is None:
            continue

        dist2 = (coords[0] - lon) ** 2 + (coords[1] - lat) ** 2
        dt = abs(float(t_val) - target_t)
        if (dist2 < best_dist2 - 1e-9) or (abs(dist2 - best_dist2) <= 1e-9 and dt < best_dt):
            best_dist2 = dist2
            best_dt = dt
            best_speed = float(speed)
            best_dir = float(direction)

    return best_speed, best_dir


def build_spread_ellipse_utm(
    fire_geom_utm,
    wind_speed_kmh: float,
    wind_from_deg: float,
    frp_max: float = 20.0,
    slope_deg: float = 0.0,
    horizon_hours: float = DEFAULT_HORIZON_HOURS,
):
    """Build a 6-hour projected spread polygon in UTM meters oriented downwind."""
    centroid = fire_geom_utm.centroid

    # Base rate of spread (km/h) driven by wind speed, fire intensity (FRP) and optional terrain slope
    intensity_factor = min(1.8, max(0.8, 0.75 + math.log10(max(frp_max, 1.0)) * 0.35))
    slope_factor = math.exp(0.053 * max(0.0, min(slope_deg, 45.0)))
    ros_head_kmh = (0.18 + 0.032 * max(0.0, wind_speed_kmh)) * intensity_factor * slope_factor

    head_dist_m = ros_head_kmh * horizon_hours * 1000.0
    # Length-to-breadth ratio increases with wind speed (Anderson / Alexander approximation)
    lb_ratio = min(4.0, max(1.15, 1.0 + 0.055 * max(0.0, wind_speed_kmh)))
    back_dist_m = head_dist_m / (lb_ratio ** 1.5)

    semi_major_m = 0.5 * (head_dist_m + back_dist_m)
    semi_minor_m = semi_major_m / lb_ratio
    center_shift_m = 0.5 * (head_dist_m - back_dist_m)

    # Unit circle scaled to ellipse along +Y (North), shifted downwind along +Y, then rotated clockwise
    ellipse = Point(0.0, 0.0).buffer(1.0, quad_segs=32)
    ellipse = affinity.scale(ellipse, xfact=semi_minor_m, yfact=semi_major_m, origin=(0.0, 0.0))
    ellipse = affinity.translate(ellipse, xoff=0.0, yoff=center_shift_m)

    wind_to_deg = (wind_from_deg + 180.0) % 360.0
    # shapely.affinity.rotate uses counter-clockwise angle from +X; azimuth clockwise from +Y is -wind_to_deg
    ellipse = affinity.rotate(ellipse, -wind_to_deg, origin=(0.0, 0.0))
    ellipse = affinity.translate(ellipse, xoff=centroid.x, yoff=centroid.y)

    projected = fire_geom_utm.union(ellipse)
    return projected, round(head_dist_m / 1000.0, 2), round(wind_to_deg, 1)


def generate_spread(
    fires_path: Path = FIRES_PATH,
    weather_path: Path = WEATHER_PATH,
    out_path: Path = SPREAD_PATH,
    horizon_hours: float = DEFAULT_HORIZON_HOURS,
) -> dict:
    fires_fc = json.loads(fires_path.read_text(encoding="utf-8"))
    weather_features: list[dict] = []
    if weather_path.is_file():
        weather_fc = json.loads(weather_path.read_text(encoding="utf-8"))
        weather_features = weather_fc.get("features", [])

    spread_features: list[dict] = []
    for feat in fires_fc.get("features", []):
        props = feat.get("properties", {})
        geom_wgs = shape(feat["geometry"])
        centroid_wgs = geom_wgs.centroid

        end_ts = props.get("end") or props.get("start") or "2026-02-14T00:00:00Z"
        target_t = _parse_iso_hours(end_ts)
        wind_speed, wind_from = _nearest_wind(centroid_wgs.x, centroid_wgs.y, target_t, weather_features)

        frp_max = float(props.get("frp_max", 20.0))
        slope_deg = float(props.get("slope_deg", 0.0))

        to_utm, to_wgs84 = transformers_for(centroid_wgs.x, centroid_wgs.y)
        geom_utm = shapely.transform(geom_wgs, lambda coords: np.column_stack(to_utm(coords[:, 0], coords[:, 1])))
        proj_utm, spread_km, wind_to_deg = build_spread_ellipse_utm(
            geom_utm,
            wind_speed_kmh=wind_speed,
            wind_from_deg=wind_from,
            frp_max=frp_max,
            slope_deg=slope_deg,
            horizon_hours=horizon_hours,
        )
        proj_wgs = shapely.transform(proj_utm, lambda coords: np.column_stack(to_wgs84(coords[:, 0], coords[:, 1])))
        area_km2 = round(proj_utm.area / 1_000_000.0, 2)

        spread_features.append({
            "type": "Feature",
            "geometry": mapping(proj_wgs),
            "properties": {
                "fire_id": props.get("fire_id"),
                "horizon_hours": int(horizon_hours),
                "wind_speed_kmh": round(wind_speed, 1),
                "wind_to_deg": wind_to_deg,
                "slope_deg": round(slope_deg, 1),
                "spread_km": spread_km,
                "area_km2": area_km2,
                "color": "#756bb1",
                "opacity": 0.25,
            },
        })

    out_fc = {
        "type": "FeatureCollection",
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "features": spread_features,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out_fc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[SAVED] {out_path} ({len(spread_features)} {int(horizon_hours)}h spread projections)")
    return out_fc


def main() -> None:
    generate_spread()


if __name__ == "__main__":
    main()
