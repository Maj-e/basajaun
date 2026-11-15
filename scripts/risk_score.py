"""Combined risk score + evacuation estimate per fire (W3-B11).

Four factors, 0-2 points each (thresholds: config.RISK_SCORE):
    F  fire           1 for any fire, 2 when intense (frp_max or number of hotspots)
    P  people         people within 5 km (population alert)
    S  smoke          smoke toward people (smoke alert, W3-B8)
    W  strong wind    strongest surface wind (10 m) during the fire's active hours

Level from the total (0-8), with floors for the combinations that matter most:
    smoke + people            -> at least medium
    fire + strong wind        -> at least high
    all four (P + S + W, F)   -> extreme

Evacuation: people in fire + 1 km + 6 h spread (`evacuate_people`); the other people within 5 km
are on warning (`warn_people`).

Writes (episode folder):
    fires.geojson (in place)  risk_score, risk_level, risk_factors, evacuate_people, warn_people
    fire_risk.geojson         fire polygons coloured by risk level
    evacuation.geojson        evacuation zone per fire
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import rasterio
import shapely
from rasterstats import zonal_stats
from shapely.geometry import shape

from alert_types import index_weather, winds_during
from fire_history import snapshots
from spread import _parse_iso_hours

try:
    from config import PROCESSED, RISK_SCORE
except ImportError:  # running outside the pipeline
    PROCESSED, RISK_SCORE = Path("web/data/processed"), {}

DEFAULTS = {
    "fire_intense_frp_mw": 100.0, "fire_intense_hotspots": 20,
    "people_some": 1_000, "people_many": 10_000, "smoke_many": 10_000,
    "wind_strong_kmh": 20.0, "wind_very_strong_kmh": 30.0,
    "evacuate_buffer_km": 1.0, "warn_radius_km": 5.0,
}
LEVELS = ["low", "medium", "high", "extreme"]
LEVEL_STYLE = {
    "low":     {"color": "#fdcc8a", "opacity": 0.35},
    "medium":  {"color": "#fc8d59", "opacity": 0.45},
    "high":    {"color": "#d7301f", "opacity": 0.55},
    "extreme": {"color": "#67000d", "opacity": 0.65},
}
EVACUATION_STYLE = {"color": "#e31a1c", "opacity": 0.18}
FACTOR_NAMES = {"F": "fire", "P": "people", "S": "smoke", "W": "strong wind"}


def cfg(overrides: dict | None = None) -> dict:
    return {**DEFAULTS, **RISK_SCORE, **(overrides or {})}


def factor_points(frp_max: float, n_hotspots: int, pop_5km: float, smoke_people: float | None,
                  max_wind_kmh: float | None, c: dict) -> dict[str, int]:
    fire = 2 if (frp_max >= c["fire_intense_frp_mw"] or n_hotspots >= c["fire_intense_hotspots"]) else 1
    people = 2 if pop_5km >= c["people_many"] else 1 if pop_5km >= c["people_some"] else 0
    smoke = 0 if not smoke_people else (2 if smoke_people >= c["smoke_many"] else 1)
    wind = 0
    if max_wind_kmh is not None:
        wind = 2 if max_wind_kmh >= c["wind_very_strong_kmh"] else 1 if max_wind_kmh >= c["wind_strong_kmh"] else 0
    return {"F": fire, "P": people, "S": smoke, "W": wind}


def risk_level(points: dict[str, int]) -> str:
    """Level from the 0-8 total, raised by the combinations: P+S >= medium, F+W >= high, all four = extreme."""
    total = sum(points.values())
    level = "low" if total <= 2 else "medium" if total <= 4 else "high" if total <= 6 else "extreme"
    present = {k for k, v in points.items() if v > 0}
    floor = "low"
    if {"P", "S"} <= present:
        floor = "medium"
    if {"F", "W"} <= present:
        floor = "high"
    if {"F", "P", "S", "W"} <= present:
        floor = "extreme"
    return max(level, floor, key=LEVELS.index)


def score_percent(points: dict[str, int]) -> int:
    return round(100 * sum(points.values()) / 8)


def people_in(zones: gpd.GeoSeries, population_tif: Path) -> list[int]:
    if zones.empty:
        return []
    with rasterio.open(population_tif) as src:
        zones = zones.to_crs(src.crs)
    return [int(round(s["sum"] or 0)) for s in zonal_stats(zones, str(population_tif), stats=["sum"])]


def _hours(ts: str | None) -> float | None:
    return _parse_iso_hours(ts) if ts else None


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run(processed: Path = PROCESSED, overrides: dict | None = None) -> bool:
    c = cfg(overrides)
    paths = {name: processed / f"{name}.geojson" for name in ("fires", "spread", "weather")}
    population_tif, alerts_path = processed / "population.tif", processed / "alerts.json"
    for path, task in ((paths["fires"], "W2-B2"), (population_tif, "W3-B3"), (alerts_path, "W3-B1")):
        if not path.exists():
            print(f"[SKIP] {path} not found yet (waiting for {task}): no risk score.")
            return False

    fires_fc = json.loads(paths["fires"].read_text(encoding="utf-8"))
    if not fires_fc.get("features"):
        print("[SKIP] no fires: no risk score.")
        return False
    alerts = json.loads(alerts_path.read_text(encoding="utf-8"))["alerts"]
    population = {a["fire_id"]: a for a in alerts if a["type"] == "population"}
    smoke = {a["fire_id"]: (a["smoke_people"], _hours(a.get("since"))) for a in alerts if a["type"] == "smoke"}
    weather = json.loads(paths["weather"].read_text(encoding="utf-8")) if paths["weather"].exists() else None
    wind_index = index_weather(weather)
    # Spread projections per fire and per snapshot start (the final one is flagged `last`)
    spread = {}
    if paths["spread"].exists():
        for s in json.loads(paths["spread"].read_text(encoding="utf-8")).get("features", []):
            sp = s["properties"]
            spread.setdefault((sp.get("fire_id"), sp.get("t_start") if "t_start" in sp else None), []).append(shape(s["geometry"]))
    hotspots_path = processed / "hotspots.geojson"
    hotspots_fc = json.loads(hotspots_path.read_text(encoding="utf-8")) if hotspots_path.exists() else None
    history = snapshots(fires_fc, hotspots_fc)

    utm = gpd.GeoSeries([shape(f["geometry"]) for f in fires_fc["features"]], crs="EPSG:4326").estimate_utm_crs()

    def to_utm(geom):
        return gpd.GeoSeries([geom], crs="EPSG:4326").to_crs(utm).iloc[0]

    # One row per fire snapshot. Evacuation zone = fire + buffer + 6 h spread; warning zone = within the warning radius
    rows = []
    for i, feature in enumerate(fires_fc["features"]):
        fid = feature["properties"].get("fire_id")
        for snap in history[int(fid)]:
            final = snap["t_until"] is None
            geom = to_utm(snap["geometry"])
            parts = [geom.buffer(c["evacuate_buffer_km"] * 1000)]
            parts += [to_utm(g) for g in spread.get((fid, snap["t_from"]), spread.get((fid, None), []))]
            evac = shapely.union_all(parts)
            rows.append({"i": i, "fid": fid, "snap": snap, "final": final, "geom": geom, "evac": evac,
                         "warn": shapely.union_all([geom.buffer(c["warn_radius_km"] * 1000), evac]),
                         "near": geom.buffer(c["warn_radius_km"] * 1000)})
    evacuate = people_in(gpd.GeoSeries([r["evac"] for r in rows], crs=utm), population_tif)
    warn_total = people_in(gpd.GeoSeries([r["warn"] for r in rows], crs=utm), population_tif)
    # People within 5 km of the fire as it was then; the final snapshot keeps the figure of the population alert
    near_people = people_in(gpd.GeoSeries([r["near"] for r in rows], crs=utm), population_tif)

    updated_at = utc_now()
    risk_features, evac_features = [], []
    evac_wgs84 = gpd.GeoSeries([r["evac"] for r in rows], crs=utm).to_crs("EPSG:4326")
    for n, row in enumerate(rows):
        feature, snap = fires_fc["features"][row["i"]], row["snap"]
        p = feature["properties"]
        fid = row["fid"]
        pop = population.get(fid, {})
        t_from = snap["t_from"]
        smoke_people, smoke_since = smoke.get(fid, (None, None))
        if not row["final"] and (smoke_since is None or smoke_since > t_from):
            smoke_people = None  # the smoke alert had not been raised yet
        centroid = snap["geometry"].centroid.coords[0]
        t_to = p.get("t_end", p.get("t_start", 0.0)) if row["final"] else t_from
        winds = winds_during(wind_index, *centroid, p.get("t_start", 0.0), t_to) if wind_index else []
        max_wind = max((w[1] for w in winds), default=None)
        people_5km = float(pop.get("pop_5km", 0)) if row["final"] else float(near_people[n])
        points = factor_points(snap["frp_max"], snap["n_hotspots"], people_5km, smoke_people, max_wind, c)
        level = risk_level(points)
        values = {
            "risk_score": score_percent(points),
            "risk_level": level,
            "risk_factors": [FACTOR_NAMES[k] for k, v in points.items() if v > 0],
            "evacuate_people": evacuate[n],
            "warn_people": max(0, warn_total[n] - evacuate[n]),
        }
        when = {"t_start": t_from, "t_until": snap["active_until"] if row["final"] else snap["t_until"], "last": row["final"]}
        if row["final"]:
            p.update(values)
        light = shapely.set_precision(snap["geometry"].simplify(0.0002), 1e-4)  # ~20 m: display only
        risk_features.append({"type": "Feature", "geometry": shapely.geometry.mapping(light),
                              "properties": {"fire_id": fid, **values, **LEVEL_STYLE[level], **when}})
        geom = shapely.set_precision(evac_wgs84.iloc[n].simplify(0.0005), 1e-4)
        evac_features.append({"type": "Feature", "geometry": shapely.geometry.mapping(geom),
                              "properties": {"fire_id": fid, "evacuate_people": evacuate[n],
                                             "warn_people": values["warn_people"], **EVACUATION_STYLE, **when}})
    final_rows = [n for n, r in enumerate(rows) if r["final"]]
    evacuate = [evacuate[n] for n in final_rows]
    risk_final = [risk_features[n] for n in final_rows]

    fires_fc["updated_at"] = updated_at
    paths["fires"].write_text(json.dumps(fires_fc, separators=(",", ":")), encoding="utf-8")
    for name, features in (("fire_risk", risk_features), ("evacuation", evac_features)):
        out = processed / f"{name}.geojson"
        out.write_text(json.dumps({"type": "FeatureCollection", "updated_at": updated_at, "features": features},
                                  separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    levels = {lvl: sum(1 for f in risk_final if f["properties"]["risk_level"] == lvl) for lvl in LEVELS}
    biggest = max(evacuate, default=0)
    print(f"[SAVED] risk score for {len(risk_final)} fires ({len(risk_features)} snapshots) {levels} · largest evacuation ≈{biggest:,} people")
    return True


def main() -> None:
    run()


if __name__ == "__main__":
    main()
