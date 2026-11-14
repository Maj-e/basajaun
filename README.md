# Ulinautas

Wildfire hotspot visualization from the **MODIS** and **VIIRS** satellites (NASA FIRMS), harmonized into a single dataset and shown on a web page: layered map, calendar, population-density alerts and time playback.

> Hackathon project (1 day). Full documentation is in Spanish: [`README.es.md`](README.es.md) · work plan [`TODO.es.md`](TODO.es.md) · data contract [`docs/contrato_datos.es.md`](docs/contrato_datos.es.md).

**Conventions:** all code and development files are in English; documents written in Spanish carry a `.es` suffix (`*.es.md`).

---

## Stack

| Part | Technology |
|---|---|
| Data processing | **Python 3.11** · pandas · geopandas · rasterio · rasterstats · scikit-learn · requests |
| Python environment | **[uv](https://docs.astral.sh/uv/)** (`pyproject.toml` + `uv.lock`) |
| Data exchange | Static **GeoJSON / JSON** files (the contract between scripts and front end) |
| Front end | **HTML + JavaScript** (ES modules, no framework, no build) · **MapLibre GL JS 4.7.1** |
| Hosting | **GitHub Pages** |
| CI/CD | **GitHub Actions** |

No server: Python scripts compute the data and write it to `web/data/processed/`, which is published together with the site.

```
NASA FIRMS / WorldPop / Open-Meteo / OSM ──► scripts/ (Python) ──► web/data/processed/*.geojson|json ──► web/ (MapLibre) ──► GitHub Pages
```

## Getting started

Requirements: [uv](https://docs.astral.sh/uv/getting-started/installation/) (it installs Python 3.11 if needed) and a [FIRMS API key](https://firms.modaps.eosdis.nasa.gov/api/map_key/).

```bash
cp .env.example .env     # set FIRMS_MAP_KEY
make install             # uv sync → .venv with the locked dependencies
make test                # pytest
make data                # run the pipeline → web/data/processed/
make serve               # front end at http://localhost:8000
```

Add a dependency with `uv add <package>` (`uv add --dev <package>` for dev-only tools) and commit `uv.lock` with it.

## Project layout

```
ulinautas/
├── README.md / README.es.md   # this summary / full documentation (Spanish)
├── TODO.es.md                 # roles, tasks, waves
├── Makefile                   # install / data / test / serve
├── pyproject.toml, uv.lock    # dependencies (uv)
├── .env.example               # FIRMS_MAP_KEY=
├── docs/                      # data contract + JSON schemas
├── .github/workflows/         # CI (tests on every PR), deploy, e2e, data refresh
├── data/raw/                  # downloaded FIRMS CSVs (not versioned)
├── scripts/                   # BACKEND: download, harmonize, enrich, validate (+ tests/)
└── web/                       # FRONT END: everything here is published
    └── data/
        ├── sample/            # sample data generated from the contract
        └── processed/         # pipeline outputs (demo/ and live/)
```

## Workflow

- One task in `TODO.es.md` = one branch `feature/<id>-<name>` = one short PR, merged only with green CI.
- `main` always works and is always published.
- Backend (B1–B4): `scripts/`, `docs/`, CI workflows, `Makefile` · Front end / DevOps (F): `web/`, deploy workflow, domain.
