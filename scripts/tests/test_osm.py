"""Tests for the OSM layers + fire accessibility (W3-B4). No network: hand-built Overpass answers."""
import json

import geopandas as gpd
import pytest
from shapely.geometry import Polygon, box

import make_manifest
import osm
import validate

# Around (-71.0, -35.0); 0.01° ≈ 0.9 km in longitude, 1.1 km in latitude there
LON, LAT = -71.0, -35.0


def pts(*xy):
    return [(LON + x, LAT + y) for x, y in xy]


def square(x0, y0, size):
    return pts((x0, y0), (x0 + size, y0), (x0 + size, y0 + size), (x0, y0 + size), (x0, y0))


ELEMENTS = [
    {"type": "node", "lon": LON + 0.10, "lat": LAT, "tags": {"amenity": "fire_station", "name": "Bomberos A"}},
    {"type": "way", "geometry": square(0.20, 0.20, 0.001), "tags": {"amenity": "fire_station"}},
    {"type": "way", "geometry": pts((-0.05, 0.02), (0.05, 0.02)), "tags": {"highway": "primary", "name": "Ruta 5"}},
    {"type": "way", "geometry": pts((0.05, 0.02), (0.08, 0.02)), "tags": {"highway": "primary", "name": "Ruta 5"}},
    {"type": "way", "geometry": pts((0.30, 0.30), (0.301, 0.30)), "tags": {"highway": "track"}},  # ~90 m
    {"type": "way", "geometry": pts((-0.30, -0.30), (-0.20, -0.30)), "tags": {"highway": "track"}},  # ~9 km
    {"type": "way", "geometry": pts((0.0, -0.10), (0.0, 0.10)), "tags": {"waterway": "river", "name": "Río X"}},
    {"type": "way", "geometry": square(0.40, 0.40, 0.05), "tags": {"natural": "water", "name": "Laguna"}},
    {"type": "way", "geometry": square(0.45, -0.45, 0.0005), "tags": {"natural": "water"}},  # tiny pond
    {"type": "way", "geometry": pts((0.5, 0.5), (0.6, 0.5)), "tags": {"highway": "residential"}},  # not a road type
    {"type": "relation", "tags": {"landuse": "reservoir", "name": "Embalse"}, "members": [
        {"type": "way", "role": "outer", "geometry": pts((-0.40, 0.40), (-0.30, 0.40), (-0.30, 0.50))},
        {"type": "way", "role": "outer", "geometry": pts((-0.30, 0.50), (-0.40, 0.50), (-0.40, 0.40))},
        {"type": "way", "role": "inner", "geometry": square(-0.37, 0.43, 0.02)},
    ]},
]


@pytest.fixture(scope="module")
def layers():
    return osm.parse(ELEMENTS)


def test_overpass_query_pads_the_bbox():
    query = osm.overpass_query(bbox=(-72.0, -38.0, -70.0, -33.0), pad=0.2)
    assert "(-38.2,-72.2,-32.8,-69.8)" in query
    for tag in ('"amenity"="fire_station"', '"waterway"="river"', '"landuse"="reservoir"', "primary|secondary"):
        assert tag in query


def test_compact_hook_turns_points_into_tuples(tmp_path):
    raw = tmp_path / "osm.json"
    raw.write_text(json.dumps({"elements": [{"type": "way", "geometry": [{"lat": -35.0, "lon": -71.0}]}]}))
    assert osm.load_elements(raw)[0]["geometry"] == [(-71.0, -35.0)]


def test_parse_sorts_elements(layers):
    assert sorted(layers["stations"]["name"].fillna("-")) == ["-", "Bomberos A"]
    assert all(g.geom_type == "Point" for g in layers["stations"].geometry)  # way station -> centroid
    assert set(layers["roads"]["highway"]) == {"primary", "track"}  # residential ignored
    kinds = layers["water"].set_index("name", drop=False)["kind"]
    assert kinds["Río X"] == "river" and kinds["Laguna"] == "lake" and kinds["Embalse"] == "reservoir"


def test_relation_inner_ring_is_a_hole(layers):
    reservoir = layers["water"].set_index("name").loc["Embalse", "geometry"]
    assert isinstance(reservoir, Polygon) and len(reservoir.interiors) == 1


