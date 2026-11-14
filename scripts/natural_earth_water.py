"""National-scale water for episodes that skip OSM (e.g. a whole country).

OSM water on a whole country is far too heavy and unreadable at that zoom, so these episodes use
Natural Earth 10m instead: large lakes / reservoirs (-> water.geojson, polygons) and main rivers
(-> rivers.geojson, lines), clipped to the episode bbox and already styled.
Runs only when the episode skips "osm" (episodes.json); otherwise it does nothing.
"""
import json
import urllib.request

from shapely.geometry import box, mapping, shape

from config import BBOX, EPISODE, PROCESSED, RAW, SKIP

BASE = "https://cdn.jsdelivr.net/gh/nvkelso/natural-earth-vector@v5.1.2/geojson/"
SOURCES = {"lakes": "ne_10m_lakes.geojson", "rivers": "ne_10m_rivers_lake_centerlines.geojson"}
STYLE = {"lakes": {"color": "#2b6cb0", "opacity": 0.55}, "rivers": {"color": "#4a90d9", "width": 1.2}}


def load(name: str) -> dict:
    path = RAW / SOURCES[name]
    if not path.exists():
        RAW.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(BASE + SOURCES[name], path)
    return json.loads(path.read_text(encoding="utf-8"))


def clip(fc: dict, kind: str) -> dict:
    frame = box(*BBOX)
    features = []
    for f in fc["features"]:
        geom = shape(f["geometry"])
        if not geom.intersects(frame):
            continue
        part = geom.intersection(frame).simplify(0.005, preserve_topology=True)
        if part.is_empty:
            continue
        props = {"name": f["properties"].get("name") or f["properties"].get("name_en"),
                 "kind": "lake" if kind == "lakes" else "river", **STYLE[kind]}
        features.append({"type": "Feature", "geometry": mapping(part), "properties": props})
    return {"type": "FeatureCollection", "updated_at": None, "features": features}


def main() -> None:
    if "osm" not in SKIP:
        print(f"-- {EPISODE['id']} uses OSM water, nothing to do")
        return
    from datetime import datetime, timezone
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for kind, out in (("lakes", "water.geojson"), ("rivers", "rivers.geojson")):
        fc = clip(load(kind), kind)
        fc["updated_at"] = updated
        (PROCESSED / out).write_text(json.dumps(fc, separators=(",", ":")), encoding="utf-8")
        print(f"[SAVED] {PROCESSED / out} ({len(fc['features'])} {kind}, Natural Earth)")


if __name__ == "__main__":
    main()
