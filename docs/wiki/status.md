# Status and decisions

_Last updated: 2026-11-14._

## Where we are
| Task | What | Status |
|---|---|---|
| W0-B4 | Repo, uv, Makefile, CI | ✅ merged |
| W0-F1 | Web skeleton + GitHub Pages deploy | ✅ merged, published |
| W0-B2 / W1-B2 | FIRMS config + downloader | ✅ merged in `dev`; first real download done (1,075 detections) |
| W1-F1 | Generic layer loader + hotspot layer | ✅ merged in `dev` (provisional sample data); not yet on `main` |
| W0-B1 | Frozen contract + generated sample data | ⏳ in progress (B1) |
| W0-B3 | Volume measurement | ✅ answered by the first download: one file is enough |
| W1-B1, W1-B3, W1-B4, W1-F2 | Harmonization, export, validator, filters | next → MVP |

Live site: https://maj-e.github.io/ulinautas/ (shows `main`).

## Open questions
- **Demo area:** keep south-central Chile, 1–14 Feb 2026? Activity peaks on 12–14 Feb; extending `END_DATE` may show the end of the episode.
- **FIRMS `type` column:** filter out static sources (industry, volcanoes, offshore)?
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

| 2026-11-14 | Contract field names follow B1's implementation: `updated_at`, `timestamp_utc`, `day_night`, `border`, `active`, legend `text`, `total_frp` | B1 owns the contract; doc, front end, `fires.py`, `weather.py` aligned |

Add a row whenever the team makes a decision that someone could later ask "why?" about.