def test_distances(layers):
    # Small fire right on the river, ~1.8 km south of Ruta 5, ~9 km from Bomberos A
    fire = gpd.GeoDataFrame(geometry=[box(LON - 0.001, LAT - 0.001, LON + 0.001, LAT + 0.001)], crs="EPSG:4326")
    row = osm.add_distances(fire, layers).iloc[0]
    assert row["dist_water_km"] == 0.0
    assert 1.8 < row["dist_road_km"] < 2.4
    assert 8.5 < row["dist_fire_station_km"] < 9.5


def test_distances_when_a_layer_is_empty(layers):
    fire = gpd.GeoDataFrame(geometry=[box(LON, LAT, LON + 0.001, LAT + 0.001)], crs="EPSG:4326")
    empty = {**layers, "stations": layers["stations"].iloc[0:0]}
    assert osm.add_distances(fire, empty).iloc[0]["dist_fire_station_km"] is None


def test_roads_layer_style_merge_and_minor_filter(layers):
    roads = osm.roads_layer(layers["roads"], box(LON - 1, LAT - 1, LON + 1, LAT + 1))
    primary = roads[roads.highway == "primary"]
    assert len(primary) == 1 and primary.iloc[0]["name"] == "Ruta 5"  # two ways joined
    assert primary.iloc[0]["geometry"].geom_type == "LineString"
    color, width, _ = osm.ROAD_STYLE["primary"]
    assert (primary.iloc[0]["color"], primary.iloc[0]["width"]) == (color, width)
    track_km = roads[roads.highway == "track"].to_crs(roads.estimate_utm_crs()).length.sum() / 1000
    assert 8 < track_km < 10  # the long track stays, the 90 m one is dropped


def test_water_layer_drops_tiny_ponds(layers):
    water = osm.water_layer(layers["water"], box(LON - 1, LAT - 1, LON + 1, LAT + 1))
    assert sorted(water["name"]) == ["Embalse", "Laguna"]  # lake + reservoir — not the 50 m pond, not the river
    assert set(water["color"]) == {osm.WATER_COLOR}


def test_water_and_rivers_never_mix_geometries(layers):
    """A LineString in a fill layer is closed into a bogus polygon: rivers get their own line layer."""
    area = box(LON - 1, LAT - 1, LON + 1, LAT + 1)
    water = osm.water_layer(layers["water"], area)
    rivers = osm.rivers_layer(layers["water"], area)
    assert set(water.geom_type) <= {"Polygon", "MultiPolygon"}
    assert set(rivers.geom_type) <= {"LineString", "MultiLineString"}
    assert list(rivers["name"]) == ["Río X"]
    assert set(rivers["width"]) == {osm.RIVER_WIDTH}


def test_clipping_a_lake_to_a_line_drops_it(layers):
    """A lake that only touches the area edge clips to a line: it must not end up in the fill layer."""
    # Laguna spans LON+0.40..0.45; this area ends exactly on its west shore
    area = box(LON + 0.30, LAT + 0.30, LON + 0.40, LAT + 0.50)
    water = osm.water_layer(layers["water"], area)
    assert "Laguna" not in set(water["name"])
    assert set(water.geom_type) <= {"Polygon", "MultiPolygon"}


def test_layers_are_clipped_to_the_area(layers):
    area = box(LON - 0.1, LAT - 0.1, LON + 0.15, LAT + 0.1)
    assert list(osm.stations_layer(layers["stations"], area)["name"]) == ["Bomberos A"]


def test_outputs_pass_the_contract(layers, tmp_path):
    area = box(LON - 1, LAT - 1, LON + 1, LAT + 1)
    registry = validate.load_registry()
    for name, gdf in [("water", osm.water_layer(layers["water"], area)),
                      ("rivers", osm.rivers_layer(layers["water"], area)),
                      ("roads", osm.roads_layer(layers["roads"], area)),
                      ("fire_stations", osm.stations_layer(layers["stations"], area))]:
        path = tmp_path / "processed" / f"{name}.geojson"
        osm.write(osm.to_feature_collection(gdf, "2026-02-14T08:00:00Z"), path)
        assert validate.validate_file(path, registry, tmp_path) == [], name


def test_update_fires_adds_distances(layers, tmp_path):
    fires_path = tmp_path / "fires.geojson"
    fire = {"type": "Feature", "properties": {"fire_id": 1},
            "geometry": {"type": "Polygon", "coordinates": [square(-0.001, -0.001, 0.002)]}}
    fires_path.write_text(json.dumps({"type": "FeatureCollection", "updated_at": "x", "features": [fire]}))
    osm.update_fires(fires_path, layers, "2026-02-14T08:00:00Z")
    props = json.loads(fires_path.read_text())["features"][0]["properties"]
    assert props["fire_id"] == 1 and props["dist_water_km"] == 0.0
    assert {"dist_road_km", "dist_water_km", "dist_fire_station_km"} <= props.keys()


