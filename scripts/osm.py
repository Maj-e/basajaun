"""OpenStreetMap layers + fire accessibility (W3-B4).

One Overpass query over the BBOX (padded so fires near the edge still find their nearest
fire station) returns water, roads and fire stations. This script then:
    - writes three styled, simplified layers for the map:
        web/data/processed/water.geojson          (fill: lakes, reservoirs, rivers)
        web/data/processed/roads.geojson          (line: color and width by road type)
        web/data/processed/fire_stations.geojson  (circle)
        web/data/processed/water_points.geojson   (circle: hydrants, firefighting tanks, tanks, wells, springs)
    - adds dist_road_km, dist_water_km, dist_fire_station_km to every fire in
      web/data/processed/fires.geojson (W2-B2), measured on the full-detail data.

The raw Overpass answer is cached in data/raw/osm_overpass_<query hash>.json (not versioned, ~200 MB);
use --refresh to download it again.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import requests
import shapely
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import linemerge, polygonize, unary_union

from config import BBOX, PROCESSED, RAW

def raw_file_for(query: str) -> Path:
    """Cache name carries a hash of the query: changing the query (new tags) downloads again."""
    return RAW / f"osm_overpass_{hashlib.sha1(query.encode()).hexdigest()[:8]}.json"

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
PAD_DEG = 0.2          # ~20 km around the BBOX, for distances near the edge
TIMEOUT_S = 300            # Overpass servers turn big requests away first when they are busy
MAXSIZE_BYTES = 512 * 1024 * 1024
USER_AGENT = "ulinautas-hackathon/0.1"

ROAD_TYPES = ("primary", "secondary", "tertiary", "track", "path")
# Display style per road type: (color, width px, simplify tolerance m)
ROAD_STYLE = {
    "primary":   ("#f2a541", 2.4, 30),
    "secondary": ("#f6c667", 1.8, 30),
    "tertiary":  ("#f9dfa0", 1.3, 40),
    "track":     ("#b08968", 0.9, 60),
    "path":      ("#9c8b7a", 0.6, 60),
}
WATER_COLOR, WATER_OPACITY = "#3d8bd4", 0.55
RIVER_WIDTH = 1.2
MINOR_ROADS = ("track", "path")
MIN_MINOR_ROAD_M = 1000     # shorter track / path pieces are left out of the map layer (still used for distances)
MIN_WATER_AREA_KM2 = 0.05   # smaller ponds are left out of the map layer (still used for distances)
WATER_SIMPLIFY_M = 40
STATION_STYLE = {"color": "#2b8cbe", "radius": 6, "border": "#ffffff"}
# Where fire crews can load water, by kind -> colour (blues: darker = more useful for firefighting)
WATER_POINT_COLORS = {
    "fire_water": "#0077b6",   # emergency=water_tank / suction_point / fire_water_pond
    "hydrant": "#00b4d8",      # emergency=fire_hydrant
    "tank": "#48cae4",         # man_made=water_tank / reservoir_covered
    "well": "#90e0ef",         # man_made=water_well
    "spring": "#ade8f4",       # natural=spring
    "water_point": "#caf0f8",  # amenity=water_point
}
WATER_POINT_STYLE = {"radius": 4, "border": "#023e8a"}
COORD_GRID = 1e-4           # ~10 m: coordinates rounded to 4 decimals


# --- download -------------------------------------------------------------------

def overpass_query(bbox=BBOX, pad=PAD_DEG) -> str:
    west, south, east, north = bbox
    b = f"({south - pad},{west - pad},{north + pad},{east + pad})"
    roads = "|".join(ROAD_TYPES)
    return f"""[out:json][timeout:{TIMEOUT_S}][maxsize:{MAXSIZE_BYTES}];
