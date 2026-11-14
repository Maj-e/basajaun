"""Shared settings: FIRMS key, area, period and paths — taken from the selected episode (W4-B5).

Episodes are listed in web/data/episodes.json. Pick one with the EPISODE environment variable:
    make data EPISODE=los-angeles-2025-01
Without EPISODE the default episode is used (Chile, data in web/data/processed/ as before).

    uv run scripts/config.py         # show the selected episode
    uv run scripts/config.py skip    # pipeline steps this episode skips (used by the Makefile)
"""
import json
import os
import sys
from pathlib import Path

# Load .env by hand, without depending on an external library
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.strip().split("=", 1)
            os.environ.setdefault(k, v)

FIRMS_MAP_KEY = os.getenv("FIRMS_MAP_KEY")

# Project paths
BASE_DIR = Path(__file__).resolve().parent.parent
WEB_DATA = BASE_DIR / "web" / "data"
EPISODES_FILE = WEB_DATA / "episodes.json"
SAMPLE = WEB_DATA / "sample"

# Used when web/data/episodes.json doesn't exist (south-central Chile, real fire episode)
FALLBACK_EPISODE = {
    "id": "chile-2026-02",
    "name": "Chile–Argentina border · Feb 2026",
    "bbox": [-72.0, -38.0, -70.0, -33.0],   # west, south, east, north
    "start": "2026-02-01",
    "end": "2026-02-14",
    "dir": "processed",
    "manifest": "manifest.json",
}


def resolve_episode(doc: dict | None, episode_id: str | None = None) -> dict:
    """Pick an episode from an episodes.json document (default one when episode_id is empty)."""
    if not doc:
        if episode_id and episode_id != FALLBACK_EPISODE["id"]:
            raise SystemExit(f"Unknown episode '{episode_id}': {EPISODES_FILE} not found.")
        return FALLBACK_EPISODE
    episodes = {e["id"]: e for e in doc["episodes"]}
    wanted = episode_id or doc.get("default") or doc["episodes"][0]["id"]
    if wanted not in episodes:
        raise SystemExit(f"Unknown episode '{wanted}'. Known: {', '.join(episodes)}")
    return episodes[wanted]


def episode_paths(episode: dict, base_dir: Path = BASE_DIR) -> dict:
    """Where an episode's raw downloads, processed files and manifest live."""
    web_data = base_dir / "web" / "data"
    default_layout = episode["dir"] == "processed"
    return {
        "raw": base_dir / "data" / "raw" / ("" if default_layout else f"episodes/{episode['id']}"),
        "processed": web_data / episode["dir"],
        "manifest": web_data / episode["manifest"],
    }


_doc = json.loads(EPISODES_FILE.read_text(encoding="utf-8")) if EPISODES_FILE.exists() else None
EPISODE = resolve_episode(_doc, os.getenv("EPISODE") or None)
EPISODE_ID = EPISODE["id"]
BBOX = tuple(EPISODE["bbox"])                 # (west, south, east, north)
START_DATE, END_DATE = EPISODE["start"], EPISODE["end"]
SKIP = set(EPISODE.get("skip", []))           # pipeline steps this episode doesn't run

_paths = episode_paths(EPISODE)
RAW = _paths["raw"]
PROCESSED = _paths["processed"]
MANIFEST = _paths["manifest"]


if __name__ == "__main__":
    if sys.argv[1:] == ["skip"]:
        print(" ".join(sorted(SKIP)))
    else:
        print(f"Episode {EPISODE_ID}: {EPISODE['name']}")
        print(f"  BBOX {BBOX} · {START_DATE} → {END_DATE}")
        print(f"  raw {RAW} · processed {PROCESSED} · manifest {MANIFEST}")
        if SKIP:
            print(f"  skips: {', '.join(sorted(SKIP))}")
