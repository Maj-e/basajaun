import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import geopandas as gpd
import numpy as np
from sklearn.cluster import DBSCAN
from config import PROCESSED


def fire_style(frp_max: float, n_hotspots: int) -> tuple[str, float]:
    """Return (hex_color, fill_opacity) based on fire intensity."""
    if frp_max >= 100.0 or n_hotspots >= 20:
        return "#a50f15", 0.45
    if frp_max >= 30.0 or n_hotspots >= 8:
        return "#de2d26", 0.38
    return "#fb6a4a", 0.30


def cluster_fires(hotspots_path: Path, fires_output_path: Path, update_hotspots: bool = True) -> None:
    raw_fc = json.loads(hotspots_path.read_text(encoding="utf-8"))
    features = raw_fc.get("features", [])
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if not features:
        fires_fc = {"type": "FeatureCollection", "updated": updated, "features": []}
        fires_output_path.parent.mkdir(parents=True, exist_ok=True)
        fires_output_path.write_text(json.dumps(fires_fc, separators=(",", ":")))
        print(f"[SAVED] {fires_output_path} (0 fires)")
        return

    gdf = gpd.GeoDataFrame.from_features(raw_fc, crs="EPSG:4326")
    utm_crs = gdf.estimate_utm_crs()
    gdf_utm = gdf.to_crs(utm_crs)

    x_km = gdf_utm.geometry.x.to_numpy() / 1000.0
    y_km = gdf_utm.geometry.y.to_numpy() / 1000.0
    t_scaled = gdf["t"].astype(float).to_numpy() / 12.0

    coords_st = np.column_stack([x_km, y_km, t_scaled])
    labels = DBSCAN(eps=1.0, min_samples=2).fit_predict(coords_st)

    unique_clusters = sorted(c for c in set(labels) if c != -1)
    label_to_fire_id = {c: idx + 1 for idx, c in enumerate(unique_clusters)}

    fire_ids = [label_to_fire_id.get(int(lbl)) for lbl in labels]
    gdf_utm["fire_id"] = fire_ids

    if update_hotspots:
        for feat, fid in zip(features, fire_ids):
            feat["properties"]["fire_id"] = fid
        raw_fc["updated"] = updated
        hotspots_path.write_text(json.dumps(raw_fc, separators=(",", ":")))

    fire_records = []
    for fid in sorted(label_to_fire_id.values()):
        cluster = gdf_utm[gdf_utm["fire_id"] == fid]
        hull_poly = cluster.geometry.union_all().convex_hull.buffer(500.0)
        area_km2 = round(float(hull_poly.area) / 1_000_000.0, 3)

        n_hotspots = int(len(cluster))
        frp_max = round(float(cluster["frp"].astype(float).max()), 1)
        start_dt = str(cluster["datetime_utc"].min())
        end_dt = str(cluster["datetime_utc"].max())
        t_start = round(float(cluster["t"].astype(float).min()), 2)
        t_end = round(float(cluster["t"].astype(float).max()), 2)
        color, opacity = fire_style(frp_max, n_hotspots)

        fire_records.append({
            "geometry": hull_poly,
            "fire_id": fid,
            "start": start_dt,
            "end": end_dt,
            "t_start": t_start,
            "t_end": t_end,
            "n_hotspots": n_hotspots,
            "frp_max": frp_max,
            "area_km2": area_km2,
            "color": color,
            "opacity": opacity,
        })

    if fire_records:
        fires_gdf = gpd.GeoDataFrame(fire_records, crs=utm_crs).to_crs("EPSG:4326")
        fires_fc = json.loads(fires_gdf.to_json(drop_id=True))
    else:
        fires_fc = {"type": "FeatureCollection", "features": []}

    fires_fc["updated"] = updated
    fires_output_path.parent.mkdir(parents=True, exist_ok=True)
    fires_output_path.write_text(json.dumps(fires_fc, separators=(",", ":")))
    print(f"[SAVED] {fires_output_path} ({len(fire_records)} fire groups from {len(features)} hotspots)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Group fire hotspots into fire polygons using DBSCAN.")
    parser.add_argument("--input", type=str, default=str(PROCESSED / "hotspots.geojson"), help="Input hotspots GeoJSON")
    parser.add_argument("--output", type=str, default=str(PROCESSED / "fires.geojson"), help="Output fires GeoJSON")
    parser.add_argument("--no-update-hotspots", action="store_true", help="Do not write fire_id back to input")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[SKIP] {input_path} not found yet (waiting for W1-B3/W2-B1).")
        return

    cluster_fires(input_path, Path(args.output), update_hotspots=not args.no_update_hotspots)


if __name__ == "__main__":
    main()
