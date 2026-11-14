import json
from pathlib import Path
from scripts.risk_ml import train_and_export_risk_model

def test_risk_ml_output(tmp_path):
    processed_dir = tmp_path / "processed"
    train_and_export_risk_model(processed_dir, (-72.0, -38.0, -70.0, -33.0))
    
    geojson_path = processed_dir / "ignition_risk.geojson"
    assert geojson_path.exists()
    
    data = json.loads(geojson_path.read_text())
    assert data["type"] == "FeatureCollection"
    assert "model_metrics" in data
    assert "val_roc_auc" in data["model_metrics"]
    
    for feature in data["features"]:
        assert 0 <= feature["properties"]["ignition_prob"] <= 1
