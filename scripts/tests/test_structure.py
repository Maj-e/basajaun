"""Smoke test (W0-B4): checks the repo layout from the README and guarantees
pytest always collects at least one test, even before any script exists."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_readme_folders_exist():
    for folder in [
        "scripts",
        "docs/schemas",
        "data/raw",
        "web/data/sample",
        "web/data/processed/demo",
        "web/data/processed/live",
    ]:
        assert (ROOT / folder).is_dir(), f"missing folder {folder}"


def test_env_ignored_and_uv_project():
    gitignore = (ROOT / ".gitignore").read_text()
    assert ".env" in gitignore.splitlines()
    assert (ROOT / ".env.example").is_file()
    assert (ROOT / "pyproject.toml").is_file()
    assert (ROOT / "uv.lock").is_file()