(
  way["highway"~"^({roads})$"]{b};
  way["natural"="water"]{b};
  relation["natural"="water"]{b};
  way["landuse"="reservoir"]{b};
  relation["landuse"="reservoir"]{b};
  way["waterway"="river"]{b};
  node["amenity"="fire_station"]{b};
  way["amenity"="fire_station"]{b};
  node["emergency"~"^(fire_hydrant|water_tank|suction_point|fire_water_pond)$"]{b};
  way["emergency"~"^(water_tank|fire_water_pond)$"]{b};
  node["man_made"~"^(water_tank|water_well|reservoir_covered)$"]{b};
  way["man_made"~"^(water_tank|reservoir_covered)$"]{b};
  node["natural"="spring"]{b};
  node["amenity"="water_point"]{b};
);
out tags geom qt;"""


def download(raw_file: Path | None = None, refresh: bool = False) -> Path:
    raw_file = raw_file or raw_file_for(overpass_query())
    if raw_file.exists() and not refresh:
        print(f"[CACHE] {raw_file} ({raw_file.stat().st_size / 1e6:.0f} MB)")
        return raw_file
    raw_file.parent.mkdir(parents=True, exist_ok=True)
    query = overpass_query()
    last_error = None
    for url in OVERPASS_URLS:
        print(f"Querying Overpass ({url}), this can take a few minutes...")
        try:
            start = time.perf_counter()
            with requests.post(url, data={"data": query}, headers={"User-Agent": USER_AGENT},
                               timeout=TIMEOUT_S + 60, stream=True) as resp:
                resp.raise_for_status()
                tmp = raw_file.with_suffix(".part")
                with tmp.open("wb") as fh:
                    for chunk in resp.iter_content(1 << 20):
                        fh.write(chunk)
            tmp.replace(raw_file)
            print(f"[SAVED] {raw_file} ({raw_file.stat().st_size / 1e6:.0f} MB in {time.perf_counter() - start:.0f}s)")
            return raw_file
        except requests.RequestException as exc:
            last_error = exc
            print(f"  failed: {exc}")
    raise RuntimeError(f"every Overpass endpoint failed: {last_error}")


def _compact(obj: dict):
    """json object_hook: {"lat", "lon"} points become (lon, lat) tuples while parsing (saves memory)."""
    if len(obj) == 2 and "lat" in obj and "lon" in obj:
        return (obj["lon"], obj["lat"])
    return obj


def load_elements(raw_file: Path) -> list[dict]:
    with raw_file.open(encoding="utf-8") as fh:
        return json.load(fh, object_hook=_compact)["elements"]


# --- parsing --------------------------------------------------------------------

def _is_closed(coords) -> bool:
    return len(coords) >= 4 and coords[0] == coords[-1]


def _relation_polygons(members: list[dict]):
    """Assemble a multipolygon relation from its outer / inner way members."""
    def lines(role):
        return [LineString(m["geometry"]) for m in members
                if m.get("type") == "way" and m.get("role", "outer") == role and len(m.get("geometry") or []) >= 2]
    outers = list(polygonize(linemerge(lines("outer")))) if lines("outer") else []
    if not outers:
        return None
    shape = unary_union(outers)
    inners = list(polygonize(linemerge(lines("inner")))) if lines("inner") else []
    if inners:
        shape = shape.difference(unary_union(inners))
    return shape if not shape.is_empty else None


def water_point_kind(tags: dict) -> str | None:
    emergency, man_made = tags.get("emergency"), tags.get("man_made")
    if emergency in ("water_tank", "suction_point", "fire_water_pond"):
        return "fire_water"
    if emergency == "fire_hydrant":
        return "hydrant"
    if man_made in ("water_tank", "reservoir_covered"):
        return "tank"
    if man_made == "water_well":
        return "well"
    if tags.get("natural") == "spring":
        return "spring"
    if tags.get("amenity") == "water_point":
        return "water_point"
    return None


def parse(elements: list[dict]) -> dict[str, gpd.GeoDataFrame]:
    roads, water, stations, water_points = [], [], [], []
    for el in elements:
        tags = el.get("tags", {})
        name = tags.get("name")
        kind = el["type"]
        point_kind = water_point_kind(tags)
        if point_kind and kind in ("node", "way"):
            if kind == "node":
                geometry = Point(el["lon"], el["lat"])
            else:
                coords = el.get("geometry") or []
                if not coords:
                    continue
                geometry = (Polygon(coords) if _is_closed(coords) else LineString(coords)).centroid if len(coords) > 1 else Point(coords[0])
            water_points.append({"geometry": geometry, "kind": point_kind, "name": name})
            continue
        if kind == "node" and tags.get("amenity") == "fire_station":
            stations.append({"geometry": Point(el["lon"], el["lat"]), "name": name})
            continue
        if kind == "way":
            coords = el.get("geometry") or []
            if len(coords) < 2:
                continue
            if tags.get("amenity") == "fire_station":
                shape = Polygon(coords) if _is_closed(coords) else LineString(coords)
                stations.append({"geometry": shape.centroid, "name": name})
            elif tags.get("highway") in ROAD_TYPES:
                roads.append({"geometry": LineString(coords), "highway": tags["highway"], "name": name})
            elif tags.get("waterway") == "river":
                water.append({"geometry": LineString(coords), "kind": "river", "name": name})
            elif _is_closed(coords):  # natural=water / landuse=reservoir area
                kind_ = "reservoir" if tags.get("landuse") == "reservoir" or tags.get("water") == "reservoir" else "lake"
                water.append({"geometry": Polygon(coords).buffer(0), "kind": kind_, "name": name})
        elif kind == "relation":
            shape = _relation_polygons(el.get("members", []))
            if shape is not None:
                kind_ = "reservoir" if tags.get("landuse") == "reservoir" or tags.get("water") == "reservoir" else "lake"
                water.append({"geometry": shape, "kind": kind_, "name": name})

    def frame(rows, columns):
        return gpd.GeoDataFrame(rows, columns=["geometry", *columns], geometry="geometry", crs="EPSG:4326")
    return {
        "roads": frame(roads, ["highway", "name"]),
        "water": frame(water, ["kind", "name"]),
        "stations": frame(stations, ["name"]),
        "water_points": frame(water_points, ["kind", "name"]),
    }


# --- distances ------------------------------------------------------------------

def add_distances(fires: gpd.GeoDataFrame, layers: dict[str, gpd.GeoDataFrame]) -> gpd.GeoDataFrame:
    """Distance in km from each fire polygon to the nearest road / water / fire station (0 if touching)."""
    fires = fires.copy()
    if fires.empty:
        return fires
    utm = fires.estimate_utm_crs()
    fires_utm = fires.to_crs(utm)
    for column, key in (("dist_road_km", "roads"), ("dist_water_km", "water"), ("dist_fire_station_km", "stations"),
                        ("dist_water_point_km", "water_points")):
        if key not in layers:
            continue
        target = layers[key]
        if target.empty:
            fires[column] = None
            continue
        tree = shapely.STRtree(target.to_crs(utm).geometry.values)
        _, dist_m = tree.query_nearest(fires_utm.geometry.values, return_distance=True, all_matches=False)
        fires[column] = [round(float(d) / 1000.0, 2) for d in dist_m]
    return fires


# --- display layers -------------------------------------------------------------

def _simplify(gdf: gpd.GeoDataFrame, tolerance_m: float) -> gpd.GeoDataFrame:
    if gdf.empty:
        return gdf
    utm = gdf.estimate_utm_crs()
    out = gdf.to_crs(utm)
    out["geometry"] = out.geometry.simplify(tolerance_m, preserve_topology=True)
    return out.to_crs("EPSG:4326")


def _finish(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    gdf = gdf.copy()
    gdf["geometry"] = shapely.set_precision(gdf.geometry.values, COORD_GRID)
    return gdf[~gdf.geometry.is_empty & ~gdf.geometry.isna()]


def roads_layer(roads: gpd.GeoDataFrame, area) -> gpd.GeoDataFrame:
    roads = roads[roads.intersects(area)].copy()
    roads["geometry"] = roads.geometry.intersection(area)
    parts = []
    for highway, group in roads.groupby("highway"):
        color, width, tolerance = ROAD_STYLE[highway]
        # Join the pieces of the same road (same type + name) into one feature
        merged = group.fillna({"name": ""}).dissolve(by="name", as_index=False)
        merged["geometry"] = [linemerge(g) if g.geom_type == "MultiLineString" else g for g in merged.geometry]
        merged = _simplify(merged, tolerance)
        if highway in MINOR_ROADS:
            # Thousands of tiny tracks weigh megabytes and add nothing at map scale
            pieces = merged.explode(index_parts=False)
            pieces = pieces[pieces.to_crs(pieces.estimate_utm_crs()).length >= MIN_MINOR_ROAD_M]
            merged = pieces.dissolve(by="name", as_index=False) if not pieces.empty else pieces
        merged["highway"], merged["color"], merged["width"] = highway, color, width
        parts.append(merged)
    if not parts:
        return gpd.GeoDataFrame(columns=["geometry", "name", "highway", "color", "width"], crs="EPSG:4326")
    out = gpd.GeoDataFrame(gpd.pd.concat(parts, ignore_index=True), crs="EPSG:4326")
    out["name"] = out["name"].replace("", None)
    # Draw minor roads first, major on top
    order = {h: i for i, h in enumerate(reversed(ROAD_TYPES))}
    out = out.sort_values("highway", key=lambda s: s.map(order)).reset_index(drop=True)
    return _finish(out[["geometry", "name", "highway", "color", "width"]])


def water_layer(water: gpd.GeoDataFrame, area) -> gpd.GeoDataFrame:
    water = water[water.intersects(area)].copy()
    water["geometry"] = water.geometry.intersection(area)
    is_area = water.geom_type.isin(["Polygon", "MultiPolygon"])
    if is_area.any():
        utm = water.estimate_utm_crs()
        area_km2 = water.to_crs(utm).area / 1e6
        water = water[~is_area | (area_km2 >= MIN_WATER_AREA_KM2)]
    water = _simplify(water, WATER_SIMPLIFY_M)
    water["color"], water["opacity"] = WATER_COLOR, WATER_OPACITY
    water["width"] = [RIVER_WIDTH if t in ("LineString", "MultiLineString") else None for t in water.geom_type]
    return _finish(water[["geometry", "name", "kind", "color", "opacity", "width"]])


def water_points_layer(points: gpd.GeoDataFrame, area) -> gpd.GeoDataFrame:
    points = points[points.intersects(area)].copy()
    points["color"] = points["kind"].map(WATER_POINT_COLORS)
    for key, value in WATER_POINT_STYLE.items():
        points[key] = value
    return _finish(points[["geometry", "name", "kind", "color", *WATER_POINT_STYLE]])


def stations_layer(stations: gpd.GeoDataFrame, area) -> gpd.GeoDataFrame:
    stations = stations[stations.intersects(area)].copy()
    for key, value in STATION_STYLE.items():
        stations[key] = value
    return _finish(stations[["geometry", "name", *STATION_STYLE]])


# --- output ---------------------------------------------------------------------

def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def to_feature_collection(gdf: gpd.GeoDataFrame, updated_at: str) -> dict:
    fc = json.loads(gdf.to_json(drop_id=True, na="drop")) if not gdf.empty else {"type": "FeatureCollection", "features": []}
    return {"type": "FeatureCollection", "updated_at": updated_at, "features": fc["features"]}


def write(fc: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(fc, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(f"[SAVED] {path} ({len(fc['features'])} features, {path.stat().st_size / 1e6:.2f} MB)")


def update_fires(fires_path: Path, layers: dict[str, gpd.GeoDataFrame], updated_at: str) -> None:
    if not fires_path.exists():
        print(f"[SKIP] {fires_path} not found yet (waiting for W2-B2): no distances added.")
        return
    fc = json.loads(fires_path.read_text(encoding="utf-8"))
    if not fc.get("features"):
        print(f"[SKIP] {fires_path} has no fires: no distances added.")
        return
    fires = gpd.GeoDataFrame.from_features(fc["features"], crs="EPSG:4326")
    fires = add_distances(fires, layers)
    for feature, (_, row) in zip(fc["features"], fires.iterrows()):
        for column in ("dist_road_km", "dist_water_km", "dist_fire_station_km", "dist_water_point_km"):
            if column not in row:
                continue
            feature["properties"][column] = row[column]
    fc["updated_at"] = updated_at
    fires_path.write_text(json.dumps(fc, separators=(",", ":")), encoding="utf-8")
    print(f"[UPDATED] {fires_path}: distances added to {len(fc['features'])} fires")


def main() -> None:
    parser = argparse.ArgumentParser(description="OSM water / roads / fire stations + fire accessibility.")
    parser.add_argument("--refresh", action="store_true", help="download the Overpass data again")
    args = parser.parse_args()

    try:
        raw = download(refresh=args.refresh)
    except RuntimeError as exc:
        # Context layers only: keep whatever is already there and let the rest of make data go on
        print(f"[SKIP] OpenStreetMap unavailable ({exc}). Previous OSM files kept; retry later with: uv run scripts/osm.py")
        return
    print("Parsing OSM data...")
    layers = parse(load_elements(raw))
    print(f"  roads {len(layers['roads'])} · water {len(layers['water'])} · fire stations {len(layers['stations'])}")

    updated_at = utc_now()
    update_fires(PROCESSED / "fires.geojson", layers, updated_at)

    area = box(*BBOX)
    write(to_feature_collection(water_layer(layers["water"], area), updated_at), PROCESSED / "water.geojson")
    write(to_feature_collection(roads_layer(layers["roads"], area), updated_at), PROCESSED / "roads.geojson")
    write(to_feature_collection(stations_layer(layers["stations"], area), updated_at), PROCESSED / "fire_stations.geojson")
    write(to_feature_collection(water_points_layer(layers["water_points"], area), updated_at), PROCESSED / "water_points.geojson")


if __name__ == "__main__":
    main()
