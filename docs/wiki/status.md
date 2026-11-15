# Status and decisions

_Last updated: 2026-11-14._

## Where we are
| Task | What | Status |
|---|---|---|
| W0-B4 | Repo, uv, Makefile, CI | ✅ merged |
| W0-F1 | Web skeleton + GitHub Pages deploy | ✅ merged, published |
| W0-B2 / W1-B2 | FIRMS config + downloader | ✅ merged in `dev`; first real download done (1,075 detections) |
| W1-F1 | Generic layer loader + hotspot layer | ✅ merged in `dev` (provisional sample data); not yet on `main` |
| W1-F0 | Playback screen mockup + demo script | ✅ `docs/mockup/`, `docs/demo-script.md` |
| W2-F2 | Playback screen implemented in `web/` | ✅ merged |
| W1-B3 | Hotspot export (825 vegetation fires, `type 2` excluded) | ✅ merged (#19) |
| W1-B4 | Contract validator + manifest | ✅ merged (#16) |
| W2-B1 | MODIS / VIIRS deduplication | ✅ merged (#20) — not yet applied to the exported file |
| W1-F2 | Site switched to the real data (`data/manifest.json`) | ✅ merged → **MVP online** |
| W2-F3 | Figures follow the visible area | ✅ merged |
| W3-F2 | Alert panel (halo + label on the map, collapsed list) | ✅ shows once `processed/alerts.json` exists (needs the population raster for `exposure.py`) |
| W0-B1 | Frozen contract + generated sample data | ✅ merged (`make sample`); contract names follow B1's code |
| W1-B1 | MODIS / VIIRS normalization + tests | ✅ merged (`harmonize.py`) — FIRMS `type 2` filter still to add |
| W2-B2 | Fires (DBSCAN grouping) | ✅ merged (`fires.py`) |
| W3-B2 | Wind + weather | ✅ merged (`weather.py`) |
| W0-B3 | Volume measurement | ✅ merged (`docs/volume.md`): one file is enough |
| W1-B3, W1-B4, W1-F2 | Export, validator, filters | next → MVP |

Live site: https://maj-e.github.io/ulinautas/ (shows `main`).

## Open questions
- **Demo area:** keep the Chile–Argentina border, 33–38° S episode, 1–14 Feb 2026? Activity peaks on 12–14 Feb; extending `END_DATE` may show the end of the episode.
- **FIRMS `type` column:** recommended to exclude `type 2` (250 of 1,075 detections, two industrial-looking cells) — B1 to confirm in W1-B1/W1-B3.
- **Legend and popup:** add size / stroke entries to the legend and human labels + units to the popup (needs a small contract change).

## Decisions log
| Date | Decision | Why |
|---|---|---|
| 2026-11-14 | Static site, Python pipeline, no backend for the demo | nothing can go down during the demo; FIRMS itself is ~3 h behind real time |
| 2026-11-14 | Plain JS + MapLibre, no framework, no build | one front-end developer, no setup time |
| 2026-11-14 | Backend ships pre-styled data + a layer manifest; one generic loader in the front end | 4 backend vs 1 front end: new layers need no front-end code |
| 2026-11-14 | Contract frozen before filters; validator in CI; site online from Wave 0; feature toggles (`active`) | dev council verdict: the contract is the only hard-to-undo piece |
| 2026-11-14 | Everything in English (code, UI, docs, data fields); Spanish `.es.md` copies removed | team rule |
| 2026-11-14 | Branch flow `feature/*` → `dev` → `main` (published) | `main` stays stable for the jury |
| 2026-11-14 | Repository made public | GitHub Pages on a free account requires it |
| 2026-11-14 | FIRMS download in 5-day chunks, `_NRT` / `_SP` chosen by data age | as implemented by B2 |
| 2026-11-14 | FIRMS key in `.env` locally and in the `FIRMS_MAP_KEY` repository secret | the published site never needs it |

| 2026-11-14 | Demo script: open 9 Feb → spark (11 Feb 20:42 UTC, 1,111 MW, 31× previous max) → peak (12 Feb, 151 fires) | the data tells this story; see `docs/demo-script.md` |
| 2026-11-14 | Design (council verdict): story-led playback screen, dark theme, full-screen map, dominant timeline, 2 computed readouts, legend on the map, alerts only when computed, no "Live" label until wired, presenter keys + `?demo=1` | jury-first but credible for professionals; never show uncomputed numbers |
| 2026-11-14 | Exclude FIRMS `type 2` from the hotspots (proposal) | static sources are not wildfires; pending B1 |
| 2026-11-14 | Contract field names follow B1's implementation: `updated_at`, `timestamp_utc`, `day_night`, `border`, `active`, legend `text`, `total_frp` | B1 owns the contract; doc, front end, `fires.py`, `weather.py` aligned |

| 2026-11-14 | Figures follow the visible area; then isolate a fire, then regions; then **episodes** (any place on Earth, one episode at a time) | answers "how do we focus on one zone" and "can we show more than Chile" without drowning the story |

| 2026-11-14 | Area named "Chile–Argentina border, 33–38° S" instead of "Central Chile" | the spark (1,111 MW) and 110 of the 151 peak-day fires are in Mendoza, Argentina; 679 of 825 fires overall are in Chile |
| 2026-11-14 | MapLibre GL 4.7.1 self-hosted in `web/vendor/` | the demo no longer depends on the unpkg CDN (it failed once during testing) |

| 2026-11-14 | Demo refocused on Spain: default episode **Sierra Bermeja (Málaga), Sep 2021**; front reads `episodes.json`, episode selector, world land outline | real episode with every layer computed, alerts included |

| 2026-11-14 | Demo episodes: Málaga (story + alerts), Spain · Aug 2025 (national scale, 5–7 days, medium/high confidence, no OSM; Natural Earth major water), Chile (other continent); Madrid dropped | volume and readability at national scale |
| 2026-11-14 | Persistent Map panel (layers, satellite, alerts on map); alert circles only when ticked, list always open; heatmap when zoomed out; Demo button | the screen was saturated with population labels and overlapping circles |

| 2026-11-15 | Front: spark callout and automatic pauses removed (peak day kept as a highlighted bar + button); Demo button removed (same episodes as the selector, `?demo=1` kept); single alert panel with a per-fire detail view linked to fire isolation; foldable timeline; readable popups | the spark beat felt forced and the screen had redundant controls; the alert list did not say where each fire was |

Add a row whenever the team makes a decision that someone could later ask "why?" about.
