import numpy as np
from pathlib import Path

def build_episode_dataset(processed_dir: Path, bbox: tuple) -> tuple:
    '''
    Extrae características sobre una malla 12x12 (contrato IA1 -> IA2).
    Devuelve (X, y, records, feature_names) sin NaNs.
    '''
    # Simulación de la malla 12x12 = 144 celdas
    X = np.random.rand(144, 8)
    y = np.random.randint(0, 2, 144)
    records = [{"cell_id": f"cell_{i}", "reference_date": "2026-02-01"} for i in range(144)]
    feature_names = [
        "temp_max", "humidity_min", "wind_max", "rain_sum", 
        "fwi_30_30_30", "dist_roads", "dist_water", "pop_density"
    ]
    return X, y, records, feature_names
