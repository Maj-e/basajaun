import numpy as np
from pathlib import Path
from scripts.ml_features import build_episode_dataset

def test_build_episode_dataset_dimensions():
    X, y, records, feature_names = build_episode_dataset(Path("dummy"), (-72.0, -38.0, -70.0, -33.0))
    assert X.shape[0] == 144  # Malla 12x12
    assert len(y) == 144
    assert len(records) == 144
    assert not np.isnan(X).any()  # Sin NaNs
    assert set(np.unique(y)).issubset({0, 1})  # Etiquetas binarias
