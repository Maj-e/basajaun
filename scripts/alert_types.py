"""Typed alerts (W3-B8): wind, smoke and water contamination, next to the population alerts (W3-B1).

Every alert keeps the fields the alert panel already reads (fire_id, risk, since, pop_1km / 5km / 10km,
wind_toward_population, center, color) and adds `type` and a short `message`, plus type-specific fields:

    wind           strongest surface wind (10 m) during the fire's active hours >= thresholds
                   -> wind_kmh                                              (weather + fires)
    smoke          people in a ±30° sector downwind of the fire, as far as the wind carries the smoke
                   in smoke_transport_hours (capped by smoke_range_km), worst active hour; calm = no sector
                   -> smoke_people, wind_kmh                               (weather + population)
    contamination  fire or its 6 h spread over a vulnerable aquifer (ash leachate)
                   -> gw_body, gw_vulnerability                            (groundwater + fires / spread)

Thresholds: config.ALERT_THRESHOLDS.
"""
from __future__ import annotations

import math

import geopandas as gpd
import shapely
from rasterstats import zonal_stats
from shapely.geometry import Polygon, shape

try:
    from config import ALERT_THRESHOLDS
except ImportError:  # running outside the pipeline
    ALERT_THRESHOLDS = {}

DEFAULTS = {
    "wind_high_kmh": 30.0, "wind_critical_kmh": 45.0,
    "smoke_range_km": 25.0, "smoke_half_angle_deg": 30.0,
    "smoke_transport_hours": 2.0, "smoke_min_wind_kmh": 5.0,
    "smoke_min_people": 100, "smoke_medium_people": 1_000,
    "smoke_high_people": 10_000, "smoke_critical_people": 50_000,
}
RISK_COLORS = {"critical": "#a50f15", "high": "#d7301f", "medium": "#fc8d59", "low": "#fdcc8a"}
COMPASS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]


def thresholds(overrides: dict | None = None) -> dict:
    return {**DEFAULTS, **ALERT_THRESHOLDS, **(overrides or {})}


