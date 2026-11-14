"""Contract self-test (W1-B4): proves the validator accepts the contract and rejects breakages.

    fixtures/contract/valid/            one correct file per contract file -> must pass
    fixtures/contract/invalid/<case>/   one deliberately broken file each  -> must fail

To cover a new rule: add a folder under invalid/ named after what is broken.
"""
from pathlib import Path

import pytest

import validate

FIXTURES = Path(__file__).parent / "fixtures" / "contract"
VALID = sorted((FIXTURES / "valid").iterdir())
INVALID = sorted(p for p in (FIXTURES / "invalid").iterdir() if p.is_dir())


@pytest.fixture(scope="module")
def registry():
    return validate.load_registry()


@pytest.mark.parametrize("path", VALID, ids=lambda p: p.name)
def test_valid_fixture_passes(path, registry):
    assert validate.validate_file(path, registry, data_dir=path.parent) == []


@pytest.mark.parametrize("case", INVALID, ids=lambda p: p.name)
def test_invalid_fixture_fails(case, registry):
    [path] = [p for p in case.iterdir() if p.suffix in validate.DATA_SUFFIXES]
    errors = validate.validate_file(path, registry, data_dir=case)
    assert errors, f"{case.name}: the validator accepted a broken file"


def test_every_contract_file_has_a_valid_fixture():
    names = {p.name for p in VALID}
    assert {"hotspots.geojson", "daily_summary.json", "alerts.json", "manifest.json"} <= names