def test_update_fires_skips_when_missing(layers, tmp_path, capsys):
    osm.update_fires(tmp_path / "fires.geojson", layers, "2026-02-14T08:00:00Z")
    assert "[SKIP]" in capsys.readouterr().out


def test_manifest_legend_matches_road_style():
    [roads] = [layer for layer in make_manifest.LAYERS if layer["id"] == "roads"]
    legend = {item["text"].lower(): item["color"] for item in roads["legend"]}
    assert legend == {highway: style[0] for highway, style in osm.ROAD_STYLE.items()}


def test_main_skips_when_overpass_is_down(monkeypatch, capsys):
    def down(refresh=False):
        raise RuntimeError("every Overpass endpoint failed: 504")
    monkeypatch.setattr(osm, "download", down)
    monkeypatch.setattr("sys.argv", ["osm.py"])
    osm.main()  # must not raise: make data keeps going
    assert "[SKIP] OpenStreetMap unavailable" in capsys.readouterr().out


# --- water points for firefighting (W3-B7) ---------------------------------------

WATER_POINT_ELEMENTS = [
    {"type": "node", "lon": LON + 0.01, "lat": LAT, "tags": {"emergency": "fire_hydrant"}},
    {"type": "node", "lon": LON + 0.02, "lat": LAT, "tags": {"emergency": "suction_point"}},
    {"type": "node", "lon": LON + 0.03, "lat": LAT, "tags": {"natural": "spring", "name": "Fuente"}},
    {"type": "node", "lon": LON + 0.04, "lat": LAT, "tags": {"man_made": "water_well"}},
    {"type": "way", "geometry": square(0.05, 0.0, 0.001), "tags": {"man_made": "water_tank"}},
    {"type": "node", "lon": LON + 0.06, "lat": LAT, "tags": {"amenity": "water_point"}},
]


def test_water_points_are_parsed_and_styled():
    layers = osm.parse(ELEMENTS + WATER_POINT_ELEMENTS)
    kinds = sorted(layers["water_points"]["kind"])
    assert kinds == ["fire_water", "hydrant", "spring", "tank", "water_point", "well"]
    out = osm.water_points_layer(layers["water_points"], box(LON - 1, LAT - 1, LON + 1, LAT + 1))
    assert all(g.geom_type == "Point" for g in out.geometry)  # the tank way became its centroid
    assert dict(zip(out["kind"], out["color"]))["hydrant"] == osm.WATER_POINT_COLORS["hydrant"]


def test_fire_gets_distance_to_nearest_water_point():
    layers = osm.parse(ELEMENTS + WATER_POINT_ELEMENTS)
    fire = gpd.GeoDataFrame(geometry=[box(LON - 0.001, LAT - 0.001, LON + 0.001, LAT + 0.001)], crs="EPSG:4326")
    assert 0.7 < osm.add_distances(fire, layers).iloc[0]["dist_water_point_km"] < 1.0  # hydrant ~0.9 km east


def test_cache_name_changes_with_the_query():
    assert osm.raw_file_for("query A") != osm.raw_file_for("query B")


def test_manifest_legend_matches_water_point_colors():
    [layer] = [l for l in make_manifest.LAYERS if l["id"] == "water_points"]
    assert [item["color"] for item in layer["legend"]] == list(osm.WATER_POINT_COLORS.values())


def test_full_query_asks_for_every_road_class_and_hydrants():
    # explicit arguments: the module defaults follow the selected episode's osm_options
    query = osm.overpass_query((-71.0, -35.0, -70.9, -34.9), road_types=osm.ALL_ROAD_TYPES, hydrants=True)
    assert "primary|secondary|tertiary|track|path" in query
    assert "fire_hydrant" in query


def test_trimmed_query_leaves_out_minor_roads_and_hydrants():
    """Large episodes (episodes.json "osm_options") download only main roads and no urban hydrants."""
    query = osm.overpass_query((-71.0, -35.0, -70.9, -34.9), road_types=("primary", "secondary"), hydrants=False)
    assert "primary|secondary)$" in query
    assert "track" not in query and "path" not in query
    assert "fire_hydrant" not in query
    assert "suction_point" in query  # firefighting tanks and suction points stay
