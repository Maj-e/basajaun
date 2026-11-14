import os
from pathlib import Path

# Load .env by hand, without depending on an external library
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.strip().split("=", 1)
            os.environ.setdefault(k, v)

FIRMS_MAP_KEY = os.getenv("FIRMS_MAP_KEY")

# Default area (south-central Chile, austral summer - real fire episode)
# Format: (west, south, east, north)
BBOX = (-72.0, -38.0, -70.0, -33.0)
START_DATE = "2026-02-01"
END_DATE = "2026-02-14"

# Project paths
BASE_DIR = Path(__file__).resolve().parent.parent
RAW = BASE_DIR / "data" / "raw"
SAMPLE = BASE_DIR / "web" / "data" / "sample"
PROCESSED = BASE_DIR / "web" / "data" / "processed"
