"""Groundwater bodies + contamination risk from ash and leachate (W3-B7).

After a fire, rain washes ash into the ground: the leachate (nitrates, phosphates, heavy metals,
PAHs) reaches the aquifer below, fast in karst. This script maps the groundwater bodies of the
episode area and flags, for every fire, the aquifer underneath and how vulnerable it is.

Source: EEA WISE Water Framework Directive 2022 groundwater bodies (Europe only, CC BY 4.0),
queried for the episode BBOX through the EEA ArcGIS REST service. Outside Europe it returns
nothing and the step is skipped.

Writes:
    <episode folder>/groundwater.geojson   fill layer, styled by vulnerability
    fires.geojson (in place)               gw_body, gw_vulnerability, gw_chemical_status per fire
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import requests
import shapely

from config import BBOX, PROCESSED, RAW

SERVICE = ("https://water.discomap.eea.europa.eu/arcgis/rest/services/WISE_WFD/"
           "WFD2022_GroundWaterBody_WM/MapServer/1/query")
RAW_FILE = RAW / "groundwater_eea.geojson"
TIMEOUT_S = 120
SIMPLIFY_M = 100
COORD_GRID = 1e-4

# WISE code list for gwChemicalStatusValue
CHEMICAL_STATUS = {"2": "good", "3": "poor"}
# Vulnerability of the aquifer to ash leachate -> display style
STYLE = {
    "high":   {"color": "#8e44ad", "opacity": 0.35},
    "medium": {"color": "#5b8def", "opacity": 0.25},
    "low":    {"color": "#9fb8c9", "opacity": 0.18},
}


def download(raw_file: Path = RAW_FILE, bbox=BBOX, refresh: bool = False) -> Path | None:
    if raw_file.exists() and not refresh:
        return raw_file
    params = {
        "geometry": ",".join(str(v) for v in bbox), "geometryType": "esriGeometryEnvelope",
        "inSR": 4326, "spatialRel": "esriSpatialRelIntersects", "outSR": 4326,
        "outFields": "euGroundWaterBodyCode,groundWaterBodyName,geologicalFormation,"
                     "gwChemicalStatusValue,gwAtRiskChemical,linkSurfaceWaterBody,cArea",
        "f": "geojson",
    }
    try:
        resp = requests.get(SERVICE, params=params, timeout=TIMEOUT_S)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        print(f"[SKIP] EEA groundwater service unavailable ({exc.__class__.__name__}): no groundwater layer.")
        return None
    raw_file.parent.mkdir(parents=True, exist_ok=True)
    raw_file.write_text(json.dumps(data), encoding="utf-8")
    print(f"[SAVED] {raw_file} ({len(data.get('features', []))} groundwater bodies)")
    return raw_file


def vulnerability(geology: str | None, chemical_status: str, at_risk: str | None) -> str:
    """High: karst (fast leachate transfer) or already poor / at risk. Medium: porous. Low: the rest."""
    geology = (geology or "").lower()
    if "karst" in geology or chemical_status == "poor" or (at_risk or "").lower() == "yes":
        return "high"
    if "porous" in geology:
        return "medium"
    return "low"


def to_bodies(raw: dict) -> gpd.GeoDataFrame:
    rows = []
    for feature in raw.get("features", []):
        p = feature.get("properties") or {}
        geometry = shapely.geometry.shape(feature["geometry"]) if feature.get("geometry") else None
        if geometry is None or geometry.is_empty:
            continue
        status = CHEMICAL_STATUS.get(str(p.get("gwChemicalStatusValue")), "unknown")
        level = vulnerability(p.get("geologicalFormation"), status, p.get("gwAtRiskChemical"))
        rows.append({
            "geometry": geometry.buffer(0),
            "code": p.get("euGroundWaterBodyCode"),
            "name": (p.get("groundWaterBodyName") or "").title() or None,
            "geology": p.get("geologicalFormation"),
            "chemical_status": status,
            "at_risk_chemical": (p.get("gwAtRiskChemical") or "").lower() == "yes",
            "vulnerability": level,
            **STYLE[level],
        })
    columns = ["geometry", "code", "name", "geology", "chemical_status", "at_risk_chemical",
               "vulnerability", "color", "opacity"]
    return gpd.GeoDataFrame(rows, columns=columns, geometry="geometry", crs="EPSG:4326")


def display_layer(bodies: gpd.GeoDataFrame, bbox=BBOX) -> gpd.GeoDataFrame:
    area = shapely.geometry.box(*bbox)
    out = bodies[bodies.intersects(area)].copy()
    out["geometry"] = out.geometry.intersection(area)
    if out.empty:
        return out
    utm = out.estimate_utm_crs()
    out = out.to_crs(utm)
    out["geometry"] = out.geometry.simplify(SIMPLIFY_M, preserve_topology=True)
    out = out.to_crs("EPSG:4326")
    out["geometry"] = shapely.set_precision(out.geometry.values, COORD_GRID)
    return out[~out.geometry.is_empty]


def aquifer_under_fires(fires: gpd.GeoDataFrame, bodies: gpd.GeoDataFrame) -> list[dict]:
    """For each fire: the groundwater body with the largest overlap (None when there is none)."""
    if fires.empty:
        return []
    if bodies.empty:
        return [{"gw_body": None, "gw_vulnerability": None, "gw_chemical_status": None} for _ in range(len(fires))]
    utm = fires.estimate_utm_crs()
    fires_utm, bodies_utm = fires.to_crs(utm), bodies.to_crs(utm)
    tree = shapely.STRtree(bodies_utm.geometry.values)
    out = []
    for geom in fires_utm.geometry.values:
        best, best_area = None, 0.0
        for i in tree.query(geom, predicate="intersects"):
            area = geom.intersection(bodies_utm.geometry.values[i]).area
            if area > best_area:
                best, best_area = bodies.iloc[i], area
        out.append({"gw_body": best["name"] if best is not None else None,
                    "gw_vulnerability": best["vulnerability"] if best is not None else None,
                    "gw_chemical_status": best["chemical_status"] if best is not None else None})
    return out


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run(processed: Path = PROCESSED, raw_file: Path = RAW_FILE, bbox=BBOX, refresh: bool = False) -> bool:
    raw = download(raw_file, bbox, refresh)
    if raw is None:
        return False
    bodies = to_bodies(json.loads(raw.read_text(encoding="utf-8")))
    if bodies.empty:
        print("[SKIP] no groundwater bodies in this area (EEA data covers Europe only).")
        return False

    updated_at = utc_now()
    layer = display_layer(bodies, bbox)
    fc = json.loads(layer.to_json(drop_id=True, na="drop"))
    out = {"type": "FeatureCollection", "updated_at": updated_at, "features": fc["features"]}
    path = processed / "groundwater.geojson"
    processed.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    counts = layer["vulnerability"].value_counts().to_dict()
    print(f"[SAVED] {path} ({len(layer)} bodies, {path.stat().st_size / 1e6:.2f} MB, vulnerability {counts})")

    fires_path = processed / "fires.geojson"
    if fires_path.exists():
        fires_fc = json.loads(fires_path.read_text(encoding="utf-8"))
        if fires_fc.get("features"):
            fires = gpd.GeoDataFrame.from_features(fires_fc["features"], crs="EPSG:4326")
            for feature, values in zip(fires_fc["features"], aquifer_under_fires(fires, bodies)):
                feature["properties"].update(values)
            fires_fc["updated_at"] = updated_at
            fires_path.write_text(json.dumps(fires_fc, separators=(",", ":")), encoding="utf-8")
            high = sum(1 for f in fires_fc["features"] if f["properties"].get("gw_vulnerability") == "high")
            print(f"[UPDATED] {fires_path}: aquifer added to {len(fires_fc['features'])} fires ({high} over a highly vulnerable one)")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Groundwater bodies + ash leachate risk per fire (EEA WISE).")
    parser.add_argument("--refresh", action="store_true", help="query the EEA service again")
    run(refresh=parser.parse_args().refresh)


if __name__ == "__main__":
    main()
