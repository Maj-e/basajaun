"""Export styled hotspots and the daily summary (W1-B3).

W0-B3 measured 271694 bytes, under 10 MiB, so this writes one file:
web/data/processed/hotspots.geojson. Normalization comes from W1-B1.
"""

import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from config import BBOX, END_DATE, PROCESSED, RAW, START_DATE
from harmonize import normalize_modis, normalize_viirs


def period_days(start: str, end: str) -> list[str]:
    cursor = date.fromisoformat(start)
    last = date.fromisoformat(end)
    days = []
    while cursor <= last:
        days.append(cursor.isoformat())
        cursor += timedelta(days=1)
    return days


def csvs_to_read(raw: Path, start: str, end: str) -> list[Path]:
    """Read every FIRMS CSV, but not both a full-period file and its 5-day chunks."""
    files = sorted(raw.glob("*.csv"))
    full_suffix = f"_{start}_{end}.csv"
    full = [path for path in files if path.name.endswith(full_suffix)]
    covered = [path.name[: -len(full_suffix)] for path in full]
    chosen = list(full)
    for path in files:
        if path in full:
            continue
        if any(path.name.startswith(prefix + "_") for prefix in covered):
            continue
        chosen.append(path)
    return chosen


def read_hotspots(paths: list[Path]) -> pd.DataFrame:
    frames = []
    for path in paths:
        raw = pd.read_csv(path)
        # Keep vegetation fires only: FIRMS type 2 = static land sources (industrial sites...)
        if "type" in raw.columns:
            raw = raw[raw["type"] == 0]
        if raw.empty:
            continue
        if path.name.startswith("MODIS"):
            frames.append(normalize_modis(raw))
        elif path.name.startswith("VIIRS"):
            frames.append(normalize_viirs(raw))
        else:
            print(f"[SKIP] {path.name} is not MODIS or VIIRS", file=sys.stderr)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def clip_to_bbox(df: pd.DataFrame, bbox: tuple[float, float, float, float]) -> pd.DataFrame:
    west, south, east, north = bbox
    if df.empty:
        return df
    inside = df["lon"].between(west, east) & df["lat"].between(south, north)
    return df.loc[inside].reset_index(drop=True)


def row_to_feature(row: pd.Series) -> dict:
    properties = {
        "id": row["id"],
        "sensor": row["sensor"],
        "satellite": row["satellite"],
        "timestamp_utc": row["timestamp_utc"],
        "date": row["date"],
        "t": float(row["t"]),
        "confidence": row["confidence"],
        "frp": None if pd.isna(row["frp"]) else float(row["frp"]),
        "brightness_k": float(row["brightness_k"]),
        "day_night": row["day_night"],
        "resolution_m": int(row["resolution_m"]),
        "detected_by": list(row["detected_by"]),
        "fire_id": None if pd.isna(row["fire_id"]) else row["fire_id"],
        "color": row["color"],
        "radius": float(row["radius"]),
        "border": row["border"],
    }
    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [float(row["lon"]), float(row["lat"])],
        },
        "properties": properties,
    }


def write_hotspots(df: pd.DataFrame, destination: Path, updated: str) -> None:
    features = [row_to_feature(row) for _, row in df.iterrows()]
    collection = {
        "type": "FeatureCollection",
        "updated_at": updated,
        "features": features,
    }
    destination.write_text(json.dumps(collection), encoding="utf-8")


def daily_summary(df: pd.DataFrame, days: list[str], updated: str) -> dict:
    summary = {"updated_at": updated}
    for day in days:
        group = df[df["date"] == day] if not df.empty else df
        hotspots = int(len(group))
        if hotspots == 0:
            summary[day] = {
                "hotspots": 0,
                "total_frp": 0.0,
                "modis": 0,
                "viirs": 0,
                "no_data": True,
            }
            continue
        summary[day] = {
            "hotspots": hotspots,
            "total_frp": round(float(group["frp"].fillna(0).sum()), 1),
            "modis": int((group["sensor"] == "MODIS").sum()),
            "viirs": int((group["sensor"] == "VIIRS").sum()),
            "no_data": False,
        }
    return summary


def main() -> None:
    paths = csvs_to_read(RAW, START_DATE, END_DATE)
    if not paths:
        print(f"Error: no CSV files in {RAW}", file=sys.stderr)
        raise SystemExit(1)

    hotspots = clip_to_bbox(read_hotspots(paths), BBOX)
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    PROCESSED.mkdir(parents=True, exist_ok=True)

    hotspots_path = PROCESSED / "hotspots.geojson"
    summary_path = PROCESSED / "daily_summary.json"
    write_hotspots(hotspots, hotspots_path, updated)
    summary = daily_summary(hotspots, period_days(START_DATE, END_DATE), updated)
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"[SAVED] {hotspots_path} ({len(hotspots)} hotspots)")
    print(f"[SAVED] {summary_path} ({len(summary) - 1} days)")


if __name__ == "__main__":
    main()
