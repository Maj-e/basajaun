"""Tests for the hourly time series (W2-B3)."""
import json

import series
import validate


def hotspot(t, frp=10.0):
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [-71.0, -35.0]},
            "properties": {"t": t, "frp": frp}}


def test_fractional_t_is_bucketed_into_whole_hours():
    # Real hotspots have t with decimals (minutes past the hour): this used to crash range()
    out = series.build_series([hotspot(491683.88), hotspot(491683.10, 5.0), hotspot(491685.5, None)])
    assert out == [
        {"t": 491683, "count": 2, "total_frp": 15.0},
        {"t": 491684, "count": 0, "total_frp": 0.0},   # zero-filled hour
        {"t": 491685, "count": 1, "total_frp": 0.0},   # null FRP counts as 0
    ]


def test_no_hotspots_gives_empty_series():
    assert series.build_series([]) == []


def test_output_file_passes_the_contract(tmp_path):
    fc = {"type": "FeatureCollection", "updated_at": "2026-02-14T08:00:00Z",
          "features": [hotspot(491683.88), hotspot(491690.2)]}
    (tmp_path / "hotspots.geojson").write_text(json.dumps(fc))
    path = series.generate_hourly_series(tmp_path)
    data = json.loads(path.read_text())
    assert len(data["series"]) == 8  # 491683 … 491690
    assert validate.validate_file(path, validate.load_registry(), tmp_path) == []


def test_skips_without_hotspots(tmp_path, capsys):
    assert series.generate_hourly_series(tmp_path) is None
    assert "[SKIP]" in capsys.readouterr().out
