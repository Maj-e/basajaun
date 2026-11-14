"""Validate every data file in web/data/ against the contract (docs/schemas/).

Usage:
    uv run scripts/validate.py                 # whole web/data/ tree
    uv run scripts/validate.py FILE [FILE...]  # only these files

Exit code 0 if everything is valid, 1 otherwise (CI fails).

Which schema applies is decided by the file name:
    manifest.json        -> manifest.schema.json  (+ checks that listed files exist)
    hotspots*.geojson    -> hotspots.schema.json  (one file or one per day)
    daily_summary.json   -> daily_summary.schema.json
    alerts.json          -> alerts.schema.json
    hourly_series.json   -> hourly_series.schema.json
    episodes.json        -> episodes.schema.json  (+ checks each episode's folder and manifest exist)
    any other *.geojson  -> geojson_layer.schema.json (generic styled layer)
    any other *.json     -> error: not part of the contract

web/data/static/ is skipped: fixed front-end assets (e.g. the land outline), not pipeline data.
"""
from __future__ import annotations

import json
import sys
from fnmatch import fnmatch
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

BASE_DIR = Path(__file__).resolve().parent.parent
SCHEMAS_DIR = BASE_DIR / "docs" / "schemas"
DATA_DIR = BASE_DIR / "web" / "data"

# (file name pattern, schema). First match wins.
SCHEMA_BY_NAME = [
    ("manifest.json", "manifest.schema.json"),
    ("hotspots*.geojson", "hotspots.schema.json"),
    ("daily_summary.json", "daily_summary.schema.json"),
    ("alerts.json", "alerts.schema.json"),
    ("hourly_series.json", "hourly_series.schema.json"),
    ("episodes.json", "episodes.schema.json"),
    ("*.geojson", "geojson_layer.schema.json"),
]
DATA_SUFFIXES = {".json", ".geojson"}
SKIPPED_DIRS = {"static"}  # top-level folders of web/data/ that hold front-end assets, not contract data


def load_registry(schemas_dir: Path = SCHEMAS_DIR) -> Registry:
    """Register every schema by its $id so cross-file $ref works."""
    resources = []
    for path in sorted(schemas_dir.glob("*.schema.json")):
        schema = json.loads(path.read_text(encoding="utf-8"))
        resources.append((schema["$id"], Resource.from_contents(schema)))
    return Registry().with_resources(resources)


def schema_for(path: Path) -> str | None:
    for pattern, schema in SCHEMA_BY_NAME:
        if fnmatch(path.name, pattern):
            return schema
    return None


def _format_error(error) -> str:
    location = "/".join(str(p) for p in error.absolute_path) or "(root)"
    return f"{location}: {error.message}"


# Geometry families each layer type can draw (a LineString in a fill layer is closed into a bogus polygon)
GEOMETRIES_BY_TYPE = {
    "fill": {"Polygon", "MultiPolygon"},
    "line": {"LineString", "MultiLineString"},
    "circle": {"Point", "MultiPoint"},
    "arrows": {"Point", "MultiPoint"},
    "particles": {"Point", "MultiPoint"},
}


def check_manifest(manifest: dict, data_dir: Path) -> list[str]:
    """Checks a schema can't express: unique ids, listed files exist, temporal layers carry `t`."""
    errors = []
    seen = set()
    for layer in manifest.get("layers", []):
        layer_id, file = layer.get("id"), layer.get("file")
        if layer_id in seen:
            errors.append(f"layers: duplicate id '{layer_id}'")
        seen.add(layer_id)
        if not isinstance(file, str):
            continue
        target = data_dir / file
        if not target.is_file():
            errors.append(f"layers/{layer_id}: file '{file}' does not exist in {data_dir.name}/")
            continue
        if target.suffix != ".geojson":
            continue
        try:
            features = json.loads(target.read_text(encoding="utf-8")).get("features", [])
        except (json.JSONDecodeError, AttributeError):
            continue  # reported when the file itself is validated
        allowed = GEOMETRIES_BY_TYPE.get(layer.get("type"))
        if allowed:
            wrong = {}
            for f in features:
                kind = (f.get("geometry") or {}).get("type")
                if kind not in allowed:
                    wrong[kind] = wrong.get(kind, 0) + 1
            if wrong:
                found = ", ".join(f"{n} {k}" for k, n in sorted(wrong.items(), key=lambda kv: str(kv[0])))
                errors.append(f"layers/{layer_id}: type '{layer.get('type')}' draws {'/'.join(sorted(allowed))} only, file has {found}")
        if layer.get("temporal"):
            missing = sum(1 for f in features if not isinstance(f.get("properties", {}).get("t"), (int, float)))
            if missing:
                errors.append(f"layers/{layer_id}: temporal layer but {missing} feature(s) lack a numeric 't'")
    return errors


