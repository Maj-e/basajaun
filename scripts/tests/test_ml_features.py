"""
Tests unitarios para el módulo IA1 (scripts/ml_features.py).
Valida dimensiones de la malla, ausencia de NaNs y etiquetas binarias.

El directorio es sintético: un solo foco dentro del bbox. Las tres
comprobaciones no necesitan las capas reales (roads.geojson pesa megabytes
y el cálculo de distancias alarga la suite varios minutos).
"""

import json
from pathlib import Path

import numpy as np
import pytest

from ml_features import build_episode_dataset


@pytest.fixture
def mock_episode_env(tmp_path: Path):
    """BBOX de Chile y un hotspot, para que y tenga 0 y 1."""
    bbox = (-72.0, -38.0, -70.0, -33.0)
    hotspots = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [-71.0, -35.5]},
                "properties": {"timestamp_utc": "2026-02-02T12:00:00Z"},
            }
        ],
    }
    (tmp_path / "hotspots.geojson").write_text(json.dumps(hotspots), encoding="utf-8")
    return tmp_path, bbox


def test_build_episode_dataset_dimensions(mock_episode_env):
    """Valida que la malla 12x12 genere exactamente 144 registros y dimensiones correctas."""
    processed_dir, bbox = mock_episode_env
    X, y, records, feature_names = build_episode_dataset(processed_dir, bbox)

    # 12 * 12 celdas = 144 muestras esperadas
    assert X.shape[0] == 144
    assert len(y) == 144
    assert len(records) == 144
    assert len(feature_names) == X.shape[1]
    assert X.shape[1] > 0


def test_build_episode_dataset_no_nans(mock_episode_env):
    """Valida que la matriz de características y etiquetas no contengan valores NaN ni infinitos."""
    processed_dir, bbox = mock_episode_env
    X, y, records, _ = build_episode_dataset(processed_dir, bbox)

    assert not np.isnan(X).any(), "La matriz X contiene valores NaN"
    assert not np.isinf(X).any(), "La matriz X contiene valores infinitos"
    assert not np.isnan(y).any(), "El vector y contiene valores NaN"


def test_build_episode_dataset_binary_labels(mock_episode_env):
    """Valida que las etiquetas de ignición sean estrictamente binarias {0, 1}."""
    processed_dir, bbox = mock_episode_env
    _, y, _, _ = build_episode_dataset(processed_dir, bbox)

    unique_labels = set(np.unique(y))
    assert unique_labels.issubset(
        {0, 1}
    ), f"Las etiquetas contienen valores no binarios: {unique_labels}"