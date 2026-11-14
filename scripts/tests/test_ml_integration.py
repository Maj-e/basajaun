"""Integration of IA1 features, the IA2 risk model and the IA3 map contract.

Each published episode must have the inputs the model reads. The model
itself is trained on a tiny copy of that episode's bbox: the real
roads and weather files are multi-megabyte and are not what this
contract checks.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import config
import make_manifest
import validate
from risk_ml import RISK_COLORS, run_risk_model

EPISODE_IDS = (
    "sierra-bermeja-2021-09",
    "chile-2026-02",
    "los-angeles-2025-01",
)

CELL_KEYS = (
    "cell_id",
    "reference_date",
    "ignition_prob",
    "risk_pct",
    "risk_level",
    "drivers",
    "recommended_action",
    "fill",
    "stroke",
)

METRIC_KEYS = ("val_roc_auc", "val_pr_auc", "feature_importances", "tier_counts")

# Same shape IA3-1 will register in make_manifest.LAYERS. Passed in here so
# the contract can be checked before that list is edited.
IGNITION_LAYER = {
    "id": "ignition_risk",
    "name": "Municipal ignition risk",
    "file": "processed/ignition_risk.geojson",
    "type": "fill",
    "temporal": False,
    "active": False,
    "popup": [
        "cell_id",
        "reference_date",
        "risk_level",
        "risk_pct",
        "drivers",
        "recommended_action",
    ],
    "legend": [
        {"color": RISK_COLORS["critical"], "text": "Critical"},
        {"color": RISK_COLORS["high"], "text": "High"},
        {"color": RISK_COLORS["moderate"], "text": "Moderate"},
        {"color": RISK_COLORS["low"], "text": "Low"},
    ],
}


def _episode(episode_id: str) -> dict:
    doc = json.loads(config.EPISODES_FILE.read_text(encoding="utf-8"))
    return config.resolve_episode(doc, episode_id)


def _write_min_inputs(dest: Path, bbox: tuple[float, float, float, float]) -> None:
    """A few weather days and three ignitions at the centre of the bbox."""
    west, south, east, north = bbox
    lon = round((west + east) / 2.0, 4)
    lat = round((south + north) / 2.0, 4)
    weather = {
        "type": "FeatureCollection",
        "updated_at": "2026-01-01T00:00:00Z",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {
                    "timestamp_utc": f"2026-01-0{day}T14:00:00Z",
                    "temperature": 22.0 + day * 2.5,
                    "humidity": 65.0 - day * 7.0,
                    "speed": 10.0 + day * 4.0,
                    "rain": 0.0,
                },
            }
            for day in range(1, 6)
        ],
    }
    hotspots = {
        "type": "FeatureCollection",
        "updated_at": "2026-01-01T00:00:00Z",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {
                    "timestamp_utc": f"2026-01-0{day}T15:00:00Z",
                    "confidence": "high",
                    "frp": 45.0,
                },
            }
            for day in (2, 4, 5)
        ],
    }
    (dest / "weather.geojson").write_text(json.dumps(weather), encoding="utf-8")
    (dest / "hotspots.geojson").write_text(json.dumps(hotspots), encoding="utf-8")


@pytest.mark.parametrize("episode_id", EPISODE_IDS)
def test_published_episode_has_model_inputs(episode_id: str):
    processed = config.episode_paths(_episode(episode_id))["processed"]
    assert (processed / "hotspots.geojson").is_file(), episode_id
    assert (processed / "weather.geojson").is_file(), episode_id


@pytest.mark.parametrize("episode_id", EPISODE_IDS)
def test_episode_produces_contract_risk_layer(episode_id: str, tmp_path: Path):
    episode = _episode(episode_id)
    bbox = tuple(episode["bbox"])
    processed = tmp_path / "processed"
    processed.mkdir()
    _write_min_inputs(processed, bbox)

    fc = run_risk_model(processed, bbox)

    data_dir = tmp_path / "data"
    subdir = episode["dir"]
    out_dir = data_dir / subdir
    out_dir.mkdir(parents=True)
    out_file = out_dir / "ignition_risk.geojson"
    out_file.write_text(json.dumps(fc), encoding="utf-8")

    registry = validate.load_registry()
    assert validate.validate_file(out_file, registry, data_dir) == []

    assert fc["type"] == "FeatureCollection"
    metrics = fc["model_metrics"]
    for key in METRIC_KEYS:
        assert key in metrics
    assert isinstance(metrics["feature_importances"], dict)
    assert set(metrics["tier_counts"]) == set(RISK_COLORS)
    assert sum(metrics["tier_counts"].values()) == 144
    if metrics.get("validation_strategy") != "baseline_prior":
        assert 0.0 <= metrics["val_roc_auc"] <= 1.0
        assert 0.0 <= metrics["val_pr_auc"] <= 1.0

    assert len(fc["features"]) == 144
    for feature in fc["features"]:
        assert feature["geometry"]["type"] == "Polygon"
        props = feature["properties"]
        for key in CELL_KEYS:
            assert key in props, key
        prob = props["ignition_prob"]
        assert 0.0 <= prob <= 1.0
        assert props["risk_level"] in RISK_COLORS
        assert props["fill"] == RISK_COLORS[props["risk_level"]]
        assert props["stroke"] == props["fill"]
        assert props["risk_pct"] == round(prob * 100.0, 1)
        assert isinstance(props["drivers"], str) and props["drivers"]
        assert isinstance(props["recommended_action"], str) and props["recommended_action"]

    layers = [*make_manifest.LAYERS, IGNITION_LAYER]
    manifest = make_manifest.build_manifest(data_dir, layers=layers, subdir=subdir)
    listed = {layer["id"]: layer for layer in manifest["layers"]}
    layer = listed["ignition_risk"]
    assert layer["active"] is False
    assert layer["type"] == "fill"
    assert layer["file"] == f"{subdir}/ignition_risk.geojson"
    assert len(layer["legend"]) == 4
    assert "recommended_action" in layer["popup"]

    manifest_path = data_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    assert validate.validate_file(manifest_path, registry, data_dir) == []