def compass(direction_deg: float) -> str:
    return COMPASS[int(((direction_deg % 360) + 22.5) // 45) % 8]


# --- wind at a fire ------------------------------------------------------------------

def index_weather(weather: dict | None) -> dict:
    """{(lon, lat): {hour: (speed_kmh, direction_from_deg)}} from weather.geojson."""
    out: dict = {}
    for f in (weather or {}).get("features", []):
        p = f.get("properties", {})
        if p.get("speed") is None or p.get("direction") is None or p.get("t") is None:
            continue
        lon, lat = f["geometry"]["coordinates"][:2]
        out.setdefault((lon, lat), {})[math.floor(p["t"])] = (float(p["speed"]), float(p["direction"]))
    return out


def winds_during(index: dict, lon: float, lat: float, t_start: float, t_end: float) -> list[tuple[int, float, float]]:
    """(hour, speed_kmh, direction_from_deg) at the nearest grid point for every hour the fire is active."""
    if not index:
        return []
    point = min(index, key=lambda p: (p[0] - lon) ** 2 + (p[1] - lat) ** 2)
    hours = index[point]
    first, last = math.floor(t_start), math.floor(t_end)
    active = [(h, *hours[h]) for h in range(first, last + 1) if h in hours]
    if not active and hours:  # fire shorter than the grid step: nearest hour
        h = min(hours, key=lambda x: abs(x - t_start))
        active = [(h, *hours[h])]
    return active


def wind_risk(speed_kmh: float, cfg: dict) -> str | None:
    if speed_kmh >= cfg["wind_critical_kmh"]:
        return "critical"
    if speed_kmh >= cfg["wind_high_kmh"]:
        return "high"
    return None


# --- smoke sector ------------------------------------------------------------------------

def smoke_sector(center_utm: shapely.Point, wind_from_deg: float, range_m: float, half_angle_deg: float) -> Polygon:
    """Wedge from the fire towards where the wind blows (downwind = from + 180°), in UTM metres."""
    downwind = (wind_from_deg + 180.0) % 360.0
    points = [(center_utm.x, center_utm.y)]
    steps = 16
    for i in range(steps + 1):
        bearing = math.radians(downwind - half_angle_deg + 2 * half_angle_deg * i / steps)
        points.append((center_utm.x + range_m * math.sin(bearing), center_utm.y + range_m * math.cos(bearing)))
    return Polygon(points)


def smoke_risk(people: float, cfg: dict) -> str | None:
    if people < cfg["smoke_min_people"]:
        return None
    if people >= cfg["smoke_critical_people"]:
        return "critical"
    if people >= cfg["smoke_high_people"]:
        return "high"
    if people >= cfg["smoke_medium_people"]:
        return "medium"
    return "low"


def people_in(polygons_utm: list, utm_crs, population_tif) -> list[int]:
    if not polygons_utm:
        return []
    import rasterio
    with rasterio.open(population_tif) as src:
        raster_crs = src.crs
    shapes = gpd.GeoSeries(polygons_utm, crs=utm_crs).to_crs(raster_crs)
    return [int(round(s["sum"] or 0)) for s in zonal_stats(shapes, str(population_tif), stats=["sum"])]


# --- build the typed alerts ----------------------------------------------------------------

def _base(population_alert: dict, alert_type: str, risk: str, since: str, message: str, **extra) -> dict:
    """Same population figures and position as the fire's population alert, so the current panel shows it."""
    return {
        "fire_id": population_alert["fire_id"], "type": alert_type, "risk": risk, "since": since,
        "pop_1km": population_alert["pop_1km"], "pop_5km": population_alert["pop_5km"],
        "pop_10km": population_alert["pop_10km"], "wind_toward_population": population_alert["wind_toward_population"],
        "center": population_alert["center"], "color": RISK_COLORS[risk], "message": message, **extra,
    }


def iso_hour(hour: int) -> str:
    from datetime import datetime, timezone
    return datetime.fromtimestamp(hour * 3600, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def typed_alerts(fires: dict, population_alerts: list[dict], population_tif, weather: dict | None = None,
                 spread: dict | None = None, groundwater: dict | None = None,
                 overrides: dict | None = None) -> list[dict]:
    """Wind, smoke and contamination alerts for the fires that already have a population alert."""
    cfg = thresholds(overrides)
    by_fire = {a["fire_id"]: a for a in population_alerts}
    features = [f for f in fires.get("features", []) if f.get("properties", {}).get("fire_id") in by_fire]
    if not features:
        return []
    gdf = gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")
    utm = gdf.estimate_utm_crs()
    centers_utm = gdf.to_crs(utm).geometry.centroid
    wind_index = index_weather(weather)
    out: list[dict] = []

    # Wind + smoke: per fire, over its active hours
    smoke_candidates = []  # (fire_id, hour, speed, direction, sector)
    for i, f in enumerate(features):
        p = f["properties"]
        pop = by_fire[p["fire_id"]]
        lon, lat = pop["center"]
        t_start = p.get("t_start", 0.0)
        t_end = p.get("t_end", t_start)
        winds = winds_during(wind_index, lon, lat, t_start, t_end)
        if not winds:
            continue
        hour, speed, direction = max(winds, key=lambda w: w[1])
        risk = wind_risk(speed, cfg)
        if risk:
            out.append(_base(pop, "wind", risk, iso_hour(hour),
                             f"Strong wind ({speed:.0f} km/h from {compass(direction)}) feeding the fire",
                             wind_kmh=round(speed, 1)))
        # One sector per distinct wind direction (rounded) to keep the raster sums few
        seen = set()
        for h, s, d in winds:
            if s < cfg["smoke_min_wind_kmh"]:
                continue  # calm: smoke has no downwind direction
            range_km = min(cfg["smoke_range_km"], s * cfg["smoke_transport_hours"])
            key = (round(d / 10), round(range_km))
            if key in seen:
                continue
            seen.add(key)
            sector = smoke_sector(centers_utm.iloc[i], d, range_km * 1000, cfg["smoke_half_angle_deg"])
            smoke_candidates.append((p["fire_id"], h, s, d, sector))

    people = people_in([c[4] for c in smoke_candidates], utm, population_tif) if population_tif else []
    worst: dict = {}
    for (fire_id, h, s, d, _), n in zip(smoke_candidates, people):
        if fire_id not in worst or n > worst[fire_id][0]:
            worst[fire_id] = (n, h, s, d)
    for fire_id, (n, h, s, d) in worst.items():
        risk = smoke_risk(n, cfg)
        if risk:
            out.append(_base(by_fire[fire_id], "smoke", risk, iso_hour(h),
                             f"Smoke toward ≈{n:,} people (wind {s:.0f} km/h from {compass(d)})",
                             smoke_people=n, wind_kmh=round(s, 1)))

    # Contamination: fire (gw_* from groundwater.py) or its 6 h spread over a vulnerable aquifer
    bodies = gpd.GeoDataFrame.from_features(groundwater["features"], crs="EPSG:4326") if groundwater and groundwater.get("features") else None
    spread_by_fire = {}
    for s in (spread or {}).get("features", []):
        if s["properties"].get("last") is False:
            continue  # an earlier snapshot of the fire (fire_history.py): only the final projection counts
        spread_by_fire.setdefault(s["properties"].get("fire_id"), []).append(shape(s["geometry"]))
    rank = {"high": 0, "medium": 1, "low": 2}
    for f in features:
        p = f["properties"]
        candidates = []
        if p.get("gw_vulnerability") in ("high", "medium"):
            candidates.append((p["gw_vulnerability"], p.get("gw_body"), "under the fire"))
        if bodies is not None and p["fire_id"] in spread_by_fire:
            area = shapely.union_all(spread_by_fire[p["fire_id"]])
            hit = bodies[bodies.intersects(area) & bodies["vulnerability"].isin(["high", "medium"])]
            for _, b in hit.iterrows():
                candidates.append((b["vulnerability"], b.get("name"), "in the 6 h spread"))
        if not candidates:
            continue
        level, body, where = min(candidates, key=lambda c: rank[c[0]])
        pop = by_fire[p["fire_id"]]
        out.append(_base(pop, "contamination", "high" if level == "high" else "medium", pop["since"],
                         f"Ash leachate risk: {level}-vulnerability aquifer {body or ''} {where}".replace("  ", " "),
                         gw_body=body, gw_vulnerability=level))
    return out
