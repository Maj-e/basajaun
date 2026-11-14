import json
import math
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.mask import mask as rasterio_mask
from rasterstats import zonal_stats
from shapely.geometry import Point, mapping

try:
    from config import PROCESSED
except ImportError:
    PROCESSED = Path("web/data/processed")

RISK_LEVELS = ["low", "medium", "high", "critical"]

RISK_RANK = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
}

RISK_COLORS = {
    "critical": "#a50f15",
    "high": "#d7301f",
    "medium": "#fc8d59",
    "low": "#fdcc8a",
}

# Default risk thresholds (can be overridden in scripts/config.py)
DEFAULT_THRESHOLDS = {
    "crit_pop_1km": 1000,
    "crit_pop_5km": 10000,
    "crit_frp_max": 100.0,
    "high_pop_5km": 1000,
    "med_pop_10km": 100,
    "wind_min_speed_kmh": 20.0,
    "wind_max_angle_deg": 45.0,
}


def classify_base_risk(
    pop_1km: int,
    pop_5km: int,
    pop_10km: int,
    frp_max: float,
    thresholds: dict | None = None,
) -> str:
    """Classify baseline risk level from exposed population buffers and max FRP."""
    cfg = {**DEFAULT_THRESHOLDS, **(thresholds or {})}

    if pop_1km >= cfg["crit_pop_1km"] or (
        pop_5km >= cfg["crit_pop_5km"] and frp_max >= cfg["crit_frp_max"]
    ):
        return "critical"
    if pop_5km >= cfg["high_pop_5km"]:
        return "high"
    if pop_10km >= cfg["med_pop_10km"]:
        return "medium"
    return "low"


def upgrade_risk_one_level(risk: str) -> str:
    """Escalate risk by one tier (capped at 'critical')."""
    idx = RISK_LEVELS.index(risk)
    return RISK_LEVELS[min(idx + 1, len(RISK_LEVELS) - 1)]


