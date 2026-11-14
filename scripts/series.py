import json
from pathlib import Path
import pandas as pd

def generate_hourly_series():
    PROCESSED_DIR = Path("web/data/processed")
    # Supports whether W0-B3 decided on a single file or multiple files
    geojson_files = list(PROCESSED_DIR.glob("hotspots*.geojson"))
    
    if not geojson_files:
        print("No GeoJSON files found. Run W1-B3 first.")
        return

    records = []
    
    # 1. Extract data from GeoJSON
    for file in geojson_files:
        data = json.loads(file.read_text(encoding="utf-8"))
        for feature in data.get("features", []):
            props = feature["properties"]
            records.append({
                "t": props["t"],
                # If FRP is null, convert it to 0.0 to allow summation
                "frp": props.get("frp") or 0.0 
            })

    df = pd.DataFrame(records)
    output_path = PROCESSED_DIR / "hourly_series.json"

    # If there is no data at all (e.g., period without fires)
    if df.empty:
        output_path.write_text("[]", encoding="utf-8")
        return

    # 2. Group by hour 't'
    grouped = df.groupby("t").agg(
        count=("t", "size"),
        total_frp=("frp", "sum")
    )

    # 3. Fill missing hours (Zero-filling)
    t_min = df["t"].min()
    t_max = df["t"].max()
    all_hours = range(t_min, t_max + 1)
    
    # reindex inserts missing hours and assigns them 0
    complete_series = grouped.reindex(all_hours, fill_value=0)
    
    # Round FRP to 1 decimal place to avoid sending massive floats to the frontend
    complete_series["total_frp"] = complete_series["total_frp"].round(1)
    
    # Convert the 't' index back to a column
    complete_series = complete_series.reset_index().rename(columns={"index": "t"})

    # 4. Export to JSON optimized for charts (list of dictionaries)
    # Example: [{"t": 491950, "count": 12, "total_frp": 340.5}, ...]
    complete_series.to_json(output_path, orient="records")
    
    print(f"Hourly series exported to {output_path}")
    print(f"Covered range: {len(complete_series)} hours.")

if __name__ == "__main__":
    generate_hourly_series()