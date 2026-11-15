# Status and decisions

_Last updated: 2026-11-15 (state of `dev`)._

## Where we are

The full path works end to end and is published: FIRMS download → harmonized hotspots → fires → enrichment → zones and alerts → validated files → the page. Task by task: [`TODO.md`](../../TODO.md). What the page does: [Features](features.md).

| Area | Done | Still open |
|---|---|---|
| **Data (backend)** | download, MODIS / VIIRS harmonization, deduplication, fires, time series, population, weather and surface wind, OSM layers and accessibility, water points and aquifers, typed alerts, risk score and evacuation, spread projection, per-snapshot zones, compact files, contract validator, manifest per episode, automatic live refresh with validation | regions task (W3-B6) to close, slope and land cover (W5-B3), alerts on recent data (W4-B1), grouped alerts (W3-B9), layer descriptions in the manifest (W3-B10; implemented, not yet merged), notifications, scalability |
| **Front end** | layer loader, Map panel, timeline and playback, figures that follow the visible area, isolate a fire, alert panel with typed alerts, wind particles, rain, base maps (Topo / Satellite / Dark), episode selector, demo banner, mobile pass, versioned deploy | calendar and filters (W1-F2, W2-F1), region selector, grouped alerts panel, Live button (W4-F1), data transparency (W5-F3), i18n and animation export |
| **Episodes** | Sierra Bermeja (default), Galicia, Chile–Argentina; live published by the refresh workflow | more places: add an entry to `episodes.json` and run `make data EPISODE=<id>` |
| **AI module** | municipal ignition-risk model, features, tests and layer finished by Sergey on branch `IA` | merge into `dev` (conflicts to solve, see [AI module](ai-risk.md#merging-it-into-dev)), regenerate the manifests, add Galicia |
| **Docs** | README, wiki, data contract, front-end layers + changelog, demo script, licences | demo GIF for the README ([`docs/media/`](../media/README.md)); licences marked "to verify" |

Live site: https://maj-e.github.io/basajaun/ (shows `main`). Known limits and ideas for after the demo: [`TODO.md`](../../TODO.md#5-future-improvements-found-while-polishing-the-demo-15-nov-2026) (section 5).

## Open questions
- **AI branch:** `IA` is ready but started from an older `dev` (Los Angeles still listed, `app.js` / `loader.js` changed on both sides). Its map repaint only on integer hours may help the playback-sync item below.
- **Playback sync:** the map can look slightly behind the timeline on slow machines (repaint speed and 24 h trails); options are listed in `TODO.md`.
- **Episode length:** Sierra Bermeja runs to 20 Sep but its last detection is 12 Sep; shorter versions felt cut, so the timeline marks the last detection instead.
- **Licences:** several sources are marked "to verify" in [`docs/licenses.md`](../licenses.md); check them before any public launch (the satellite base map is non-commercial only).
- **Repository name:** the repository is now `basajaun` (was `ulinautas`); the old Pages URL no longer works and `scripts/check_site.py` / `e2e.yml` still default to it.

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
| 2026-11-14 | Demo episodes: Málaga (story + alerts), Galicia · Aug 2025 (regional scale, 5 days, medium/high confidence, no OSM; Natural Earth major water; was the whole peninsula until 2026-11-15, too heavy), Chile (other continent); Madrid dropped | volume and readability at national scale |
| 2026-11-14 | Persistent Map panel (layers, satellite, alerts on map); alert circles only when ticked, list always open; heatmap when zoomed out; Demo button | the screen was saturated with population labels and overlapping circles |
| 2026-11-15 | Front: spark callout and automatic pauses removed (peak day kept as a highlighted bar + button); Demo button removed (same episodes as the selector, `?demo=1` kept); single alert panel with a per-fire detail view linked to fire isolation; foldable timeline; readable popups | the spark beat felt forced and the screen had redundant controls; the alert list did not say where each fire was |
| 2026-11-15 | Playback: zones (spread, evacuation, risk) computed per 6 h fire snapshot; perimeters rebuilt in the browser from the hotspots; a fire is active until 24 h after its last detection, then only faint burned area; the player stops at the last day | scrubbing back used to show the final state at every hour |
| 2026-11-15 | Wind particles on by default, frozen (not animated) while paused; the page opens paused on the peak of the default episode | the demo starts on its most telling frame and stays still when the presenter pauses |
| 2026-11-15 | README rewritten as the entry point: what it does, the demo GIF, and a documentation map linking the whole wiki | one place to start for jurors and new contributors |
| 2026-11-15 | Ignition risk by AI: logistic regression + Platt calibration on a 12 × 12 grid, relative levels per episode (12.5 / 25 / 34.7 / rest %), shown as a daily temporal layer (`hold_hours: 24`) | a predictive layer next to the observed ones; relative levels keep the map readable and honest about being episode-relative |

Add a row whenever the team makes a decision that someone could later ask "why?" about.
