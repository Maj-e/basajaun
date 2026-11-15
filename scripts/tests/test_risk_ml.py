"""Unit tests for scripts/risk_ml.py (IA2 municipal ignition risk model)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from risk_ml import (
    apply_platt_calibrator,
    brier_score_np,
    classify_risk_tier,
    compute_local_contributions,
    fit_logistic_l2,
    fit_platt_calibrator,
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


def test_platt_calibration_improves_brier_without_changing_auc():
    rng = np.random.default_rng(21)
    y = np.array([0] * 180 + [1] * 20)
    raw_probs = np.where(y == 1, rng.uniform(0.65, 0.95, size=200), rng.uniform(0.35, 0.64, size=200))
    a, b = fit_platt_calibrator(raw_probs, y)
    cal_probs = apply_platt_calibrator(raw_probs, a, b)
    assert roc_auc_score_np(y, cal_probs) == roc_auc_score_np(y, raw_probs)
    assert brier_score_np(y, cal_probs) < brier_score_np(y, raw_probs)


def test_local_contributions_rank_dominant_driver():
    X = np.array([[0.0, 0.0], [3.0, -1.0]])
    params = np.array([1.5, -0.5, 0.0])
    mean = np.array([0.0, 0.0])
    std = np.array([1.0, 1.0])
    contribs = compute_local_contributions(X, params, mean, std, ["temp_max", "humidity_min"], top_k=2)
    assert contribs[0] == []
    assert contribs[1][0]["feature"] == "temp_max"
    assert contribs[1][0]["share_pct"] == 90.0

def test_risk_tier_thresholds():
    # Umbrales absolutos (episodios de alta incidencia)
    assert classify_risk_tier(0.42, base_rate=0.15) == "critical"
    assert classify_risk_tier(0.24, base_rate=0.15) == "high"
    assert classify_risk_tier(0.11, base_rate=0.15) == "moderate"
    assert classify_risk_tier(0.03, base_rate=0.15) == "low"

    assert classify_risk_tier(0.14, base_rate=0.015) == "critical"
    assert classify_risk_tier(0.075, base_rate=0.015) == "high"
    assert classify_risk_tier(0.035, base_rate=0.015) == "moderate"
    assert classify_risk_tier(0.01, base_rate=0.015) == "low"

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
    assert fc["model_metrics"]["val_roc_auc"] is not None
    assert fc["model_metrics"]["brier_score"] is not None
    sample_props = fc["features"][0]["properties"]
    for key in ("cell_id", "ignition_prob", "risk_pct", "risk_level", "top_drivers", "drivers", "recommended_action", "color", "opacity"):
        assert key in sample_props
    assert sample_props["color"] == sample_props["fill"]
    assert sample_props["opacity"] == 0.42


def test_run_risk_model_accepts_ia1_dataset(tmp_path: Path, monkeypatch):
    """El episodio mínimo de IA1 entra por el normalizador: el respaldo no se llama."""
    bbox = (-72.0, -38.0, -70.0, -33.0)
    weather = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [-71.0, -35.5]},
                "properties": {
                    "timestamp_utc": day,
                    "temperature": temp,
                    "humidity": 40.0,
                    "speed": 12.0,
                    "rain": 0.0,
                },
            }
            for day, temp in (("2026-02-01T12:00:00Z", 18.0), ("2026-02-02T12:00:00Z", 34.0))
        ],
    }
    hotspots = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [-71.08, -35.4]},
                "properties": {"timestamp_utc": "2026-02-02T15:00:00Z", "confidence": "high", "frp": 45.0},
            }
        ],
    }
    (tmp_path / "weather.geojson").write_text(json.dumps(weather), encoding="utf-8")
    (tmp_path / "hotspots.geojson").write_text(json.dumps(hotspots), encoding="utf-8")

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("_fallback_build_dataset no debe ejecutarse")

    monkeypatch.setattr("risk_ml._fallback_build_dataset", fail_if_called)

    fc = run_risk_model(tmp_path, bbox)
    assert len(fc["features"]) == 144
    assert {f["properties"]["cell_id"] for f in fc["features"]} == {f"SEC-{i:03d}" for i in range(1, 145)}
