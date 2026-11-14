"""Country and region on every hotspot, plus a styled regions layer (W3-B6).

Countries come from Natural Earth 110m intersected with the episode bbox.
ADM1 polygons come from geoBoundaries. Both downloads are cached under data/raw/boundaries/.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import box, mapping

from config import BBOX, PROCESSED, RAW

COUNTRIES_URL = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/"
    "master/geojson/ne_110m_admin_0_countries.geojson"
)
ADM1_API = "https://www.geoboundaries.org/api/current/gbOpen/{iso}/ADM1/"
CACHE = RAW / "boundaries"
PALETTE = ["#9ecae1", "#a1d99b", "#fdae6b", "#bcbddc", "#fdd0a2", "#c994c7"]


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def repair_text(value):
    """geoBoundaries sometimes ships UTF-8 that was decoded as Latin-1 (`RegiÃ³n` -> `Región`)."""
    if not isinstance(value, str):
        return value
    try:
        return value.encode("latin-1").decode("utf-8")
    except UnicodeError:
        return value


def download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file() and destination.stat().st_size > 0:
        print(f"[CACHE] {destination.name}")
        return
    response = requests.get(url, timeout=120)
    response.raise_for_status()
    destination.write_bytes(response.content)
    print(f"[SAVED] {destination.name} ({destination.stat().st_size / 1e6:.2f} MB)")


def iso_of(row) -> str | None:
    """ISO 3166-1 alpha-3. Natural Earth leaves '-99' where the code is not reliable."""
    for column in ("ISO_A3", "ADM0_A3", "ISO_A3_EH"):
        value = row.get(column) if hasattr(row, "get") else row[column] if column in row else None
        if isinstance(value, str) and len(value) == 3 and value != "-99":
            return value
    return None


def countries_in_bbox(bbox=BBOX) -> gpd.GeoDataFrame:
    path = CACHE / "ne_110m_admin_0_countries.geojson"
    download(COUNTRIES_URL, path)
    world = gpd.read_file(path)
    inside = world[world.intersects(box(*bbox))].copy()
    inside["iso"] = inside.apply(iso_of, axis=1)
    return inside[inside["iso"].notna()]


def load_adm1(iso: str) -> gpd.GeoDataFrame:
    path = CACHE / f"{iso}_ADM1.geojson"
    if not path.is_file():
        meta = requests.get(ADM1_API.format(iso=iso), timeout=60)
        meta.raise_for_status()
        url = meta.json().get("gjDownloadURL")
        if not url:
            raise RuntimeError(f"geoBoundaries has no ADM1 download for {iso}")
        download(url, path)
    frame = gpd.read_file(path)
    frame["iso"] = iso
    return frame


def _region_name(frame: gpd.GeoDataFrame) -> pd.Series:
    for column in ("shapeName", "shapeName_en", "name"):
        if column in frame.columns:
            return frame[column]
    raise RuntimeError(f"ADM1 file has no region name. Columns: {list(frame.columns)}")


def regions_for_episode(bbox=BBOX) -> gpd.GeoDataFrame:
    countries = countries_in_bbox(bbox)
    if countries.empty:
        return gpd.GeoDataFrame(columns=["country", "region"], geometry=[], crs="EPSG:4326")
    pieces = []
    area = box(*bbox)
    for _, country in countries.iterrows():
        adm1 = load_adm1(country["iso"])
        hit = adm1[adm1.intersects(area)].copy()
        if hit.empty:
            print(f"  {country['iso']}: no region touches the bbox")
            continue
        hit["country"] = repair_text(country.get("ADMIN") or country["iso"])
        hit["region"] = _region_name(hit).map(repair_text)
        pieces.append(hit[["geometry", "country", "region"]])
        print(f"  {country['iso']}: {len(hit)} regions touch the bbox")
    if not pieces:
        return gpd.GeoDataFrame(columns=["country", "region"], geometry=[], crs="EPSG:4326")
    return gpd.GeoDataFrame(pd.concat(pieces, ignore_index=True), crs="EPSG:4326")


def for_display(regions: gpd.GeoDataFrame, bbox=BBOX, pad: float = 0.15, tolerance_m: float = 500) -> gpd.GeoDataFrame:
    """Clip to the episode (plus a small margin) and drop coastline detail the map cannot show."""
    west, south, east, north = bbox
    area = box(west - pad, max(south - pad, -90), east + pad, min(north + pad, 90))
    out = regions.copy()
    out["geometry"] = out.geometry.intersection(area)
    out = out[~out.geometry.is_empty & out.geometry.notna()].copy()
    if out.empty:
        return out
    projected = out.to_crs(out.estimate_utm_crs())
    projected["geometry"] = projected.geometry.simplify(tolerance_m, preserve_topology=True)
    return projected.to_crs("EPSG:4326")


def write_regions(regions: gpd.GeoDataFrame, destination: Path) -> None:
    features = []
    for index, row in enumerate(regions.itertuples(index=False)):
        features.append({
            "type": "Feature",
            "geometry": mapping(row.geometry),
            "properties": {
                "country": row.country,
                "region": row.region,
                "color": PALETTE[index % len(PALETTE)],
                "opacity": 0.35,
            },
        })
    collection = {"type": "FeatureCollection", "updated_at": utc_now(), "features": features}
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(collection, ensure_ascii=False), encoding="utf-8")
    print(f"[SAVED] {destination} ({len(features)} regions)")


def annotate_hotspots(regions: gpd.GeoDataFrame, hotspots_path: Path) -> None:
    collection = json.loads(hotspots_path.read_text(encoding="utf-8"))
    features = collection.get("features", [])
    if not features:
        print(f"[SKIP] {hotspots_path} has no hotspots.")
        return
    points = gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")
    # A second run already has these columns; drop them so the join does not rename the new values.
    points = points.drop(columns=[name for name in ("country", "region") if name in points.columns])
    joined = gpd.sjoin(points, regions[["geometry", "country", "region"]], how="left", predicate="intersects")
    joined = joined[~joined.index.duplicated(keep="first")].sort_index()
    if len(joined) != len(features):
        raise RuntimeError(f"region join changed the hotspot count ({len(features)} -> {len(joined)})")
    for feature, row in zip(features, joined.itertuples(index=False)):
        feature["properties"]["country"] = None if pd.isna(row.country) else str(row.country)
        feature["properties"]["region"] = None if pd.isna(row.region) else str(row.region)
    collection["updated_at"] = utc_now()
    hotspots_path.write_text(json.dumps(collection, ensure_ascii=False), encoding="utf-8")
    missing = sum(1 for feature in features if feature["properties"]["region"] is None)
    print(f"[UPDATED] {hotspots_path}: country and region on {len(features)} hotspots, {missing} outside every region")


def main() -> None:
    hotspots_path = PROCESSED / "hotspots.geojson"
    if not hotspots_path.is_file():
        print(f"[SKIP] {hotspots_path} not found yet (waiting for W1-B3).")
        return
    regions = regions_for_episode()
    if regions.empty:
        print("[SKIP] no administrative region intersects the bbox.")
        return
    write_regions(for_display(regions), PROCESSED / "regions.geojson")
    annotate_hotspots(regions, hotspots_path)


if __name__ == "__main__":
    main()
