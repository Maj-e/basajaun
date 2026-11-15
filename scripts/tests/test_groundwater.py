"""Tests for groundwater bodies + ash leachate risk (W3-B7). No network: hand-built EEA answers."""
import json

import geopandas as gpd
import pytest
from shapely.geometry import box, mapping

import groundwater
import make_manifest
import validate

BBOX = (-5.6, 36.3, -4.6, 36.9)


def body(code, name, geometry, geology, chemical, at_risk="No"):
    return {"type": "Feature", "geometry": mapping(geometry), "properties": {
        "euGroundWaterBodyCode": code, "groundWaterBodyName": name, "geologicalFormation": geology,
        "gwChemicalStatusValue": chemical, "gwAtRiskChemical": at_risk}}


RAW = {"type": "FeatureCollection", "features": [
    body("ES1", "SIERRA DE MIJAS", box(-4.8, 36.5, -4.6, 36.7), "Fissured aquifers including karst - highly productive", 2),
    body("ES2", "BAJO GUADALHORCE", box(-4.6, 36.6, -4.4, 36.8), "Porous aquifers - moderately productive", 3, "Yes"),
    body("ES3", "MARBELLA-ESTEPONA", box(-5.3, 36.4, -4.9, 36.6), "Porous aquifers - moderately productive", 2),
    body("ES4", "SOMEWHERE", box(-5.6, 36.7, -5.4, 36.9), "Low productive formations", 2),
]}


@pytest.mark.parametrize("geology, status, at_risk, expected", [
    ("Fissured aquifers including karst - highly productive", "good", "No", "high"),
    ("Porous aquifers - moderately productive", "poor", "No", "high"),
    ("Porous aquifers - moderately productive", "good", "Yes", "high"),
    ("Porous aquifers - moderately productive", "good", "No", "medium"),
    ("Low productive formations", "good", "No", "low"),
    (None, "unknown", None, "low"),
])
def test_vulnerability(geology, status, at_risk, expected):
    assert groundwater.vulnerability(geology, status, at_risk) == expected


def test_bodies_are_styled():
    bodies = groundwater.to_bodies(RAW).set_index("code")
    assert bodies.loc["ES1", "vulnerability"] == "high" and bodies.loc["ES1", "color"] == groundwater.STYLE["high"]["color"]
    assert bodies.loc["ES2", "chemical_status"] == "poor" and bool(bodies.loc["ES2", "at_risk_chemical"])
    assert bodies.loc["ES3", "vulnerability"] == "medium"
    assert bodies.loc["ES3", "name"] == "Marbella-Estepona"


def test_aquifer_under_each_fire():
    bodies = groundwater.to_bodies(RAW)
    fires = gpd.GeoDataFrame(geometry=[
        box(-5.2, 36.45, -5.1, 36.55),      # inside Marbella-Estepona
        box(-4.65, 36.62, -4.5, 36.68),     # mostly over Bajo Guadalhorce (poor)
        box(-5.0, 36.8, -4.95, 36.85),      # over nothing
    ], crs="EPSG:4326")
    out = groundwater.aquifer_under_fires(fires, bodies)
    assert out[0] == {"gw_body": "Marbella-Estepona", "gw_vulnerability": "medium", "gw_chemical_status": "good"}
    assert out[1]["gw_body"] == "Bajo Guadalhorce" and out[1]["gw_vulnerability"] == "high"
    assert out[2] == {"gw_body": None, "gw_vulnerability": None, "gw_chemical_status": None}


def test_run_writes_a_valid_layer_and_updates_fires(tmp_path):
    raw = tmp_path / "raw.geojson"
    raw.write_text(json.dumps(RAW))
    processed = tmp_path / "processed"
    processed.mkdir()
    fire = {"type": "Feature", "geometry": mapping(box(-5.2, 36.45, -5.1, 36.55)), "properties": {"fire_id": 1}}
    (processed / "fires.geojson").write_text(json.dumps({"type": "FeatureCollection", "updated_at": "x", "features": [fire]}))

    assert groundwater.run(processed, raw, BBOX)
    assert validate.validate_file(processed / "groundwater.geojson", validate.load_registry(), tmp_path) == []
    props = json.loads((processed / "fires.geojson").read_text())["features"][0]["properties"]
    assert props["fire_id"] == 1 and props["gw_body"] == "Marbella-Estepona"


def test_run_skips_outside_europe(tmp_path, capsys):
    raw = tmp_path / "raw.geojson"
    raw.write_text(json.dumps({"type": "FeatureCollection", "features": []}))
    assert groundwater.run(tmp_path, raw, BBOX) is False
    assert "Europe only" in capsys.readouterr().out
    assert not (tmp_path / "groundwater.geojson").exists()


def test_run_skips_when_service_is_down(tmp_path, monkeypatch, capsys):
    def down(*args, **kwargs):
        raise groundwater.requests.ConnectionError("down")
    monkeypatch.setattr(groundwater.requests, "get", down)
    assert groundwater.run(tmp_path, tmp_path / "missing.geojson", BBOX) is False
    assert "[SKIP]" in capsys.readouterr().out


def test_manifest_legend_matches_style():
    [layer] = [l for l in make_manifest.LAYERS if l["id"] == "groundwater"]
    assert [item["color"] for item in layer["legend"]] == [groundwater.STYLE[k]["color"] for k in ("high", "medium", "low")]
