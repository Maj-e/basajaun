import os
from pathlib import Path

# Carga manual de .env sin depender de librerías externas
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.strip().split("=", 1)
            os.environ.setdefault(k, v)

FIRMS_MAP_KEY = os.getenv("FIRMS_MAP_KEY")

# Zona por defecto (Chile centro-sur, verano austral - episodio real)
# Formato: (oeste, sur, este, norte)
BBOX = (-72.0, -38.0, -70.0, -33.0)
FECHA_INICIO = "2026-02-01"
FECHA_FIN = "2026-02-14"

# Rutas del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent
RAW = BASE_DIR / "data" / "raw"
SAMPLE = BASE_DIR / "web" / "data" / "sample"
PROCESSED = BASE_DIR / "web" / "data" / "processed"
