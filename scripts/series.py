"""Hourly time series of hotspots (W2-B3): active hotspots and total FRP per hour.

Output: web/data/processed/hourly_series.json
    {"updated_at": "...", "series": [{"t": 491950, "count": 12, "total_frp": 340.5}, ...]}
`t` is the whole hour (hours since 1970); every hour of the period is present, zero-filled.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from config import PROCESSED


def build_series(features: list[dict]) -> list[dict]:
    records = [
        {"t": feature["properties"]["t"],
         # If FRP is null, count it as 0.0 so the sum still works
         "frp": feature["properties"].get("frp") or 0.0}
        for feature in features
    ]
    if not records:
        return []
    df = pd.DataFrame(records)
    # t has decimals (e.g. 491683.88 = 52 min past the hour): bucket each hotspot into its hour
    df["t"] = np.floor(df["t"].astype(float)).astype(int)

    grouped = df.groupby("t").agg(count=("t", "size"), total_frp=("frp", "sum"))
    # Every hour of the period, with 0 where there is nothing
    complete = grouped.reindex(range(df["t"].min(), df["t"].max() + 1), fill_value=0)
    complete["total_frp"] = complete["total_frp"].round(1)
    complete = complete.rename_axis("t").reset_index()
    return [{"t": int(r.t), "count": int(r.count), "total_frp": float(r.total_frp)}
            for r in complete.itertuples(index=False)]


def generate_hourly_series(processed_dir: Path = PROCESSED) -> Path | None:
    # Works whether W0-B3 chose one hotspots file or one per day
    geojson_files = sorted(processed_dir.glob("hotspots*.geojson"))
    if not geojson_files:
        print(f"[SKIP] no hotspots*.geojson in {processed_dir} yet (waiting for W1-B3).")
        return None

    features = []
    for file in geojson_files:
        features += json.loads(file.read_text(encoding="utf-8")).get("features", [])
    series = build_series(features)

    output_path = processed_dir / "hourly_series.json"
    updated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    output_path.write_text(json.dumps({"updated_at": updated_at, "series": series}, separators=(",", ":")),
                           encoding="utf-8")
    print(f"[SAVED] {output_path} ({len(series)} hours)")
    return output_path


if __name__ == "__main__":
    generate_hourly_series()
