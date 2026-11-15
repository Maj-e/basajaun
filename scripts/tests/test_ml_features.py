"""
Tests unitarios para el módulo IA1 (scripts/ml_features.py).

El directorio es sintético: dos días con temperaturas distintas, un foco
solo en uno de ellos y un tramo corto de carretera. Así se comprueba el
dataset diario sin leer las capas reales (roads.geojson pesa megabytes).
"""

import json
from pathlib import Path

import numpy as np
import pytest
from shapely.geometry import Point

from ml_features import build_episode_dataset


@pytest.fixture
def mock_episode_env(tmp_path: Path):
    """BBOX de Chile, dos días de tiempo y un hotspot en un solo día."""
    bbox = (-72.0, -38.0, -70.0, -33.0)
    # Interior de una celda (no cae en el borde, donde within no cuenta).
    hotspot = (-71.08, -35.4)
    weather = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [-71.0, -35.5]},
                "properties": {
                    "timestamp_utc": "2026-02-01T12:00:00Z",
                    "temperature": 18.0,
                    "humidity": 60.0,
                    "speed": 10.0,
                    "rain": 0.0,
                },
            },
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [-71.0, -35.5]},
                "properties": {
                    "timestamp_utc": "2026-02-02T12:00:00Z",
                    "temperature": 34.0,
                    "humidity": 25.0,
                    "speed": 28.0,
                    "rain": 0.0,
                },
            },
        ],
    }
    hotspots = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": list(hotspot)},
                "properties": {"timestamp_utc": "2026-02-02T15:00:00Z"},
            }
        ],
    }
    # Tramo corto en la esquina suroeste: las celdas no pueden quedar a la misma distancia.
    roads = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[-71.99, -37.99], [-71.95, -37.95]],
                },
                "properties": {"highway": "track"},
            }
        ],
    }
    (tmp_path / "weather.geojson").write_text(json.dumps(weather), encoding="utf-8")
    (tmp_path / "hotspots.geojson").write_text(json.dumps(hotspots), encoding="utf-8")
    (tmp_path / "roads.geojson").write_text(json.dumps(roads), encoding="utf-8")
    return tmp_path, bbox, hotspot


def test_build_episode_dataset_daily_rows(mock_episode_env):
    """144 filas por día, temperatura que varía, y cada record con day y geometry."""
    processed_dir, bbox, _hotspot = mock_episode_env
    X, y, records, feature_names = build_episode_dataset(processed_dir, bbox)

    n_days = 2
    assert len(records) == 144 * n_days
    assert X.shape[0] == 144 * n_days
    assert len(y) == 144 * n_days
    assert len(feature_names) == X.shape[1]

    temp = X[:, feature_names.index("temp_max")]
    assert float(np.std(temp)) > 0

    assert all("day" in rec and "geometry" in rec["cell"] for rec in records)
    assert {rec["cell"]["cell_id"] for rec in records} == {f"SEC-{i:03d}" for i in range(1, 145)}


def test_build_episode_dataset_labels_one_cell_day(mock_episode_env):
    """El foco etiqueta una sola celda y solo su día."""
    processed_dir, bbox, hotspot = mock_episode_env
    _X, y, records, _names = build_episode_dataset(processed_dir, bbox)

    assert int(y.sum()) == 1
    hit = records[int(np.flatnonzero(y)[0])]
    assert hit["day"] == "2026-02-02"
    assert hit["cell"]["geometry"].covers(Point(hotspot))
    day_one = [int(y[i]) for i, rec in enumerate(records) if rec["day"] == "2026-02-01"]
    assert day_one and sum(day_one) == 0


def test_build_episode_dataset_road_distances_and_population(mock_episode_env):
    """Distancias a carretera en metros y no constantes. Sin population.tif, densidad 0."""
    processed_dir, bbox, _hotspot = mock_episode_env
    X, _y, _records, feature_names = build_episode_dataset(processed_dir, bbox)

    roads = X[:, feature_names.index("dist_roads_m")]
    assert np.isfinite(roads).all()
    assert float(np.std(roads)) > 0
    assert float(roads.max()) > 1000.0

    # Capas ausentes: el defecto del respaldo, 25 km, pasado a metros.
    assert np.all(X[:, feature_names.index("dist_stations_m")] == 25_000.0)
    assert np.all(X[:, feature_names.index("dist_water_m")] == 25_000.0)
    assert np.all(X[:, feature_names.index("pop_density")] == 0.0)


def test_build_episode_dataset_requires_weather(tmp_path: Path):
    """Sin weather.geojson no se inventa un día a 28,5 °C."""
    bbox = (-72.0, -38.0, -70.0, -33.0)
    with pytest.raises(ValueError):
        build_episode_dataset(tmp_path, bbox)


def test_build_episode_dataset_no_nans(mock_episode_env):
    """La matriz de características y las etiquetas no contienen NaN ni infinitos."""
    processed_dir, bbox, _hotspot = mock_episode_env
    X, y, _records, _names = build_episode_dataset(processed_dir, bbox)

    assert not np.isnan(X).any(), "La matriz X contiene valores NaN"
    assert not np.isinf(X).any(), "La matriz X contiene valores infinitos"
    assert not np.isnan(y).any(), "El vector y contiene valores NaN"


def test_build_episode_dataset_binary_labels(mock_episode_env):
    """Las etiquetas de ignición son estrictamente binarias {0, 1}."""
    processed_dir, bbox, _hotspot = mock_episode_env
    _X, y, _records, _names = build_episode_dataset(processed_dir, bbox)

    unique_labels = set(np.unique(y))
    assert unique_labels.issubset({0, 1}), f"Las etiquetas contienen valores no binarios: {unique_labels}"
