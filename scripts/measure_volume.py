import json
import os
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()
MAP_KEY = os.environ["FIRMS_MAP_KEY"]

BBOX = (-72.0, -38.0, -70.0, -33.0)  # west, south, east, north — from B2
START_DATE = date.fromisoformat("2026-02-01")
END_DATE = date.fromisoformat("2026-02-14")  # inclusive

# Codes confirmed with data_availability. Archive example:
SOURCES = [
    "MODIS_SP",
    "VIIRS_SNPP_SP",
    "VIIRS_NOAA20_SP",
    "VIIRS_NOAA21_SP",
]

RAW = Path("data/raw")
RAW.mkdir(parents=True, exist_ok=True)
MAX_DAYS = 5  # current Area API limit; raise to 10 only if a test returns CSV
BYTE_THRESHOLD = 10 * 1024 * 1024  # ~10 MB from the TODO


def date_windows(start: date, end: date, max_days: int):
    cursor = start
    while cursor <= end:
        day_count = min(max_days, (end - cursor).days + 1)
        yield cursor, day_count
        cursor += timedelta(days=day_count)


def download(source: str, start: date, day_count: int) -> Path:
    west, south, east, north = BBOX
    area = f"{west},{south},{east},{north}"
    url = (
        "https://firms.modaps.eosdis.nasa.gov/api/area/csv/"
        f"{MAP_KEY}/{source}/{area}/{day_count}/{start.isoformat()}"
    )
    destination = RAW / f"{source}_{start.isoformat()}_{day_count}d.csv"
    print(f"Requesting: {url}")
    response = requests.get(url, timeout=120)
    response.raise_for_status()
    body = response.text
    if not body.startswith("latitude,"):
        raise SystemExit(f"FIRMS did not return CSV for {source} {start}: {body[:200]}")
    destination.write_text(body, encoding="utf-8")
    return destination


def count_csv_rows(path: Path) -> int:
    df = pd.read_csv(path)
    return len(df)


def row_to_feature(row: pd.Series, source: str) -> dict:
    sensor = "MODIS" if source.startswith("MODIS") else "VIIRS"
    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [round(float(row["longitude"]), 4), round(float(row["latitude"]), 4)],
        },
        "properties": {
            "sensor": sensor,
            "satelite": str(row["satellite"]),
            "fecha": str(row["acq_date"]),
            # Aviso para W1-B3 (Front): El campo FRP puede venir como nulo (None/null), controlarlo al pintar el mapa.
            "frp": round(float(row["frp"]), 1) if pd.notna(row["frp"]) else None,
            "confianza": str(row["confidence"]),
            "color": "#d7301f",
            "radio": 6.0,
            "borde": "#222222",
        },
    }


def write_geojson(df: pd.DataFrame, source_per_row: list[str], destination: Path) -> int:
    features = [
        row_to_feature(row, source)
        for (_, row), source in zip(df.iterrows(), source_per_row)
    ]
    collection = {"type": "FeatureCollection", "features": features}
    destination.write_text(json.dumps(collection), encoding="utf-8")
    return destination.stat().st_size


def main() -> None:
    chunks = []
    counts = {}
    for source in SOURCES:
        frames = []
        for start, day_count in date_windows(START_DATE, END_DATE, MAX_DAYS):
            path = download(source, start, day_count)
            frames.append(pd.read_csv(path))
        df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        counts[source] = len(df)
        if len(df):
            df["_source"] = source
            chunks.append(df)

    combined = pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame()
    total = len(combined)
    size_bytes = 0
    if total:
        size_bytes = write_geojson(
            combined.drop(columns="_source"),
            combined["_source"].tolist(),
            RAW / "focos_bruto.geojson",
        )

    daily_sizes = {}
    if total:
        for day, group in combined.groupby("acq_date"):
            temp_file = RAW / f"temp_{day}.geojson"
            day_size = write_geojson(
                group.drop(columns="_source"),
                group["_source"].tolist(),
                temp_file,
            )
            daily_sizes[day] = day_size
            temp_file.unlink()  # remove the temp file so data/raw stays clean

        heaviest_day = max(daily_sizes, key=daily_sizes.get)
        print(f"Heaviest day: {heaviest_day} with {daily_sizes[heaviest_day]} bytes")

    decision = "one file per day" if size_bytes > BYTE_THRESHOLD else "one single file"
    print("hotspots", total, counts)
    print("bytes", size_bytes, decision)


if __name__ == "__main__":
    main()
