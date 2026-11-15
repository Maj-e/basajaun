"""How each fire looked over time: one snapshot every few hours, from its first to its last detection.

Why: fires.geojson holds one final polygon per fire. Spread, evacuation and risk are computed from it, so
scrubbing back in the player showed the end state at every hour. A snapshot is the fire as it was at one
moment (hull of the hotspots detected up to then, same rule as fires.py), and the scripts that derive zones
from the fire run once per snapshot.

The last snapshot of a fire IS its final polygon (same geometry, same figures), so everything that reads
"the fire" keeps working: consumers use the snapshots without `t_until`.

    snapshots(fires_fc, hotspots_fc)  ->  {fire_id: [ {t_from, t_until, geometry, frp_max, n_hotspots}, ... ]}
"""
from __future__ import annotations

import numpy as np
import shapely
from shapely.geometry import MultiPoint, shape

from spread import transformers_for

STEP_HOURS = 6.0
BUFFER_M = 500.0  # same as fires.py


def boundaries(t_start: float, t_end: float, step: float = STEP_HOURS) -> list[float]:
    """Moments a fire is sampled at: its start, every `step` hours, and its last detection."""
    times = [t_start]
    t = t_start + step
    while t < t_end - 1e-6:
        times.append(t)
        t += step
    if t_end > t_start + 1e-6:
        times.append(t_end)
    return [round(t, 2) for t in times]


def hull_at(points: list[tuple[float, float]]):
    """Convex hull of lon/lat points + 500 m, as a WGS84 shapely geometry (like fires.py)."""
    lon, lat = points[0]
    to_utm, to_wgs84 = transformers_for(lon, lat)
    xs, ys = to_utm([p[0] for p in points], [p[1] for p in points])
    hull = MultiPoint(list(zip(xs, ys))).convex_hull.buffer(BUFFER_M)
    return shapely.transform(hull, lambda c: np.column_stack(to_wgs84(c[:, 0], c[:, 1])))


def snapshots(fires_fc: dict, hotspots_fc: dict | None, step: float = STEP_HOURS) -> dict[int, list[dict]]:
    """Snapshots per fire id, oldest first. Without hotspots every fire has one snapshot: its final polygon."""
    by_fire: dict[int, list[tuple[float, float, float, float]]] = {}
    for f in (hotspots_fc or {}).get("features", []):
        p = f.get("properties", {})
        if p.get("fire_id") is None or f.get("geometry", {}).get("type") != "Point":
            continue
        lon, lat = f["geometry"]["coordinates"][:2]
        by_fire.setdefault(int(p["fire_id"]), []).append((float(p["t"]), lon, lat, float(p.get("frp") or 0)))

    result: dict[int, list[dict]] = {}
    for fire in fires_fc.get("features", []):
        p = fire["properties"]
        fid = int(p["fire_id"])
        final = {"geometry": shape(fire["geometry"]), "frp_max": float(p.get("frp_max") or 0),
                 "n_hotspots": int(p.get("n_hotspots") or 0)}
        hs = sorted(by_fire.get(fid, []))
        t_start = float(p.get("t_start", hs[0][0] if hs else 0.0))
        t_end = float(p.get("t_end", hs[-1][0] if hs else t_start))
        times = boundaries(t_start, t_end, step) if hs else [t_end]
        out = []
        for k, t in enumerate(times):
            last = k == len(times) - 1
            if last:
                snap = dict(final)
            else:
                upto = [h for h in hs if h[0] <= t + 1e-6]
                snap = {"geometry": hull_at([(h[1], h[2]) for h in upto]),
                        "frp_max": max(h[3] for h in upto), "n_hotspots": len(upto)}
            snap["t_from"] = t
            snap["t_until"] = None if last else times[k + 1]
            out.append(snap)
        result[fid] = out
    return result
