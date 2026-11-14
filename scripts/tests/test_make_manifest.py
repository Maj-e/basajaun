"""Tests for the manifest generator (W1-B4)."""
import json

import make_manifest
import validate


def test_only_existing_files_are_listed(tmp_path):
    (tmp_path / "processed").mkdir()
    (tmp_path / "processed/meteo.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "updated": "2026-02-14T08:00:00Z", "features": []})
    )
    manifest = make_manifest.build_manifest(tmp_path)

    ids = [layer["id"] for layer in manifest["layers"]]
    assert ids == ["wind", "weather"]  # both read meteo.geojson; nothing else exists
    assert all(layer["updated"] == "2026-02-14T08:00:00Z" for layer in manifest["layers"])


def test_empty_data_dir_gives_empty_manifest(tmp_path):
    assert make_manifest.build_manifest(tmp_path)["layers"] == []


def test_updated_falls_back_to_mtime(tmp_path):
    (tmp_path / "processed").mkdir()
    (tmp_path / "processed/population.png").write_bytes(b"png")
    [layer] = make_manifest.build_manifest(tmp_path)["layers"]
    assert layer["id"] == "population"
    assert layer["updated"].endswith("Z")


def test_every_registered_layer_passes_the_schema(tmp_path):
    """If every file existed, the generated manifest must satisfy the contract."""
    for layer in make_manifest.LAYERS:
        path = tmp_path / layer["file"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"type": "FeatureCollection", "updated": "2026-02-14T08:00:00Z",
                                    "features": []}))
    manifest = make_manifest.build_manifest(tmp_path)
    assert len(manifest["layers"]) == len(make_manifest.LAYERS)

    out = tmp_path / "manifest.json"
    out.write_text(json.dumps(manifest))
    assert validate.validate_file(out, validate.load_registry(), tmp_path) == []
