"""Tests for the end-to-end site check (W2-B4), against a fake site served locally."""
import functools
import json
import shutil
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

import check_site

VALID = Path(__file__).parent / "fixtures" / "contract" / "valid"

CONFIG_JS = """export const CONFIG = {
  dataRoot: "data/",
  manifest: "data/manifest.json",
  dailySummary: "data/processed/daily_summary.json",
  land: "data/static/land.geojson",
  tiles: "https://example.org/{z}/{x}/{y}.jpg",
};
"""


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


@pytest.fixture(autouse=True)
def no_retry_wait(monkeypatch):
    monkeypatch.setattr(check_site, "RETRY_WAIT_S", 0)


@pytest.fixture
def site(tmp_path):
    """A published-like site: shell, config.js, manifest + the files it lists."""
    root = tmp_path / "web"
    (root / "data/processed").mkdir(parents=True)
    (root / "data/static").mkdir()
    (root / "index.html").write_text("<!doctype html><title>t</title>")
    (root / "config.js").write_text(CONFIG_JS)
    shutil.copy(VALID / "hotspots.geojson", root / "data/processed/hotspots.geojson")
    shutil.copy(VALID / "daily_summary.json", root / "data/processed/daily_summary.json")
    (root / "data/static/land.geojson").write_text('{"type":"FeatureCollection","features":[]}')
    manifest = json.loads((VALID / "manifest.json").read_text())
    manifest["layers"] = [dict(manifest["layers"][0], file="processed/hotspots.geojson")]
    (root / "data/manifest.json").write_text(json.dumps(manifest))

    handler = functools.partial(QuietHandler, directory=str(root))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield root, f"http://127.0.0.1:{server.server_address[1]}/"
    server.shutdown()


def failing(report):
    return {f.path: f.errors for f in report.files if f.errors}


def test_healthy_site_passes(site):
    _, url = site
    report = check_site.check_site(url, max_load_s=30)
    assert report.ok, check_site.format_report(report)
    paths = [f.path for f in report.files]
    assert {"data/manifest.json", "data/processed/hotspots.geojson",
            "data/processed/daily_summary.json", "data/static/land.geojson"} <= set(paths)
    assert all(f.first_load for f in report.files)  # hotspots layer is active


def test_missing_file_fails(site):
    root, url = site
    (root / "data/processed/hotspots.geojson").unlink()
    report = check_site.check_site(url, max_load_s=30)
    assert not report.ok
    errors = failing(report)
    assert any("404" in e for e in errors["data/processed/hotspots.geojson"])
    assert any("does not exist" in e for e in errors["data/manifest.json"])


def test_off_contract_file_fails(site):
    root, url = site
    path = root / "data/processed/hotspots.geojson"
    data = json.loads(path.read_text())
    data["features"][0]["properties"]["confidence"] = "alta"
    path.write_text(json.dumps(data))
    report = check_site.check_site(url, max_load_s=30)
    assert not report.ok
    assert any("confidence" in e for e in failing(report)["data/processed/hotspots.geojson"])


def test_broken_json_fails(site):
    root, url = site
    (root / "data/processed/daily_summary.json").write_text("{truncated")
    report = check_site.check_site(url, max_load_s=30)
    assert any("invalid JSON" in e for e in failing(report)["data/processed/daily_summary.json"])


def test_broken_static_asset_fails(site):
    root, url = site
    (root / "data/static/land.geojson").write_text("<html>404</html>")
    report = check_site.check_site(url, max_load_s=30)
    assert "data/static/land.geojson" in failing(report)


def test_missing_manifest_fails(site):
    root, url = site
    (root / "data/manifest.json").unlink()
    report = check_site.check_site(url, max_load_s=30)
    assert "data/manifest.json" in failing(report)


def test_inactive_layer_is_checked_but_not_first_load(site):
    root, url = site
    shutil.copy(VALID / "weather.geojson", root / "data/processed/weather.geojson")
    manifest = json.loads((root / "data/manifest.json").read_text())
    manifest["layers"].append({"id": "weather", "name": "Weather", "file": "processed/weather.geojson",
                               "type": "circle", "temporal": True, "active": False})
    (root / "data/manifest.json").write_text(json.dumps(manifest))
    report = check_site.check_site(url, max_load_s=30)
    assert report.ok, check_site.format_report(report)
    [weather] = [f for f in report.files if f.path == "data/processed/weather.geojson"]
    assert not weather.first_load


def test_slow_first_load_fails(site):
    _, url = site
    report = check_site.check_site(url, max_load_s=0.0)
    assert not report.ok
    assert any("budget" in e for e in report.errors)


def test_unreachable_site_fails():
    report = check_site.check_site("http://127.0.0.1:9/", max_load_s=30)
    assert not report.ok


def test_main_exit_code_and_summary(site, tmp_path, monkeypatch, capsys):
    _, url = site
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    assert check_site.main(["--url", url, "--max-load", "30"]) == 0
    assert "RESULT: PASS" in capsys.readouterr().out
    assert "PASS" in summary.read_text()


def _publish_episodes(root, live_published):
    episodes = {"updated_at": "2026-02-14T08:00:00Z", "default": "demo", "episodes": [
        {"id": "demo", "name": "Demo", "bbox": [-72.0, -38.0, -70.0, -33.0], "start": "2026-02-01",
         "end": "2026-02-14", "dir": "processed", "manifest": "manifest.json"},
        {"id": "live", "name": "Live", "bbox": [-9.6, 35.9, 3.4, 43.9], "live": True,
         "dir": "processed/live", "manifest": "processed/live/manifest.json"}]}
    (root / "data/episodes.json").write_text(json.dumps(episodes))
    if live_published:
        live = root / "data/processed/live"
        live.mkdir(parents=True)
        shutil.copy(VALID / "hotspots.geojson", live / "hotspots.geojson")
        manifest = json.loads((root / "data/manifest.json").read_text())
        manifest["layers"] = [dict(manifest["layers"][0], file="processed/live/hotspots.geojson")]
        (live / "manifest.json").write_text(json.dumps(manifest))
    return root / "data/processed/live"


def test_unpublished_live_episode_is_only_a_note(site):
    root, url = site
    _publish_episodes(root, live_published=False)
    report = check_site.check_site(url, max_load_s=30)
    assert report.ok, check_site.format_report(report)
    assert any("not published yet" in n for n in report.notes)


def test_published_live_episode_is_validated(site):
    root, url = site
    live = _publish_episodes(root, live_published=True)
    assert check_site.check_site(url, max_load_s=30).ok
    data = json.loads((live / "hotspots.geojson").read_text())
    data["features"][0]["properties"]["confidence"] = "alta"
    (live / "hotspots.geojson").write_text(json.dumps(data))
    report = check_site.check_site(url, max_load_s=30)
    assert "data/processed/live/hotspots.geojson" in failing(report)
