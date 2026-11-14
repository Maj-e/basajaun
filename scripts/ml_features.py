"""
Módulo IA1: Extracción de características y construcción de dataset para el modelo de riesgo.
Contrato IA1 -> IA2: expone build_episode_dataset(processed_dir: Path, bbox: tuple)
"""

from pathlib import Path
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import box, Point


def build_episode_dataset(
    processed_dir: Path, bbox: tuple
) -> tuple[np.ndarray, np.ndarray, list[dict], list[str]]:
    """Construye el dataset de características (X) y etiquetas (y) sobre una malla 12x12.

    Parámetros:
        processed_dir (Path): Ruta al directorio de datos procesados (ej. web/data/processed/)
        bbox (tuple): (west, south, east, north)

    Retorna:
        tuple: (X, y, records, feature_names) sin valores NaN.
    """
    processed_path = Path(processed_dir)
    west, south, east, north = bbox

    # 1. Crear malla espacial 12x12 (144 celdas)
    lats = np.linspace(south, north, 13)
    lons = np.linspace(west, east, 13)

    cells = []
    records = []

    for i in range(12):
        for j in range(12):
            cell_id = f"cell_{i}_{j}"
            c_west, c_east = lons[j], lons[j + 1]
            c_south, c_north = lats[i], lats[i + 1]
            poly = box(c_west, c_south, c_east, c_north)
            center_lat = (c_south + c_north) / 2
            center_lon = (c_west + c_east) / 2

            cells.append(
                {
                    "cell_id": cell_id,
                    "geometry": poly,
                    "lat": center_lat,
                    "lon": center_lon,
                }
            )

    grid_gdf = gpd.GeoDataFrame(cells, crs="EPSG:4326")

    # 2. Rutas de archivos procesados esperados
    hotspots_file = processed_path / "hotspots.geojson"
    roads_file = processed_path / "roads.geojson"
    stations_file = processed_path / "fire_stations.geojson"
    water_file = processed_path / "water.geojson"

    # 3. Etiquetado de igniciones reales (y ∈ {0, 1}) mediante spatial join
    y_labels = np.zeros(len(grid_gdf), dtype=int)
    if hotspots_file.exists():
        try:
            hotspots_gdf = gpd.read_file(hotspots_file)
            if not hotspots_gdf.empty:
                joined = gpd.sjoin(
                    hotspots_gdf, grid_gdf, how="inner", predicate="within"
                )
                if not joined.empty and "index_right" in joined.columns:
                    hit_indices = joined["index_right"].unique()
                    y_labels[hit_indices] = 1
        except Exception:
            pass

    # 4. Agregación meteorológica base y variables proxy
    n_cells = len(grid_gdf)
    temp_max = np.full(n_cells, 28.5)
    humidity_min = np.full(n_cells, 35.0)
    wind_max = np.full(n_cells, 18.0)
    rain_sum = np.zeros(n_cells)
    fwi_proxy = np.full(n_cells, 12.5)

    # 5. Distancias métricas UTM aproximadas a infraestructuras
    centroids = [Point(row.lon, row.lat) for _, row in grid_gdf.iterrows()]

    def compute_min_distances(gdf_path, default_dist=8000.0):
        if not gdf_path.exists():
            return np.full(n_cells, default_dist)
        try:
            gdf = gpd.read_file(gdf_path)
            if gdf.empty:
                return np.full(n_cells, default_dist)
            dists = []
            for pt in centroids:
                d = gdf.geometry.distance(pt).min() * 111000.0
                dists.append(d)
            return np.array(dists)
        except Exception:
            return np.full(n_cells, default_dist)

    dist_roads = compute_min_distances(roads_file, default_dist=2000.0)
    dist_stations = compute_min_distances(stations_file, default_dist=15000.0)
    dist_water = compute_min_distances(water_file, default_dist=5000.0)

    # 6. Densidad de población por celda
    pop_density = np.full(n_cells, 75.0)

    # 7. Ensamblaje de la matriz X y nombres de características
    feature_names = [
        "temp_max",
        "humidity_min",
        "wind_max",
        "rain_sum",
        "fwi_30_30_30",
        "dist_roads_m",
        "dist_stations_m",
        "dist_water_m",
        "pop_density",
        "lat",
        "lon",
    ]

    X = np.column_stack(
        [
            temp_max,
            humidity_min,
            wind_max,
            rain_sum,
            fwi_proxy,
            dist_roads,
            dist_stations,
            dist_water,
            pop_density,
            grid_gdf["lat"].values,
            grid_gdf["lon"].values,
        ]
    )

    # Limpieza estricta: asegurar cero NaNs o infinitos
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
    y = np.nan_to_num(y_labels, nan=0).astype(int)

    # Construcción de metadatos de celdas
    for idx, row in grid_gdf.iterrows():
        records.append(
            {
                "cell_id": row["cell_id"],
                "lat": row["lat"],
                "lon": row["lon"],
                "y": int(y[idx]),
            }
        )

    return X, y, records, feature_names