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
        if layer.get("temporal") and target.suffix == ".geojson":
            try:
                features = json.loads(target.read_text(encoding="utf-8")).get("features", [])
            except (json.JSONDecodeError, AttributeError):
                continue  # reported when the file itself is validated
            missing = sum(1 for f in features if not isinstance(f.get("properties", {}).get("t"), (int, float)))
            if missing:
                errors.append(f"layers/{layer_id}: temporal layer but {missing} feature(s) lack a numeric 't'")
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
