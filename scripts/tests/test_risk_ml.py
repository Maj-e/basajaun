"""Unit tests for scripts/risk_ml.py (IA2 municipal ignition risk model)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from risk_ml import (
    classify_risk_tier,
    fit_logistic_l2,
    pr_auc_score_np,
    predict_proba,
    roc_auc_score_np,
    run_risk_model,
)
from validate import load_registry, validate_file


def test_logistic_l2_separates_high_risk_conditions():
    rng = np.random.default_rng(7)
    X = rng.normal(size=(200, 3))
    y = (X[:, 0] - X[:, 1] > 0.3).astype(int)
    params, mean, std = fit_logistic_l2(X, y, l2=0.5)
    probs = predict_proba(X, params, mean, std)
    assert probs.shape == (200,)
    assert np.all((probs >= 0.0) & (probs <= 1.0))
    assert roc_auc_score_np(y, probs) > 0.90
    assert pr_auc_score_np(y, probs) > 0.85


def test_risk_tier_thresholds():
    assert classify_risk_tier(0.82) == "critical"
    assert classify_risk_tier(0.55) == "high"
    assert classify_risk_tier(0.30) == "moderate"
    assert classify_risk_tier(0.10) == "low"


def test_run_risk_model_produces_contract_valid_geojson(tmp_path: Path):
    bbox = (-5.3, 36.4, -5.0, 36.6)
    weather = {
        "type": "FeatureCollection",
        "updated_at": "2026-01-01T00:00:00Z",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [-5.15, 36.5]},
                "properties": {
                    "timestamp_utc": f"2026-01-0{d}T14:00:00Z",
                    "temperature": 22.0 + d * 2.5,
                    "humidity": 65.0 - d * 7.0,
                    "speed": 10.0 + d * 4.0,
                    "rain": 0.0,
                },
            }
            for d in range(1, 6)
        ],
    }
    hotspots = {
        "type": "FeatureCollection",
        "updated_at": "2026-01-01T00:00:00Z",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [-5.12, 36.52]},
                "properties": {
                    "timestamp_utc": f"2026-01-0{d}T15:00:00Z",
                    "confidence": "high",
                    "frp": 45.0,
                },
            }
            for d in (2, 4, 5)
        ],
    }
    (tmp_path / "weather.geojson").write_text(json.dumps(weather), encoding="utf-8")
    (tmp_path / "hotspots.geojson").write_text(json.dumps(hotspots), encoding="utf-8")

    fc = run_risk_model(tmp_path, bbox)
    out_file = tmp_path / "ignition_risk.geojson"
    out_file.write_text(json.dumps(fc), encoding="utf-8")

    errors = validate_file(out_file, load_registry())
    assert errors == []
    assert len(fc["features"]) == 144
    assert "model_metrics" in fc
    assert fc["model_metrics"]["val_roc_auc"] is not None
    sample_props = fc["features"][0]["properties"]
    for key in ("cell_id", "ignition_prob", "risk_pct", "risk_level", "drivers", "recommended_action"):
        assert key in sample_props
