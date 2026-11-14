"""Tests for the pipeline per episode (W4-B5)."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import config
import make_manifest
import validate

ROOT = Path(__file__).resolve().parents[2]

DOC = {
    "updated_at": "2026-02-14T08:00:00Z",
    "default": "chile",
    "episodes": [
        {"id": "chile", "name": "Chile", "bbox": [-72.0, -38.0, -70.0, -33.0], "start": "2026-02-01",
         "end": "2026-02-14", "dir": "processed", "manifest": "manifest.json"},
        {"id": "la", "name": "Los Angeles", "bbox": [-119.0, 33.6, -117.4, 34.6], "start": "2025-01-06",
         "end": "2025-01-16", "dir": "episodes/la", "manifest": "episodes/la/manifest.json", "skip": ["osm"]},
    ],
}


# --- config -------------------------------------------------------------------

def test_default_episode_when_none_selected():
    assert config.resolve_episode(DOC)["id"] == "chile"


def test_selected_episode():
    assert config.resolve_episode(DOC, "la")["bbox"] == [-119.0, 33.6, -117.4, 34.6]


def test_unknown_episode_stops_with_the_known_ones():
    with pytest.raises(SystemExit, match="chile, la"):
        config.resolve_episode(DOC, "mars")


def test_without_episodes_file_falls_back_to_chile():
    assert config.resolve_episode(None) == config.FALLBACK_EPISODE
    with pytest.raises(SystemExit):
        config.resolve_episode(None, "la")


def test_episode_paths(tmp_path):
    chile = config.episode_paths(DOC["episodes"][0], tmp_path)
    assert chile == {"raw": tmp_path / "data/raw", "processed": tmp_path / "web/data/processed",
                     "manifest": tmp_path / "web/data/manifest.json"}
    la = config.episode_paths(DOC["episodes"][1], tmp_path)
    assert la == {"raw": tmp_path / "data/raw/episodes/la", "processed": tmp_path / "web/data/episodes/la",
                  "manifest": tmp_path / "web/data/episodes/la/manifest.json"}


def test_published_episodes_file_selects_each_episode():
    """The real web/data/episodes.json: every episode resolves, through the EPISODE variable like make does."""
    doc = json.loads(config.EPISODES_FILE.read_text())
    for episode in doc["episodes"]:
        env = {**os.environ, "EPISODE": episode["id"]}
        out = subprocess.run([sys.executable, "scripts/config.py"], cwd=ROOT, env=env,
                             capture_output=True, text=True, check=True).stdout
        assert f"Episode {episode['id']}" in out
        skip = subprocess.run([sys.executable, "scripts/config.py", "skip"], cwd=ROOT, env=env,
                              capture_output=True, text=True, check=True).stdout.split()
        assert skip == sorted(episode.get("skip", []))


# --- manifest -------------------------------------------------------------------

def test_manifest_points_at_the_episode_folder(tmp_path):
    folder = tmp_path / "episodes/la"
    folder.mkdir(parents=True)
    (folder / "hotspots.geojson").write_text(json.dumps(
        {"type": "FeatureCollection", "updated_at": "2026-02-14T08:00:00Z", "features": []}))
    manifest = make_manifest.build_manifest(tmp_path, subdir="episodes/la")
    assert [(layer["id"], layer["file"]) for layer in manifest["layers"]] == [("hotspots", "episodes/la/hotspots.geojson")]

    (folder / "manifest.json").write_text(json.dumps(manifest))
    assert validate.validate_file(folder / "manifest.json", validate.load_registry(), tmp_path) == []


# --- validator ----------------------------------------------------------------

@pytest.fixture
def data_dir(tmp_path):
    (tmp_path / "processed").mkdir()
    (tmp_path / "manifest.json").write_text("{}")
    (tmp_path / "episodes/la").mkdir(parents=True)
    (tmp_path / "episodes/la/manifest.json").write_text("{}")
    return tmp_path


def errors_for(doc, data_dir):
    path = data_dir / "episodes.json"
    path.write_text(json.dumps(doc))
    return validate.validate_file(path, validate.load_registry(), data_dir)


def test_valid_episodes_pass(data_dir):
    assert errors_for(DOC, data_dir) == []


def test_episode_not_generated_fails(data_dir):
    (data_dir / "episodes/la/manifest.json").unlink()
    assert any("make data EPISODE=la" in e for e in errors_for(DOC, data_dir))


@pytest.mark.parametrize("change, expected", [
    (lambda d: d.update(default="mars"), "default"),
    (lambda d: d["episodes"].append(dict(d["episodes"][1])), "duplicate id"),
    (lambda d: d["episodes"][1].update(bbox=[-117.4, 33.6, -119.0, 34.6]), "west < east"),
    (lambda d: d["episodes"][1].update(start="2025-02-01"), "start is after end"),
    (lambda d: d["episodes"][1].update(id="Los Angeles"), "does not match"),
    (lambda d: d["episodes"][1].pop("bbox"), "'bbox' is a required property"),
])
def test_broken_episodes_fail(data_dir, change, expected):
    doc = json.loads(json.dumps(DOC))
    change(doc)
    assert any(expected in e for e in errors_for(doc, data_dir)), errors_for(doc, data_dir)