def check_episodes(doc: dict, data_dir: Path) -> list[str]:
    """Checks a schema can't express: unique ids, default exists, folders and manifests exist, sane bbox / dates."""
    errors = []
    ids = [e.get("id") for e in doc.get("episodes", [])]
    for dup in sorted({i for i in ids if ids.count(i) > 1}):
        errors.append(f"episodes: duplicate id '{dup}'")
    if doc.get("default") not in ids:
        errors.append(f"default: '{doc.get('default')}' is not one of the episode ids")
    for e in doc.get("episodes", []):
        eid = e.get("id")
        bbox = e.get("bbox") or []
        if len(bbox) == 4 and not (bbox[0] < bbox[2] and bbox[1] < bbox[3]):
            errors.append(f"episodes/{eid}: bbox must be west < east and south < north")
        if isinstance(e.get("start"), str) and isinstance(e.get("end"), str) and e["start"] > e["end"]:
            errors.append(f"episodes/{eid}: start is after end")
        if e.get("live"):
            continue  # live data only exists on the published site (update-data.yml), never in the repo
        for key in ("dir", "manifest"):
            if isinstance(e.get(key), str):
                target = data_dir / e[key]
                exists = target.is_dir() if key == "dir" else target.is_file()
                if not exists:
                    errors.append(f"episodes/{eid}: {key} '{e[key]}' does not exist (run make data EPISODE={eid})")
    return errors


def validate_file(path: Path, registry: Registry, data_dir: Path = DATA_DIR) -> list[str]:
    """Return the list of contract errors for one file (empty = valid)."""
    schema_name = schema_for(path)
    if schema_name is None:
        return [f"not a contract file (expected one of: {', '.join(p for p, _ in SCHEMA_BY_NAME)})"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]

    schema = registry.contents(schema_name)
    validator = Draft202012Validator(schema, registry=registry)
    errors = [_format_error(e) for e in sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path))]

    if schema_name == "episodes.schema.json" and isinstance(data, dict):
        errors += check_episodes(data, data_dir)
    if schema_name == "manifest.schema.json" and isinstance(data, dict):
        # `file` paths are relative to web/data/, wherever the manifest lives
        errors += check_manifest(data, data_dir)
    return errors


def find_data_files(data_dir: Path = DATA_DIR) -> list[Path]:
    return sorted(
        p for p in data_dir.rglob("*")
        if p.is_file() and p.suffix in DATA_SUFFIXES
        and p.relative_to(data_dir).parts[0] not in SKIPPED_DIRS
    )


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    files = [Path(a).resolve() for a in args] if args else find_data_files()
    registry = load_registry()

    failed = 0
    for path in files:
        errors = validate_file(path, registry)
        try:
            shown = path.relative_to(BASE_DIR)
        except ValueError:
            shown = path
        if errors:
            failed += 1
            print(f"FAIL {shown}")
            for err in errors[:20]:
                print(f"     - {err}")
            if len(errors) > 20:
                print(f"     … and {len(errors) - 20} more")
        else:
            print(f"ok   {shown}")

    print(f"\n{len(files) - failed}/{len(files)} files valid")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