def compute_bearing_deg(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Compute initial compass bearing in degrees [0, 360) from point 1 to point 2."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_lambda = math.radians(lon2 - lon1)

    y = math.sin(d_lambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(d_lambda)
    bearing = math.degrees(math.atan2(y, x))
    return (bearing + 360.0) % 360.0


def angular_difference_deg(angle_a: float, angle_b: float) -> float:
    """Return smallest angular difference in degrees [0, 180]."""
    return abs((angle_a - angle_b + 180.0) % 360.0 - 180.0)


def is_wind_blowing_toward_target(
    fire_lon: float,
    fire_lat: float,
    target_lon: float,
    target_lat: float,
    wind_from_deg: float,
    wind_speed_kmh: float,
    min_speed_kmh: float = 20.0,
    max_angle_deg: float = 45.0,
) -> bool:
    """
    Check if wind speed >= min_speed_kmh and wind direction blows within max_angle_deg
    toward the target populated cell.
    Meteorological wind direction is where wind comes FROM, so downwind is (wind_from_deg + 180) % 360.
    """
    if wind_speed_kmh < min_speed_kmh:
        return False

    # Same coordinates -> fire is already on top of the peak population pixel
    if math.isclose(fire_lon, target_lon, abs_tol=1e-5) and math.isclose(
        fire_lat, target_lat, abs_tol=1e-5
    ):
        return True

    bearing_to_target = compute_bearing_deg(fire_lon, fire_lat, target_lon, target_lat)
    wind_toward_deg = (wind_from_deg + 180.0) % 360.0
    diff = angular_difference_deg(bearing_to_target, wind_toward_deg)
    return diff < max_angle_deg


def _find_peak_population_coords(
    src: rasterio.DatasetReader,
    buffer_10km_wgs84,
) -> tuple[float, float] | None:
    """Return (lon, lat) of the highest-population pixel within the 10 km buffer."""
    geom_raster = (
        gpd.GeoSeries([buffer_10km_wgs84], crs="EPSG:4326")
        .to_crs(src.crs)
        .iloc[0]
    )

    try:
        out_image, out_transform = rasterio_mask(
            src, [mapping(geom_raster)], crop=True, filled=False
        )
    except ValueError:
        return None

    band = out_image[0]
    if np.ma.isMaskedArray(band):
        data = band.filled(0.0)
    else:
        data = np.nan_to_num(band, nan=0.0)

    if data.size == 0 or float(np.max(data)) <= 0.0:
        return None

    max_row, max_col = np.unravel_index(int(np.argmax(data)), data.shape)
    x_coord, y_coord = rasterio.transform.xy(out_transform, max_row, max_col)

    if str(src.crs) != "EPSG:4326":
        pt = gpd.GeoSeries([Point(x_coord, y_coord)], crs=src.crs).to_crs("EPSG:4326").iloc[0]
        return float(pt.x), float(pt.y)

    return float(x_coord), float(y_coord)


def _extract_wind_at_fire(
    meteo_features: list[dict],
    fire_lon: float,
    fire_lat: float,
    since_iso: str,
) -> tuple[float, float] | None:
    """
    Find nearest meteo grid point around the fire's start hour.
    Reads weather.py's 'speed' / 'direction' keys; older names ('wind_speed' / 'wind_direction',
    'vel' / 'dir') are still accepted.
    """
    if not meteo_features:
        return None

    dt = datetime.fromisoformat(since_iso.replace("Z", "+00:00"))
    target_t = dt.timestamp() / 3600.0

    best_wind = None
    best_score = float("inf")

    for feat in meteo_features:
        props = feat.get("properties", {})
        coords = feat.get("geometry", {}).get("coordinates", [])
        if len(coords) < 2:
            continue

        vel = next((props[k] for k in ("speed", "wind_speed", "vel") if props.get(k) is not None), None)
        direction = next((props[k] for k in ("direction", "wind_direction", "dir") if props.get(k) is not None), None)
        if vel is None or direction is None:
            continue

        lon, lat = float(coords[0]), float(coords[1])
        dist_sq = (lon - fire_lon) ** 2 + (lat - fire_lat) ** 2

        t_val = props.get("t")
        time_penalty = abs(float(t_val) - target_t) * 0.01 if t_val is not None else 0.0
        score = dist_sq + time_penalty

        if score < best_score:
            best_score = score
            best_wind = (float(direction), float(vel))

    return best_wind


def _sum_population_for_buffers(
    buffers_utm: gpd.GeoSeries,
    raster_path: Path,
    raster_crs,
) -> list[int]:
    """Run zonal_stats sum on a GeoSeries of UTM polygons reprojected to raster_crs."""
    buffers_raster = buffers_utm.to_crs(raster_crs)
    stats = zonal_stats(buffers_raster, str(raster_path), stats=["sum"], all_touched=False)
    return [int(round(item["sum"] or 0)) for item in stats]


def compute_alerts(
    fires_geojson: dict,
    population_tif: Path,
    meteo_geojson: dict | None = None,
    thresholds: dict | None = None,
) -> dict:
    """
    Compute population exposure (1, 5, 10 km), wind risk escalation, and return
    the contract-compliant alerts object sorted from most to least severe.
    """
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    features = fires_geojson.get("features", [])
    if not features:
        return {"updated_at": now_iso, "alerts": []}

    gdf = gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")
    utm_crs = gdf.estimate_utm_crs()
    gdf_utm = gdf.to_crs(utm_crs)

    # Compute accurate centroids in UTM and project back to WGS84
    centroids_wgs84 = gdf_utm.geometry.centroid.to_crs("EPSG:4326")

    # Create 1 km, 5 km, and 10 km buffers in meters
    buf_1km_utm = gdf_utm.geometry.buffer(1000.0)
    buf_5km_utm = gdf_utm.geometry.buffer(5000.0)
    buf_10km_utm = gdf_utm.geometry.buffer(10000.0)
    buf_10km_wgs84 = buf_10km_utm.to_crs("EPSG:4326")

    with rasterio.open(population_tif) as src:
        raster_crs = src.crs
        pop_1km_list = _sum_population_for_buffers(buf_1km_utm, population_tif, raster_crs)
        pop_5km_list = _sum_population_for_buffers(buf_5km_utm, population_tif, raster_crs)
        pop_10km_list = _sum_population_for_buffers(buf_10km_utm, population_tif, raster_crs)

        peak_pop_coords = [
            _find_peak_population_coords(src, geom_10km) for geom_10km in buf_10km_wgs84
        ]

    meteo_features = (meteo_geojson or {}).get("features", [])
    cfg = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    alerts = []

    for idx, feat in enumerate(features):
        props = feat.get("properties", {})
        raw_fire_id = props.get("fire_id", props.get("incendio_id", idx + 1))
        fire_id = int(raw_fire_id) if isinstance(raw_fire_id, (int, float, np.integer)) else raw_fire_id

        since = (
            props.get("since")
            or props.get("start")
            or props.get("inicio")
            or props.get("timestamp_utc")
            or now_iso
        )
        frp_max = float(props.get("frp_max", props.get("frp", 0.0)) or 0.0)

        pop_1km = pop_1km_list[idx]
        pop_5km = pop_5km_list[idx]
        pop_10km = pop_10km_list[idx]

        center_pt = centroids_wgs84.iloc[idx]
        center_lon = round(float(center_pt.x), 4)
        center_lat = round(float(center_pt.y), 4)

        risk = classify_base_risk(pop_1km, pop_5km, pop_10km, frp_max, cfg)
        wind_toward_pop = False

        peak_coords = peak_pop_coords[idx]
        if peak_coords is not None and meteo_features:
            wind = _extract_wind_at_fire(meteo_features, center_lon, center_lat, since)
            if wind is not None:
                wind_from_deg, wind_speed_kmh = wind
                if is_wind_blowing_toward_target(
                    fire_lon=center_lon,
                    fire_lat=center_lat,
                    target_lon=peak_coords[0],
                    target_lat=peak_coords[1],
                    wind_from_deg=wind_from_deg,
                    wind_speed_kmh=wind_speed_kmh,
                    min_speed_kmh=cfg["wind_min_speed_kmh"],
                    max_angle_deg=cfg["wind_max_angle_deg"],
                ):
                    wind_toward_pop = True
                    risk = upgrade_risk_one_level(risk)

        alerts.append({
            "fire_id": fire_id,
            "risk": risk,
            "since": since,
            "pop_1km": pop_1km,
            "pop_5km": pop_5km,
            "pop_10km": pop_10km,
            "wind_toward_population": wind_toward_pop,
            "center": [center_lon, center_lat],
            "color": RISK_COLORS[risk],
        })

    # Sort from most to least severe, breaking ties by 1 km and 5 km population
    alerts.sort(key=lambda a: (RISK_RANK[a["risk"]], -a["pop_1km"], -a["pop_5km"]))

    return {
        "updated_at": now_iso,
        "alerts": alerts,
    }


def run_exposure(data_dir: Path = PROCESSED) -> Path | None:
    """Load fires, population raster, and optional weather data from data_dir and write alerts.json.

    Returns None (and writes nothing) while an input from an earlier step is still missing,
    so `make data` keeps going.
    """
    fires_path = data_dir / "fires.geojson"
    pop_path = data_dir / "population.tif"
    meteo_path = data_dir / "weather.geojson"  # W3-B2
    alerts_path = data_dir / "alerts.json"

    for path, task in ((fires_path, "W2-B2"), (pop_path, "W3-B3")):
        if not path.exists():
            print(f"[SKIP] {path} not found yet (waiting for {task}): no alerts generated.")
            return None

    fires_data = json.loads(fires_path.read_text(encoding="utf-8"))
    meteo_data = (
        json.loads(meteo_path.read_text(encoding="utf-8"))
        if meteo_path.exists()
        else None
    )

    result = compute_alerts(fires_data, pop_path, meteo_data)
    alerts_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    counts = {lvl: sum(1 for a in result["alerts"] if a["risk"] == lvl) for lvl in RISK_LEVELS}
    print(f"Alerts generated ({len(result['alerts'])} total) -> {alerts_path} | breakdown: {counts}")
    return alerts_path


def main() -> None:
    run_exposure(PROCESSED)


if __name__ == "__main__":
    main()