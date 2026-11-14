import json
from datetime import datetime, timezone
import numpy as np
import requests
from config import BBOX, END_DATE, PROCESSED, START_DATE


def wind_style(speed_kmh: float) -> tuple[str, float]:
    """Return (hex_color, icon_size) based on wind speed in km/h."""
    if speed_kmh >= 45:
        return "#d7301f", 1.35
    if speed_kmh >= 30:
        return "#fc8d59", 1.15
    if speed_kmh >= 15:
        return "#fee08b", 0.95
    return "#91cf60", 0.75


def main() -> None:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    west, south, east, north = BBOX

    lons = np.linspace(west + (east - west) * 0.1, east - (east - west) * 0.1, 5)
    lats = np.linspace(south + (north - south) * 0.1, north - (north - south) * 0.1, 5)

    grid_lats = [f"{lat:.4f}" for lat in lats for _ in lons]
    grid_lons = [f"{lon:.4f}" for _ in lats for lon in lons]

    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": ",".join(grid_lats),
        "longitude": ",".join(grid_lons),
        "start_date": START_DATE,
        "end_date": END_DATE,
        "hourly": "wind_speed_10m,wind_direction_10m,temperature_2m,relative_humidity_2m,precipitation",
        "timezone": "UTC",
    }

    print("Fetching hourly meteorology (5x5 grid) from Open-Meteo...")
    resp = requests.get(url, params=params, timeout=60)
    resp.raise_for_status()
    payload = resp.json()

    if isinstance(payload, dict):
        payload = [payload]

    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    features = []

    for idx, cell in enumerate(payload):
        lat_c = round(float(grid_lats[idx]), 4)
        lon_c = round(float(grid_lons[idx]), 4)
        hourly = cell["hourly"]

        for i, ts_str in enumerate(hourly["time"]):
            speed = hourly["wind_speed_10m"][i]
            direction = hourly["wind_direction_10m"][i]
            temp = hourly["temperature_2m"][i]
            humidity = hourly["relative_humidity_2m"][i]
            rain = hourly["precipitation"][i]

            if speed is None or direction is None:
                continue

            dt = datetime.strptime(ts_str, "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc)
            t_hours = round((dt - epoch).total_seconds() / 3600.0, 2)
            rotation = round((float(direction) + 180.0) % 360.0, 1)
            color, size = wind_style(float(speed))

            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon_c, lat_c]},
                "properties": {
                    "datetime_utc": dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "t": t_hours,
                    "direction": round(float(direction), 1),
                    "speed": round(float(speed), 1),
                    "temperature": round(float(temp), 1) if temp is not None else None,
                    "humidity": round(float(humidity), 1) if humidity is not None else None,
                    "rain": round(float(rain), 1) if rain is not None else 0.0,
                    "rotation": rotation,
                    "size": size,
                    "color": color,
                    "radius": round(3.0 + min(float(speed) / 6.0, 10.0), 1),
                },
            })

    updated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    fc = {
        "type": "FeatureCollection",
        "updated": updated,
        "features": features,
    }

    output_path = PROCESSED / "weather.geojson"
    output_path.write_text(json.dumps(fc, separators=(",", ":")))
    size_kb = output_path.stat().st_size / 1024
    print(f"[SAVED] {output_path} ({len(features)} hourly records, {size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
