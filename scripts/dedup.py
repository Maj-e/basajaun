import json
from pathlib import Path
import geopandas as gpd
from shapely.geometry import Point

try:
    from config import PROCESSED
except ImportError:
    PROCESSED = Path("web/data/processed")

MAX_DISTANCE_M = 1000.0  # 1 km
MAX_TIME_DIFF_H = 1.0    # 60 minutes (t is stored in hours since Unix epoch)


def deduplicate_hotspots(geojson_data: dict) -> tuple[dict, int]:
    """
    Merge MODIS and VIIRS detections within 1 km and 60 minutes.
    Keeps the higher-resolution VIIRS record and sets detected_by = ["MODIS", "VIIRS"].

    Returns:
        (updated_geojson_dict, merged_count)
    """
    features = geojson_data.get("features", [])
    if not features:
        return geojson_data, 0

    records = []
    for idx, feat in enumerate(features):
        props = feat.get("properties", {})
        lon, lat = feat["geometry"]["coordinates"][:2]
        records.append({
            "orig_idx": idx,
            "sensor": props.get("sensor"),
            "t": float(props["t"]),
            "geometry": Point(lon, lat),
        })

    gdf = gpd.GeoDataFrame(records, crs="EPSG:4326")

    modis_gdf = gdf[gdf["sensor"] == "MODIS"].copy()
    viirs_gdf = gdf[gdf["sensor"] == "VIIRS"].copy()

    if modis_gdf.empty or viirs_gdf.empty:
        return geojson_data, 0

    # Project to local UTM zone in meters for accurate Euclidean distances
    utm_crs = gdf.estimate_utm_crs()
    modis_utm = modis_gdf.to_crs(utm_crs)
    viirs_utm = viirs_gdf.to_crs(utm_crs)

    # Spatial pre-filter using a 1 km buffer around MODIS points
    modis_buffers = modis_utm[["orig_idx", "t", "geometry"]].copy()
    modis_buffers["geometry"] = modis_buffers.geometry.buffer(MAX_DISTANCE_M)

    candidates = gpd.sjoin(
        modis_buffers,
        viirs_utm[["orig_idx", "t", "geometry"]],
        how="inner",
        predicate="intersects",
        lsuffix="modis",
        rsuffix="viirs",
    )

    if candidates.empty:
        return geojson_data, 0

    # Filter by exact < 1 km distance and |Δt| < 60 min (1.0 hour)
    valid_matches = []
    viirs_geom_lookup = viirs_utm.set_index("orig_idx")["geometry"].to_dict()
    modis_geom_lookup = modis_utm.set_index("orig_idx")["geometry"].to_dict()

    for _, row in candidates.iterrows():
        time_diff_h = abs(row["t_viirs"] - row["t_modis"])
        if time_diff_h >= MAX_TIME_DIFF_H:
            continue

        m_idx = int(row["orig_idx_modis"])
        v_idx = int(row["orig_idx_viirs"])
        dist_m = modis_geom_lookup[m_idx].distance(viirs_geom_lookup[v_idx])

        if dist_m < MAX_DISTANCE_M:
            valid_matches.append({
                "m_idx": m_idx,
                "v_idx": v_idx,
                "dist_m": dist_m,
                "time_diff_h": time_diff_h,
            })

    if not valid_matches:
        return geojson_data, 0

    # Match each duplicate MODIS detection to its single nearest VIIRS detection
    valid_matches.sort(key=lambda item: (item["dist_m"], item["time_diff_h"]))
    modis_to_drop: set[int] = set()
    viirs_to_tag: set[int] = set()

    for match in valid_matches:
        m_idx = match["m_idx"]
        if m_idx not in modis_to_drop:
            modis_to_drop.add(m_idx)
            viirs_to_tag.add(match["v_idx"])

    # Rebuild feature list preserving exact JSON types and property order
    deduped_features = []
    for idx, feat in enumerate(features):
        if idx in modis_to_drop:
            continue
        if idx in viirs_to_tag:
            existing_sensors = feat["properties"].get("detected_by", ["VIIRS"])
            merged_sensors = sorted(set(existing_sensors) | {"MODIS", "VIIRS"})
            feat["properties"]["detected_by"] = merged_sensors
        deduped_features.append(feat)

    updated_geojson = {
        **geojson_data,
        "features": deduped_features,
    }
    return updated_geojson, len(modis_to_drop)


def main() -> None:
    hotspots_path = PROCESSED / "hotspots.geojson"
    if not hotspots_path.exists():
        print(f"[SKIP] {hotspots_path} not found yet (waiting for W1-B3): nothing to deduplicate.")
        return

    raw_data = json.loads(hotspots_path.read_text(encoding="utf-8"))
    initial_count = len(raw_data.get("features", []))

    deduped_data, merged_count = deduplicate_hotspots(raw_data)
    final_count = len(deduped_data.get("features", []))

    hotspots_path.write_text(json.dumps(deduped_data, indent=2), encoding="utf-8")
    print(
        f"Deduplication complete: merged {merged_count} MODIS hotspots into VIIRS "
        f"({initial_count} -> {final_count} total features)."
    )


if __name__ == "__main__":
    main()