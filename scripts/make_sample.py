import json
import random
from datetime import datetime, timezone
from pathlib import Path

try:
    from config import BBOX, SAMPLE
except ImportError:
    BBOX = (-72.0, -38.0, -70.0, -33.0)  # west, south, east, north
    SAMPLE = Path("web/data/sample")

CONFIDENCE_COLORS = {
    "high": "#d7301f",
    "medium": "#fc8d59",
    "low": "#fdcc8a",
}

RISK_COLORS = {
    "critical": "#d7301f",
    "high": "#fc8d59",
    "medium": "#fdcc8a",
    "low": "#fef0d9",
}


def calculate_radius(frp: float) -> float:
    """Interpolate circle radius between 3 and 16 px based on FRP (0 to 500 MW)."""
    clamped_frp = max(0.0, min(500.0, frp))
    if clamped_frp <= 50:
        return round(3.0 + (clamped_frp / 50.0) * 5.0, 1)
    return round(8.0 + ((clamped_frp - 50.0) / 450.0) * 8.0, 1)


def main():
    random.seed(42)
    SAMPLE.mkdir(parents=True, exist_ok=True)
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    west, south, east, north = BBOX
    demo_dates = ["2026-02-12", "2026-02-13", "2026-02-14"]
    confidence_levels = ["low", "medium", "high"]
    sensors = [
        ("MODIS", "Terra", 1000, "#ffffff"),
        ("MODIS", "Aqua", 1000, "#ffffff"),
        ("VIIRS", "S-NPP", 375, "#222222"),
        ("VIIRS", "NOAA-20", 375, "#222222"),
        ("VIIRS", "NOAA-21", 375, "#222222"),
    ]

    features = []
    daily_summary = {"updated_at": now_iso}

    for d in demo_dates:
        daily_summary[d] = {
            "hotspots": 0,
            "total_frp": 0.0,
            "modis": 0,
            "viirs": 0,
            "no_data": False,
        }

    # Generate 50 sample hotspots across 3 days
    for i in range(50):
        date_str = demo_dates[i % len(demo_dates)]
        hour = random.randint(0, 23)
        minute = random.randint(0, 59)
        dt = datetime.strptime(f"{date_str} {hour:02d}:{minute:02d}", "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        t_hours = round(dt.timestamp() / 3600.0, 1)

        sensor, satellite, res_m, border = random.choice(sensors)
        confidence = confidence_levels[i % 3]
        frp = round(random.uniform(5.0, 320.0), 1)
        brightness_k = round(random.uniform(310.0, 395.0), 1)
        day_night = "D" if 8 <= hour <= 20 else "N"

        lon = round(random.uniform(west + 0.3, east - 0.3), 4)
        lat = round(random.uniform(south + 0.3, north - 0.3), 4)

        sat_code = {"S-NPP": "N", "NOAA-20": "N20", "NOAA-21": "N21", "Terra": "T", "Aqua": "A"}[satellite]
        hotspot_id = f"{sensor}_{sat_code}_{date_str.replace('-', '')}_{hour:02d}{minute:02d}_{lat}_{lon}"

        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {
                "id": hotspot_id,
                "sensor": sensor,
                "satellite": satellite,
                "timestamp_utc": dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "date": date_str,
                "t": t_hours,
                "confidence": confidence,
                "frp": frp,
                "brightness_k": brightness_k,
                "day_night": day_night,
                "resolution_m": res_m,
                "detected_by": [sensor],
                "fire_id": None,
                "color": CONFIDENCE_COLORS[confidence],
                "radius": calculate_radius(frp),
                "border": border,
            },
        })

        day_stats = daily_summary[date_str]
        day_stats["hotspots"] += 1
        day_stats["total_frp"] = round(day_stats["total_frp"] + frp, 1)
        if sensor == "MODIS":
            day_stats["modis"] += 1
        else:
            day_stats["viirs"] += 1

    # Add a no-data day to test striped calendar cells in the UI
    daily_summary["2026-02-11"] = {
        "hotspots": 0,
        "total_frp": 0.0,
        "modis": 0,
        "viirs": 0,
        "no_data": True,
    }

    # 1. hotspots.geojson
    hotspots_geojson = {
        "type": "FeatureCollection",
        "updated_at": now_iso,
        "features": features,
    }
    (SAMPLE / "hotspots.geojson").write_text(json.dumps(hotspots_geojson, indent=2), encoding="utf-8")

    # 2. daily_summary.json
    (SAMPLE / "daily_summary.json").write_text(json.dumps(daily_summary, indent=2), encoding="utf-8")

    # 3. alerts.json (object with updated_at + alerts list, per contract)
    center_lon = round((west + east) / 2, 2)
    center_lat = round((south + north) / 2, 2)
    alerts = [
        {
            "fire_id": 12,
            "type": "population",
            "message": "≈23,400 people within 5 km · wind toward them",
            "risk": "critical",
            "color": RISK_COLORS["critical"],
            "since": "2026-02-12T07:42:00Z",
            "pop_1km": 1200,
            "pop_5km": 23400,
            "pop_10km": 51000,
            "wind_toward_population": True,
            "center": [center_lon, center_lat],
        },
        {
            "fire_id": 15,
            "type": "population",
            "message": "≈2,400 people within 5 km",
            "risk": "high",
            "color": RISK_COLORS["high"],
            "since": "2026-02-13T14:15:00Z",
            "pop_1km": 80,
            "pop_5km": 2400,
            "pop_10km": 9500,
            "wind_toward_population": False,
            "center": [round(center_lon + 0.25, 2), round(center_lat - 0.25, 2)],
        },
    ]
    # Typed alerts (W3-B8) on fire 12: same figures and position, one per type
    alerts += [
        {**alerts[0], "type": "smoke", "risk": "high", "color": RISK_COLORS["high"],
         "message": "Smoke toward ≈18,000 people (wind 28 km/h from SW)", "smoke_people": 18000, "wind_kmh": 28.0},
        {**alerts[0], "type": "wind", "risk": "high", "color": RISK_COLORS["high"],
         "message": "Strong wind (34 km/h from SW) feeding the fire", "wind_kmh": 34.0},
        {**alerts[0], "type": "contamination", "risk": "high", "color": RISK_COLORS["high"],
         "message": "Ash leachate risk: high-vulnerability aquifer under the fire",
         "gw_body": "Sample karst aquifer", "gw_vulnerability": "high"},
    ]
    alerts_doc = {"updated_at": now_iso, "alerts": alerts}
    (SAMPLE / "alerts.json").write_text(json.dumps(alerts_doc, indent=2), encoding="utf-8")

    # 4. manifest.json
    manifest = {
        "updated_at": now_iso,
        "layers": [
            {
                "id": "hotspots",
                "name": "Thermal Hotspots",
                "file": "sample/hotspots.geojson",
                "type": "circle",
                "temporal": True,
                "active": True,
                "popup": ["sensor", "satellite", "timestamp_utc", "confidence", "frp"],
                "legend": [
                    {"color": "#d7301f", "text": "High confidence"},
                    {"color": "#fc8d59", "text": "Medium confidence"},
                    {"color": "#fdcc8a", "text": "Low confidence"},
                ],
            }
        ],
    }
    (SAMPLE / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"✅ English sample files generated in {SAMPLE}/")


if __name__ == "__main__":
    main()