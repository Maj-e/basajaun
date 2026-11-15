# Overview

## What we are building
A web page that shows **wildfire hotspots** detected by NASA satellites, merging two instruments into one dataset:

- **MODIS** (Terra and Aqua satellites, ~1 km resolution, operating since 2000)
- **VIIRS** (S-NPP, NOAA-20 and NOAA-21 satellites, ~375 m resolution)

Both are distributed by **NASA FIRMS** (Fire Information for Resource Management System), but with different resolutions, confidence scales and column names. **Harmonizing them** into one format is the core of the project.

On top of the hotspots, the page adds:
- a **timeline** of fire activity per day and a **playback** where perimeters, spread, evacuation zones and risk evolve with the clock,
- a **map with context layers**: wind, rain, population density, water, roads, fire stations, aquifers, base maps,
- **typed alerts** (population, smoke, wind, water contamination), a **risk score** and an **evacuation estimate** per fire,
- several **episodes** (Sierra Bermeja, Galicia, Chile) and a **live** mode with the latest detections.

See [Features](features.md) for the full tour and [Architecture](architecture.md) for how it is built.

## Team
| Role | Focus |
|---|---|
| B1 — Harmonization | data contract owner, MODIS / VIIRS normalization, deduplication, alerts |
| B2 — Ingestion & fires | FIRMS download, demo area, grouping into fires, weather |
| B3 — Aggregates & population | hotspot export, daily / hourly summaries, population |
| B4 — Data platform | repo, CI, validator, layer manifest, OSM, automatic refresh |
| F — Front end / DevOps | web page, layer loader, filters, calendar, timeline, deployment |

Names and the task list are in [`TODO.md`](../../TODO.md).

## How we work
- **Static site, no server.** Python scripts compute everything and write files to `web/data/`; the page only reads files. See [Data pipeline](data-pipeline.md).
- **The backend ships display-ready data.** Colors and sizes are computed in Python; the front end never decides styles. See [Using the data in the front end](front-end.md).
- **Waves.** Each wave leaves the site working and published; Wave 1 is the MVP (a map of real, harmonized hotspots with filters).
- **Everything in English**: code, UI, docs, data fields.
- **Branches**: `feature/<task-id>-<name>` → PR to `dev` → `dev` merged into `main`, which is published. See [Operations](operations.md).
