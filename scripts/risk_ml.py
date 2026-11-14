"""Municipal wildfire ignition risk model trained on historical episode data.

Uses only project-native scientific libraries (numpy, scipy, shapely, pyproj)
to avoid adding new dependencies to CI or team environments.

Integrates with `ml_features.build_episode_dataset` (IA1) when available, and includes
a self-contained fallback feature builder with optional DEM slope extraction, out-of-sample
probability calibration (Platt scaling), Brier score evaluation, and local SHAP-like
linear feature contributions per grid cell.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pyproj
import shapely
from scipy.optimize import minimize
from scipy.special import expit, logit
from shapely.geometry import Point, box, mapping, shape

from config import BBOX, PROCESSED

GRID_COLS = 12
GRID_ROWS = 12

RISK_COLORS = {
    "critical": "#b10026",
    "high": "#fc4e2a",
    "moderate": "#feb24c",
    "low": "#78c679",
}

MUNICIPAL_ACTIONS = {
    "critical": "Cierre preventivo de accesos forestales, vigilancia aérea y preposicionamiento de brigadas.",
    "high": "Alerta amarilla municipal, patrullaje en interfaz urbano-forestal y restricción de quemas.",
    "moderate": "Monitorización meteorológica continua y revisión de hidrantes / vías de evacuación.",
    "low": "Vigilancia ordinaria de red de alerta temprana.",
}

DEFAULT_FEATURE_NAMES = [
    "temp_max",
    "humidity_min",
    "wind_max",
    "rain_sum",
    "fwi_30_30_30",
    "dist_road_km",
    "dist_fire_station_km",
    "dist_water_km",
    "pop_density",
    "slope_deg",
]

FEATURE_LABELS_ES = {
    "temp_max": "Temperatura máx.",
    "humidity_min": "Humedad mín.",
    "wind_max": "Racha viento",
    "rain_sum": "Déficit lluvia",
    "fwi_30_30_30": "Índice 30-30-30",
    "dist_road_km": "Proximidad vía",
    "dist_fire_station_km": "Dist. parque bomberos",
    "dist_water_km": "Dist. punto agua",
    "pop_density": "Interfaz urbana",
    "slope_deg": "Pendiente ladera",
}


def _utm_transformer(lon: float, lat: float):
    zone = int((lon + 180.0) / 6.0) + 1
    epsg = 32600 + zone if lat >= 0 else 32700 + zone
    return pyproj.Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True).transform


def _load_geojson(path: Path) -> dict:
    if not path.is_file():
        return {"type": "FeatureCollection", "features": []}
    return json.loads(path.read_text(encoding="utf-8"))


def _build_grid(bbox: tuple[float, float, float, float], cols: int = GRID_COLS, rows: int = GRID_ROWS) -> list[dict]:
    west, south, east, north = bbox
    dx = (east - west) / cols
    dy = (north - south) / rows
    cells = []
    cid = 1
    for r in range(rows):
        for c in range(cols):
            x0 = west + c * dx
            y0 = south + r * dy
            cells.append({
                "cell_id": f"SEC-{cid:03d}",
                "row": r,
                "col": c,
                "lon": round(x0 + dx / 2.0, 5),
                "lat": round(y0 + dy / 2.0, 5),
                "geometry": box(x0, y0, x0 + dx, y0 + dy),
            })
            cid += 1
    return cells


def _min_distance_km(pt_utm, geoms_utm: list) -> float:
    if not geoms_utm:
        return 25.0
    return round(float(min(pt_utm.distance(g) for g in geoms_utm)) / 1000.0, 2)


def _extract_mean_slope_deg(processed_dir: Path, cells: list[dict]) -> None:
    """Populate `slope_deg` per cell from `slope.tif` or `elevation.tif` when available."""
    for cell in cells:
        cell.setdefault("slope_deg", 0.0)

    slope_tif = processed_dir / "slope.tif"
    elev_tif = processed_dir / "elevation.tif"
    target_tif = slope_tif if slope_tif.is_file() else (elev_tif if elev_tif.is_file() else None)
    if target_tif is None:
        return

    try:
        import rasterio
    except Exception:
        return

    try:
        with rasterio.open(target_tif) as src:
            res_x, res_y = src.res
            meters_per_deg_lat = 111_320.0
            for cell in cells:
                minx, miny, maxx, maxy = cell["geometry"].bounds
                win = src.window(minx, miny, maxx, maxy)
                arr = src.read(1, window=win, masked=True)
                if arr.count() == 0:
                    continue
                if target_tif == slope_tif:
                    val = float(np.maximum(arr.compressed(), 0.0).mean())
                else:
                    dem = np.ma.filled(arr.astype(float), np.nan)
                    if dem.shape[0] < 2 or dem.shape[1] < 2:
                        continue
                    cos_lat = max(0.2, float(np.cos(np.radians(cell["lat"]))))
                    dx_m = max(1.0, abs(res_x) * meters_per_deg_lat * cos_lat)
                    dy_m = max(1.0, abs(res_y) * meters_per_deg_lat)
                    dz_dy, dz_dx = np.gradient(dem, dy_m, dx_m)
                    slope_rad = np.arctan(np.hypot(dz_dx, dz_dy))
                    valid = slope_rad[~np.isnan(slope_rad)]
                    val = float(np.degrees(valid).mean()) if valid.size > 0 else 0.0
                cell["slope_deg"] = round(val, 2)
    except Exception:
        return


def _fallback_build_dataset(
    processed_dir: Path, bbox: tuple[float, float, float, float]
) -> tuple[np.ndarray, np.ndarray, list[dict], list[str]]:
    """Self-contained dataset builder used until IA1's `ml_features.py` is merged."""
    hotspots_fc = _load_geojson(processed_dir / "hotspots.geojson")
    weather_fc = _load_geojson(processed_dir / "weather.geojson")

    cells = _build_grid(bbox)
    to_utm = _utm_transformer((bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0)

    def load_utm_geoms(filename: str) -> list:
        fc = _load_geojson(processed_dir / filename)
        out = []
        for feat in fc.get("features", []):
            geom_raw = feat.get("geometry")
            if not geom_raw:
                continue
            g = shape(geom_raw)
            if not g.is_empty:
                out.append(shapely.transform(g, lambda coords: np.column_stack(to_utm(coords[:, 0], coords[:, 1]))))
        return out

    roads_utm = load_utm_geoms("roads.geojson")
    stations_utm = load_utm_geoms("fire_stations.geojson")
    water_utm = load_utm_geoms("water.geojson")

    pop_raster = None
    pop_tif = processed_dir / "population.tif"
    if pop_tif.is_file():
        try:
            import rasterio
            pop_raster = rasterio.open(pop_tif)
        except Exception:
            pop_raster = None

    for cell in cells:
        pt = Point(cell["lon"], cell["lat"])
        pt_utm = shapely.transform(pt, lambda coords: np.column_stack(to_utm(coords[:, 0], coords[:, 1])))
        cell["dist_road_km"] = _min_distance_km(pt_utm, roads_utm)
        cell["dist_fire_station_km"] = _min_distance_km(pt_utm, stations_utm)
        cell["dist_water_km"] = _min_distance_km(pt_utm, water_utm)
        pop_val = 0.0
        if pop_raster is not None:
            try:
                minx, miny, maxx, maxy = cell["geometry"].bounds
                win = pop_raster.window(minx, miny, maxx, maxy)
                arr = pop_raster.read(1, window=win, masked=True)
                if arr.count() > 0:
                    pop_val = float(np.maximum(arr.compressed(), 0.0).mean())
            except Exception:
                pop_val = 0.0
        cell["pop_density"] = round(pop_val, 1)

    if pop_raster is not None:
        pop_raster.close()

    _extract_mean_slope_deg(processed_dir, cells)

    by_day_point: dict[tuple[str, float, float], dict] = {}
    for feat in weather_fc.get("features", []):
        props = feat.get("properties", {})
        coords = (feat.get("geometry") or {}).get("coordinates") or []
        ts = props.get("timestamp_utc", "")
        if len(coords) < 2 or len(ts) < 10:
            continue
        day = ts[:10]
        lon, lat = round(float(coords[0]), 4), round(float(coords[1]), 4)
        rec = by_day_point.setdefault((day, lon, lat), {
            "lon": lon,
            "lat": lat,
            "temp_max": -99.0,
            "humidity_min": 100.0,
            "wind_max": 0.0,
            "rain_sum": 0.0,
        })
        if isinstance(props.get("temperature"), (int, float)):
            rec["temp_max"] = max(rec["temp_max"], float(props["temperature"]))
        if isinstance(props.get("humidity"), (int, float)):
            rec["humidity_min"] = min(rec["humidity_min"], float(props["humidity"]))
        if isinstance(props.get("speed"), (int, float)):
            rec["wind_max"] = max(rec["wind_max"], float(props["speed"]))
        if isinstance(props.get("rain"), (int, float)):
            rec["rain_sum"] += float(props["rain"])

    weather_by_day: dict[str, list[dict]] = defaultdict(list)
    for (day, _, _), rec in by_day_point.items():
        if rec["temp_max"] < -50:
            rec["temp_max"] = 25.0
        weather_by_day[day].append(rec)

    ignitions: dict[tuple[str, str], int] = defaultdict(int)
    for feat in hotspots_fc.get("features", []):
        props = feat.get("properties", {})
        coords = (feat.get("geometry") or {}).get("coordinates") or []
        ts = props.get("timestamp_utc", "")
        if len(coords) < 2 or len(ts) < 10:
            continue
        day = ts[:10]
        pt = Point(float(coords[0]), float(coords[1]))
        for cell in cells:
            if cell["geometry"].covers(pt):
                ignitions[(day, cell["cell_id"])] += 1
                break

    days = sorted(weather_by_day.keys())
    if not days:
        raise ValueError("No daily weather records found to train ignition risk model.")

    records = []
    for day in days:
        stations = weather_by_day[day]
        for cell in cells:
            w = min(stations, key=lambda s: (s["lon"] - cell["lon"]) ** 2 + (s["lat"] - cell["lat"]) ** 2)
            fwi = (
                max(0.0, w["temp_max"] - 20.0) / 15.0
                + max(0.0, 50.0 - w["humidity_min"]) / 35.0
                + w["wind_max"] / 35.0
                - min(w["rain_sum"], 5.0) * 0.4
            )
            y = 1 if ignitions.get((day, cell["cell_id"]), 0) > 0 else 0
            records.append({
                "day": day,
                "cell": cell,
                "temp_max": round(w["temp_max"], 2),
                "humidity_min": round(w["humidity_min"], 2),
                "wind_max": round(w["wind_max"], 2),
                "rain_sum": round(w["rain_sum"], 2),
                "fwi_30_30_30": round(fwi, 3),
                "dist_road_km": cell["dist_road_km"],
                "dist_fire_station_km": cell["dist_fire_station_km"],
                "dist_water_km": cell["dist_water_km"],
                "pop_density": cell["pop_density"],
                "slope_deg": cell["slope_deg"],
                "y": y,
            })

    X = np.array([[r[f] for f in DEFAULT_FEATURE_NAMES] for r in records], dtype=float)
    y = np.array([r["y"] for r in records], dtype=int)
    return X, y, records, DEFAULT_FEATURE_NAMES


def get_dataset(
    processed_dir: Path, bbox: tuple[float, float, float, float]
) -> tuple[np.ndarray, np.ndarray, list[dict], list[str]]:
    """Load dataset via IA1 `ml_features.build_episode_dataset` when present, else fallback."""
    try:
        from ml_features import build_episode_dataset
        return build_episode_dataset(processed_dir, bbox)
    except ImportError:
        return _fallback_build_dataset(processed_dir, bbox)


def fit_logistic_l2(X: np.ndarray, y: np.ndarray, l2: float = 1.0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Train class-balanced L2-regularized logistic regression using scipy L-BFGS-B."""
    mean = X.mean(axis=0)
    std = np.where(X.std(axis=0) > 1e-8, X.std(axis=0), 1.0)
    Xs = (X - mean) / std

    n_pos = max(1, int(y.sum()))
    n_neg = max(1, int(len(y) - n_pos))
    w_pos = len(y) / (2.0 * n_pos)
    w_neg = len(y) / (2.0 * n_neg)
    sample_w = np.where(y == 1, w_pos, w_neg)

    def loss_and_grad(params: np.ndarray) -> tuple[float, np.ndarray]:
        w = params[:-1]
        b = params[-1]
        logits = np.clip(Xs @ w + b, -30.0, 30.0)
        p = expit(logits)
        eps = 1e-12
        bce = -np.mean(sample_w * (y * np.log(p + eps) + (1.0 - y) * np.log(1.0 - p + eps)))
        reg = 0.5 * l2 * float(np.sum(w ** 2)) / len(y)
        diff = sample_w * (p - y) / len(y)
        grad_w = Xs.T @ diff + (l2 * w) / len(y)
        grad_b = float(np.sum(diff))
        return float(bce + reg), np.append(grad_w, grad_b)

    res = minimize(loss_and_grad, np.zeros(Xs.shape[1] + 1), jac=True, method="L-BFGS-B")
    return res.x, mean, std


def predict_proba(X: np.ndarray, params: np.ndarray, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    Xs = (X - mean) / std
    return expit(np.clip(Xs @ params[:-1] + params[-1], -30.0, 30.0))


def fit_platt_calibrator(raw_probs: np.ndarray, y_true: np.ndarray) -> tuple[float, float]:
    """Fit Platt scaling (a * logit(p) + b) to calibrate probabilities without altering rank order."""
    if len(np.unique(y_true)) < 2:
        return 1.0, 0.0
    clipped = np.clip(raw_probs, 1e-6, 1.0 - 1e-6)
    z = logit(clipped)

    def loss(ab: np.ndarray) -> float:
        a, b = float(ab[0]), float(ab[1])
        p = expit(np.clip(a * z + b, -30.0, 30.0))
        eps = 1e-12
        bce = -np.mean(y_true * np.log(p + eps) + (1.0 - y_true) * np.log(1.0 - p + eps))
        reg = 0.01 * ((a - 1.0) ** 2 + b ** 2)
        return float(bce + reg)

    res = minimize(loss, np.array([1.0, 0.0]), bounds=[(0.2, 5.0), (-5.0, 5.0)], method="L-BFGS-B")
    return float(res.x[0]), float(res.x[1])


def apply_platt_calibrator(raw_probs: np.ndarray, a: float, b: float) -> np.ndarray:
    clipped = np.clip(raw_probs, 1e-6, 1.0 - 1e-6)
    return expit(np.clip(a * logit(clipped) + b, -30.0, 30.0))


def brier_score_np(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    return float(np.mean((y_prob - y_true) ** 2))


def roc_auc_score_np(y_true: np.ndarray, y_score: np.ndarray) -> float:
    pos = y_score[y_true == 1]
    neg = y_score[y_true == 0]
    if len(pos) == 0 or len(neg) == 0:
        return 0.5
    wins = sum(float(np.sum(p > neg)) + 0.5 * float(np.sum(p == neg)) for p in pos)
    return wins / (len(pos) * len(neg))


def pr_auc_score_np(y_true: np.ndarray, y_score: np.ndarray) -> float:
    if int(y_true.sum()) == 0:
        return 0.0
    order = np.argsort(-y_score)
    y_sorted = y_true[order]
    tp = np.cumsum(y_sorted)
    precision = tp / np.arange(1, len(y_sorted) + 1)
    return float(np.sum(precision[y_sorted == 1]) / np.sum(y_true == 1))


def stratified_kfold_probs(X: np.ndarray, y: np.ndarray, k: int = 5) -> np.ndarray:
    rng = np.random.default_rng(42)
    pos_idx = rng.permutation(np.where(y == 1)[0])
    neg_idx = rng.permutation(np.where(y == 0)[0])
    folds = [np.concatenate([pos_idx[i::k], neg_idx[i::k]]) for i in range(k)]
    oof = np.zeros(len(y), dtype=float)
    for i in range(k):
        val_idx = folds[i]
        tr_idx = np.concatenate([folds[j] for j in range(k) if j != i])
        if len(np.unique(y[tr_idx])) < 2:
            oof[val_idx] = float(y[tr_idx].mean())
            continue
        params, mean, std = fit_logistic_l2(X[tr_idx], y[tr_idx])
        oof[val_idx] = predict_proba(X[val_idx], params, mean, std)
    return oof


def compute_local_contributions(
    X_rows: np.ndarray,
    params: np.ndarray,
    mean: np.ndarray,
    std: np.ndarray,
    feature_names: list[str],
    top_k: int = 3,
) -> list[list[dict]]:
    """Compute exact per-cell log-odds contributions w_j * (x_ij - mean_j) / std_j."""
    Xs = (X_rows - mean) / std
    w = params[:-1]
    contrib_matrix = Xs * w
    results: list[list[dict]] = []
    for row_contrib in contrib_matrix:
        pos_pairs = [
            (fname, float(val))
            for fname, val in zip(feature_names, row_contrib)
            if val > 0.0
        ]
        pos_pairs.sort(key=lambda kv: kv[1], reverse=True)
        total_pos = sum(v for _, v in pos_pairs) or 1.0
        top_items = [
            {
                "feature": fname,
                "label": FEATURE_LABELS_ES.get(fname, fname),
                "share_pct": round((val / total_pos) * 100.0, 1),
            }
            for fname, val in pos_pairs[:top_k]
        ]
        results.append(top_items)
    return results


def classify_risk_tier(prob: float, base_rate: float = 0.05) -> str:
    effective_base = max(0.005, float(base_rate))
    lift = prob / effective_base
    if prob >= 0.35 or (prob >= 0.08 and lift >= 8.5):
        return "critical"
    if prob >= 0.18 or (prob >= 0.045 and lift >= 4.5):
        return "high"
    if prob >= 0.08 or (prob >= 0.02 and lift >= 2.0):
        return "moderate"
    return "low"



def format_drivers(row: dict, top_drivers: list[dict] | None = None) -> str:
    parts = [
        f"T.máx {row['temp_max']:.1f}°C",
        f"Hum.mín {row['humidity_min']:.0f}%",
        f"Viento {row['wind_max']:.0f} km/h",
    ]
    if row.get("slope_deg", 0.0) >= 8.0:
        parts.append(f"Pendiente {row['slope_deg']:.1f}°")
    if row.get("dist_road_km", 99.0) <= 2.5:
        parts.append(f"Carretera a {row['dist_road_km']:.1f} km")
    elif row.get("pop_density", 0.0) >= 20.0:
        parts.append(f"Población {row['pop_density']:.0f} hab/km²")
    if top_drivers:
        lead = top_drivers[0]
        parts.append(f"Factor líder: {lead['label']} ({lead['share_pct']:.0f}%)")
    return " · ".join(parts)


def run_risk_model(processed_dir: Path = PROCESSED, bbox: tuple[float, float, float, float] = BBOX) -> dict:
    X_all, y_all, records, feature_names = get_dataset(processed_dir, bbox)

    days = sorted({r["day"] for r in records})
    unique_cells = {r["cell"]["cell_id"] for r in records}

    split_idx = max(1, int(len(days) * 0.70))
    train_days = set(days[:split_idx])
    val_days = set(days[split_idx:]) if split_idx < len(days) else set(days[-1:])
    train_mask = np.array([r["day"] in train_days for r in records])
    val_mask = np.array([r["day"] in val_days for r in records])

    metrics: dict = {
        "algorithm": "Calibrated L2 Logistic Regression (numpy/scipy + Platt scaling)",
        "n_cells": len(unique_cells),
        "n_days": len(days),
        "n_samples": len(records),
        "positive_rate": round(float(y_all.mean()), 4),
    }

    cal_a, cal_b = 1.0, 0.0

    if len(np.unique(y_all[train_mask])) > 1 and len(np.unique(y_all[val_mask])) > 1:
        params_v, mean_v, std_v = fit_logistic_l2(X_all[train_mask], y_all[train_mask])
        raw_val = predict_proba(X_all[val_mask], params_v, mean_v, std_v)
        cal_a, cal_b = fit_platt_calibrator(raw_val, y_all[val_mask])
        val_probs = apply_platt_calibrator(raw_val, cal_a, cal_b)
        metrics["validation_strategy"] = "out_of_time_70_30"
        metrics["train_days"] = sorted(train_days)
        metrics["val_days"] = sorted(val_days)
        metrics["val_roc_auc"] = round(roc_auc_score_np(y_all[val_mask], val_probs), 4)
        metrics["val_pr_auc"] = round(pr_auc_score_np(y_all[val_mask], val_probs), 4)
        metrics["brier_score"] = round(brier_score_np(y_all[val_mask], val_probs), 4)
    elif len(np.unique(y_all)) > 1:
        k = max(2, min(5, int(y_all.sum())))
        raw_oof = stratified_kfold_probs(X_all, y_all, k=k)
        cal_a, cal_b = fit_platt_calibrator(raw_oof, y_all)
        oof_probs = apply_platt_calibrator(raw_oof, cal_a, cal_b)
        metrics["validation_strategy"] = f"stratified_{k}fold"
        metrics["val_roc_auc"] = round(roc_auc_score_np(y_all, oof_probs), 4)
        metrics["val_pr_auc"] = round(pr_auc_score_np(y_all, oof_probs), 4)
        metrics["brier_score"] = round(brier_score_np(y_all, oof_probs), 4)
    else:
        metrics["validation_strategy"] = "baseline_prior"
        metrics["val_roc_auc"] = None
        metrics["val_pr_auc"] = None
        metrics["brier_score"] = None

    metrics["calibration"] = {"method": "platt_scaling", "slope": round(cal_a, 4), "intercept": round(cal_b, 4)}

    latest_day = days[-1]
    latest_records = [r for r in records if r["day"] == latest_day]
    X_latest = np.array([[r[f] for f in feature_names] for r in latest_records], dtype=float)

    if len(np.unique(y_all)) > 1:
        params_f, mean_f, std_f = fit_logistic_l2(X_all, y_all)
        raw_latest = predict_proba(X_latest, params_f, mean_f, std_f)
        latest_probs = apply_platt_calibrator(raw_latest, cal_a, cal_b)
        weights = np.abs(params_f[:-1])
        total_w = float(weights.sum()) or 1.0
        importances = {fname: round(float(w / total_w), 4) for fname, w in zip(feature_names, weights)}
        metrics["feature_importances"] = dict(sorted(importances.items(), key=lambda kv: kv[1], reverse=True))
        local_drivers = compute_local_contributions(X_latest, params_f, mean_f, std_f, feature_names)
    else:
        latest_probs = np.full(len(latest_records), float(y_all.mean()))
        metrics["feature_importances"] = {}
        local_drivers = [[] for _ in latest_records]

    base_rate = float(y_all.mean())
    features = []
    tier_counts = {"critical": 0, "high": 0, "moderate": 0, "low": 0}
    for rec, prob, cell_top_drivers in zip(latest_records, latest_probs, local_drivers):
        p_val = round(float(np.clip(prob, 0.0, 1.0)), 4)
        tier = classify_risk_tier(p_val, base_rate=base_rate)
        tier_counts[tier] += 1
        cell = rec["cell"]
        features.append({
            "type": "Feature",
            "geometry": mapping(cell["geometry"]),
            "properties": {
                "cell_id": cell["cell_id"],
                "reference_date": latest_day,
                "ignition_prob": p_val,
                "risk_pct": round(p_val * 100.0, 1),
                "risk_level": tier,
                "fill": RISK_COLORS[tier],
                "fill-opacity": 0.42,
                "stroke": RISK_COLORS[tier],
                "stroke-width": 1.0,
                "temp_max": rec["temp_max"],
                "humidity_min": rec["humidity_min"],
                "wind_max": rec["wind_max"],
                "dist_road_km": rec["dist_road_km"],
                "dist_fire_station_km": rec["dist_fire_station_km"],
                "pop_density": rec["pop_density"],
                "slope_deg": round(float(rec.get("slope_deg", 0.0)), 2),
                "top_drivers": cell_top_drivers,
                "drivers": format_drivers(rec, cell_top_drivers),
                "recommended_action": MUNICIPAL_ACTIONS[tier],
            },
        })

    metrics["latest_date"] = latest_day
    metrics["tier_counts"] = tier_counts

    return {
        "type": "FeatureCollection",
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "model_metrics": metrics,
        "features": features,
    }


def main() -> None:
    out_path = PROCESSED / "ignition_risk.geojson"
    fc = run_risk_model(PROCESSED, BBOX)
    out_path.write_text(json.dumps(fc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    m = fc["model_metrics"]
    print(
        f"[SAVED] {out_path} ({len(fc['features'])} cells | "
        f"strategy={m.get('validation_strategy')} | "
        f"ROC-AUC={m.get('val_roc_auc')} | PR-AUC={m.get('val_pr_auc')} | "
        f"Brier={m.get('brier_score')} | tiers={m.get('tier_counts')})"
    )


if __name__ == "__main__":
    main()
