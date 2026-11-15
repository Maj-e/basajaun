"""
Módulo IA1: extracción de características y construcción del dataset de riesgo.

Contrato IA1 -> IA2: build_episode_dataset(processed_dir, bbox) devuelve
(X, y, records, feature_names) sin NaN. Una fila por celda y día, con la
misma malla 12x12 (SEC-001 … SEC-144) que usa el modelo.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import geopandas as gpd
import numpy as np
import pyproj
from shapely.geometry import box

GRID_COLS = 12
GRID_ROWS = 12

# Misma distancia que _min_distance_km cuando la capa no existe o está vacía.
DEFAULT_DIST_M = 25_000.0

FEATURE_NAMES = [
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


def _utm_epsg(lon: float, lat: float) -> int:
    """Zona UTM del centro del bbox. La misma regla que risk_ml._utm_transformer."""
    zone = int((lon + 180.0) / 6.0) + 1
    return (32600 if lat >= 0 else 32700) + zone


def _build_grid(bbox: tuple[float, float, float, float]) -> list[dict]:
    """12x12 celdas con los mismos cortes e identificadores que risk_ml._build_grid."""
    west, south, east, north = bbox
    dx = (east - west) / GRID_COLS
    dy = (north - south) / GRID_ROWS
    cells = []
    cid = 1
    for r in range(GRID_ROWS):
        for c in range(GRID_COLS):
            x0 = west + c * dx
            y0 = south + r * dy
            cells.append({
                "cell_id": f"SEC-{cid:03d}",
                "lon": round(x0 + dx / 2.0, 5),
                "lat": round(y0 + dy / 2.0, 5),
                "geometry": box(x0, y0, x0 + dx, y0 + dy),
            })
            cid += 1
    return cells


def _as_float(value) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _load_weather_by_day(path: Path) -> dict[str, list[dict]]:
    """Agrega cada punto meteorológico por día: max temp, min humedad, max viento, suma de lluvia.

    Sin archivo, o sin ningún día con coordenadas y marca de tiempo, no hay
    con qué entrenar: se lanza ValueError en lugar de rellenar 28,5 °C.
    """
    if not path.is_file():
        raise ValueError("No daily weather records found to train ignition risk model.")

    fc = json.loads(path.read_text(encoding="utf-8"))
    by_point: dict[tuple[str, float, float], dict] = {}
    for feat in fc.get("features", []):
        props = feat.get("properties") or {}
        coords = (feat.get("geometry") or {}).get("coordinates") or []
        ts = props.get("timestamp_utc") or ""
        if len(coords) < 2 or len(str(ts)) < 10:
            continue
        day = str(ts)[:10]
        lon, lat = round(float(coords[0]), 4), round(float(coords[1]), 4)
        rec = by_point.setdefault((day, lon, lat), {
            "lon": lon,
            "lat": lat,
            "temp_max": -99.0,
            "humidity_min": 100.0,
            "wind_max": 0.0,
            "rain_sum": 0.0,
        })
        temperature = _as_float(props.get("temperature"))
        humidity = _as_float(props.get("humidity"))
        speed = _as_float(props.get("speed"))
        rain = _as_float(props.get("rain"))
        if temperature is not None:
            rec["temp_max"] = max(rec["temp_max"], temperature)
        if humidity is not None:
            rec["humidity_min"] = min(rec["humidity_min"], humidity)
        if speed is not None:
            rec["wind_max"] = max(rec["wind_max"], speed)
        if rain is not None:
            rec["rain_sum"] += rain

    by_day: dict[str, list[dict]] = defaultdict(list)
    for (day, _, _), rec in by_point.items():
        # Un punto sin ninguna lectura de temperatura no puede quedar en -99.
        if rec["temp_max"] < -50:
            rec["temp_max"] = 25.0
        by_day[day].append(rec)

    if not by_day:
        raise ValueError("No daily weather records found to train ignition risk model.")
    return by_day


def _fwi_30_30_30(temp: np.ndarray, humidity: np.ndarray, wind: np.ndarray, rain: np.ndarray) -> np.ndarray:
    """La misma fórmula que el constructor de respaldo de IA2."""
    return (
        np.maximum(0.0, temp - 20.0) / 15.0
        + np.maximum(0.0, 50.0 - humidity) / 35.0
        + wind / 35.0
        - np.minimum(rain, 5.0) * 0.4
    )


def _nearest_station_index(cell_lon: np.ndarray, cell_lat: np.ndarray, stations: list[dict]) -> np.ndarray:
    xy = np.array([[s["lon"], s["lat"]] for s in stations], dtype=float)
    d2 = (cell_lon[:, None] - xy[None, :, 0]) ** 2 + (cell_lat[:, None] - xy[None, :, 1]) ** 2
    return d2.argmin(axis=1)


def _distances_m(grid_utm: gpd.GeoDataFrame, path: Path) -> np.ndarray:
    """Distancia en metros de cada celda a la geometría más cercana, calculada una sola vez.

    La capa se proyecta una vez a la UTM del grid (pyproj) y se mide con
    sjoin_nearest. Si el archivo no existe o no tiene geometría, 25 km.
    """
    n = len(grid_utm)
    fallback = np.full(n, DEFAULT_DIST_M)
    if not path.is_file():
        return fallback
    try:
        layer = gpd.read_file(path)
    except Exception:
        return fallback
    if layer.empty:
        return fallback
    layer = layer[layer.geometry.notna()]
    layer = layer[~layer.geometry.is_empty]
    if layer.empty:
        return fallback
    if layer.crs is None:
        layer = layer.set_crs("EPSG:4326")
    layer_utm = layer.to_crs(grid_utm.crs)
    joined = gpd.sjoin_nearest(
        grid_utm[["geometry"]],
        layer_utm[["geometry"]],
        how="left",
        distance_col="dist_m",
    )
    # Un empate devuelve varias filas por celda: nos quedamos con la menor.
    dist = joined["dist_m"].groupby(level=0).min()
    values = dist.reindex(grid_utm.index).to_numpy(dtype=float)
    return np.where(np.isfinite(values), values, DEFAULT_DIST_M)


def _population_density(path: Path, cells: list[dict]) -> np.ndarray:
    """Media de los valores no negativos de population.tif dentro de cada celda.

    Sin tif la densidad es 0. No se rellena con 75 hab/km².
    """
    out = np.zeros(len(cells), dtype=float)
    if not path.is_file():
        return out
    try:
        import rasterio
    except Exception:
        return out
    try:
        with rasterio.open(path) as src:
            for i, cell in enumerate(cells):
                minx, miny, maxx, maxy = cell["geometry"].bounds
                window = src.window(minx, miny, maxx, maxy)
                arr = src.read(1, window=window, masked=True)
                if arr.count() == 0:
                    continue
                out[i] = float(np.maximum(arr.compressed(), 0.0).mean())
    except Exception:
        return np.zeros(len(cells), dtype=float)
    return out


def _ignition_by_day(path: Path, grid: gpd.GeoDataFrame, days: list[str]) -> dict[str, np.ndarray]:
    """y = 1 solo en la celda que contiene un foco de ese día. Otro día no etiqueta."""
    labels = {day: np.zeros(len(grid), dtype=int) for day in days}
    if not path.is_file():
        return labels
    try:
        hotspots = gpd.read_file(path)
    except Exception:
        return labels
    if hotspots.empty or "timestamp_utc" not in hotspots.columns:
        return labels
    hotspots = hotspots[hotspots.geometry.notna()]
    hotspots = hotspots[~hotspots.geometry.is_empty]
    if hotspots.empty:
        return labels
    hotspots = hotspots.copy()
    hotspots["day"] = hotspots["timestamp_utc"].astype(str).str.slice(0, 10)
    hotspots = hotspots[hotspots["day"].isin(days)]
    if hotspots.empty:
        return labels
    if hotspots.crs is None:
        hotspots = hotspots.set_crs("EPSG:4326")
    joined = gpd.sjoin(hotspots, grid, how="inner", predicate="within")
    if joined.empty:
        return labels
    for day, idx in zip(joined["day"], joined["index_right"]):
        labels[str(day)][int(idx)] = 1
    return labels


def build_episode_dataset(
    processed_dir: Path, bbox: tuple
) -> tuple[np.ndarray, np.ndarray, list[dict], list[str]]:
    """Una fila por celda y día: tiempo real, distancias UTM y población.

    Parameters:
        processed_dir: carpeta procesada del episodio (weather.geojson, hotspots, capas).
        bbox: (west, south, east, north).

    Returns:
        (X, y, records, feature_names). Cada record lleva `day` y `cell`
        (cell_id, lon, lat, geometry). X no tiene NaN ni infinitos.
        El número de filas es 144 * número de días.
    """
    processed_path = Path(processed_dir)
    weather_by_day = _load_weather_by_day(processed_path / "weather.geojson")
    days = sorted(weather_by_day)

    cells = _build_grid(bbox)
    grid = gpd.GeoDataFrame(cells, geometry="geometry", crs="EPSG:4326")
    cell_lon = grid["lon"].to_numpy(dtype=float)
    cell_lat = grid["lat"].to_numpy(dtype=float)

    west, south, east, north = bbox
    utm = pyproj.CRS.from_epsg(_utm_epsg((west + east) / 2.0, (south + north) / 2.0))
    grid_utm = grid.to_crs(utm)

    dist_roads = _distances_m(grid_utm, processed_path / "roads.geojson")
    dist_stations = _distances_m(grid_utm, processed_path / "fire_stations.geojson")
    dist_water = _distances_m(grid_utm, processed_path / "water.geojson")
    pop_density = _population_density(processed_path / "population.tif", cells)
    ignitions = _ignition_by_day(processed_path / "hotspots.geojson", grid, days)

    temp_parts: list[np.ndarray] = []
    humidity_parts: list[np.ndarray] = []
    wind_parts: list[np.ndarray] = []
    rain_parts: list[np.ndarray] = []
    y_parts: list[np.ndarray] = []
    records: list[dict] = []

    for day in days:
        stations = weather_by_day[day]
        nearest = _nearest_station_index(cell_lon, cell_lat, stations)
        temp_parts.append(np.array([stations[i]["temp_max"] for i in nearest], dtype=float))
        humidity_parts.append(np.array([stations[i]["humidity_min"] for i in nearest], dtype=float))
        wind_parts.append(np.array([stations[i]["wind_max"] for i in nearest], dtype=float))
        rain_parts.append(np.array([stations[i]["rain_sum"] for i in nearest], dtype=float))
        y_parts.append(ignitions[day])
        for cell in cells:
            records.append({
                "day": day,
                "cell": {
                    "cell_id": cell["cell_id"],
                    "lon": cell["lon"],
                    "lat": cell["lat"],
                    "geometry": cell["geometry"],
                },
            })

    temp_max = np.concatenate(temp_parts)
    humidity_min = np.concatenate(humidity_parts)
    wind_max = np.concatenate(wind_parts)
    rain_sum = np.concatenate(rain_parts)
    n_days = len(days)

    X = np.column_stack([
        temp_max,
        humidity_min,
        wind_max,
        rain_sum,
        _fwi_30_30_30(temp_max, humidity_min, wind_max, rain_sum),
        np.tile(dist_roads, n_days),
        np.tile(dist_stations, n_days),
        np.tile(dist_water, n_days),
        np.tile(pop_density, n_days),
        np.tile(cell_lat, n_days),
        np.tile(cell_lon, n_days),
    ])
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
    y = np.concatenate(y_parts).astype(int)
    return X, y, records, list(FEATURE_NAMES)
