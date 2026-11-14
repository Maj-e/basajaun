import sys
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import pytest

# Allow importing scripts/harmonize.py when running pytest from repo root
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harmonize import (
    CONTRACT_COLUMNS,
    normalize_modis,
    normalize_viirs,
    parse_datetime,
)


def test_parse_datetime_zero_padding():
    dt1 = parse_datetime("2026-02-14", 742)
    assert dt1 == datetime(2026, 2, 14, 7, 42, tzinfo=timezone.utc)

    dt2 = parse_datetime("2026-02-14", "5")
    assert dt2 == datetime(2026, 2, 14, 0, 5, tzinfo=timezone.utc)

    dt3 = parse_datetime("2026-02-14", 742.0)
    assert dt3 == datetime(2026, 2, 14, 7, 42, tzinfo=timezone.utc)


def test_normalize_modis_three_rows():
    raw_df = pd.DataFrame([
        {
            "latitude": -33.45691,
            "longitude": -70.64834,
            "brightness": 315.42,
            "acq_date": "2026-02-14",
            "acq_time": 742,
            "satellite": "T",
            "confidence": 20,  # < 30 -> low
            "frp": 12.34,
            "daynight": "N",
        },
        {
            "latitude": -34.1234,
            "longitude": -71.5678,
            "brightness": 330.0,
            "acq_date": "2026-02-14",
            "acq_time": 1315,
            "satellite": "A",
            "confidence": 55,  # 30-79 -> medium
            "frp": 65.8,
            "daynight": "D",
        },
        {
            "latitude": -35.0,
            "longitude": -71.0,
            "brightness": 389.9,
            "acq_date": "2026-02-14",
            "acq_time": 5,
            "satellite": "Terra",
            "confidence": 92,  # >= 80 -> high
            "frp": 250.0,
            "daynight": "N",
        },
    ])

    result = normalize_modis(raw_df)

    assert list(result.columns) == CONTRACT_COLUMNS
    assert len(result) == 3
    assert set(result["confidence"]).issubset({"low", "medium", "high"})
    assert list(result["confidence"]) == ["low", "medium", "high"]
    assert list(result["satellite"]) == ["Terra", "Aqua", "Terra"]
    assert list(result["timestamp_utc"]) == [
        "2026-02-14T07:42:00Z",
        "2026-02-14T13:15:00Z",
        "2026-02-14T00:05:00Z",
    ]
    assert (result["resolution_m"] == 1000).all()
    assert (result["border"] == "#ffffff").all()
    assert result.iloc[0]["lat"] == -33.4569
    assert result.iloc[0]["lon"] == -70.6483
    assert result.iloc[0]["detected_by"] == ["MODIS"]
    assert pd.isna(result.iloc[0]["fire_id"])


def test_normalize_viirs_three_rows():
    raw_df = pd.DataFrame([
        {
            "latitude": -33.4569,
            "longitude": -70.6483,
            "bright_ti4": 320.1,
            "acq_date": "2026-02-14",
            "acq_time": 742,
            "satellite": "N",
            "confidence": "l",
            "frp": 8.2,
            "daynight": "N",
        },
        {
            "latitude": -34.2222,
            "longitude": -71.1111,
            "bright_ti4": 342.1,
            "acq_date": "2026-02-14",
            "acq_time": 1430,
            "satellite": "N20",
            "confidence": "nominal",
            "frp": 45.0,
            "daynight": "D",
        },
        {
            "latitude": -35.5555,
            "longitude": -71.9999,
            "bright_ti4": 367.8,
            "acq_date": "2026-02-14",
            "acq_time": 2105,
            "satellite": "1",
            "confidence": "h",
            "frp": 180.5,
            "daynight": "N",
        },
    ])

    result = normalize_viirs(raw_df)

    assert list(result.columns) == CONTRACT_COLUMNS
    assert len(result) == 3
    assert set(result["confidence"]).issubset({"low", "medium", "high"})
    assert list(result["confidence"]) == ["low", "medium", "high"]
    assert list(result["satellite"]) == ["S-NPP", "NOAA-20", "NOAA-20"]
    assert (result["resolution_m"] == 375).all()
    assert (result["border"] == "#222222").all()
    assert result.iloc[0]["id"] == "VIIRS_N_20260214_0742_-33.4569_-70.6483"
    assert result.iloc[1]["brightness_k"] == 342.1
    assert result.iloc[2]["color"] == "#d7301f"


def test_normalize_viirs_explicit_satellite():
    raw_df = pd.DataFrame([
        {
            "latitude": -33.5,
            "longitude": -70.6,
            "bright_ti4": 350.0,
            "acq_date": "2026-02-14",
            "acq_time": 900,
            "satellite": "N21",
            "confidence": "high",
            "frp": 30.0,
            "daynight": "D",
        }
    ])

    result = normalize_viirs(raw_df, satellite="NOAA-21")
    assert result.iloc[0]["satellite"] == "NOAA-21"
    assert result.iloc[0]["id"].startswith("VIIRS_N21_")


def test_empty_dataframes_preserve_contract_columns():
    empty_modis = normalize_modis(pd.DataFrame())
    empty_viirs = normalize_viirs(pd.DataFrame())

    assert empty_modis.empty
    assert list(empty_modis.columns) == CONTRACT_COLUMNS
    assert empty_viirs.empty
    assert list(empty_viirs.columns) == CONTRACT_COLUMNS


def test_invalid_viirs_confidence_raises():
    bad_df = pd.DataFrame([
        {
            "latitude": -33.5,
            "longitude": -70.6,
            "bright_ti4": 350.0,
            "acq_date": "2026-02-14",
            "acq_time": 900,
            "satellite": "N20",
            "confidence": "unknown",
            "frp": 30.0,
            "daynight": "D",
        }
    ])

    with pytest.raises(ValueError, match="Unknown VIIRS confidence value"):
        normalize_viirs(bad_df)