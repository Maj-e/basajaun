# Demo script

The page is the support of a short story told to the jury. This script decides what the playback screen must show and what the backend must precompute. Validated by the design council (2026-11-14); figures come from the real FIRMS download (vegetation fires only, see below).

**Episode:** central Chile, 1–14 Feb 2026 · **825 vegetation fires** detected by MODIS + VIIRS.

| # | Beat | Screen | Presenter says |
|---|---|---|---|
| 1 | **Open** | Dark map of central Chile. Caption always visible: *"Active fires detected by NASA satellites (MODIS + VIIRS) — Central Chile, 1–14 Feb 2026"*. Playback paused on **9 Feb**. | "Two NASA instruments, two formats — we merged them into one view." |
| 2 | **Calm** | `Space` starts playback 9 → 11 Feb. Big date ticking. Counter around **44–68 fires/day**. | "A normal summer week: a few dozen fires a day." |
| 3 | **Spark** | Auto-pause on **11 Feb, 20:42 UTC**: one hotspot at **1,111 MW** fire intensity (FRP), near 35.94° S, 70.07° W — **31× the strongest fire of the previous 10 days** (36 MW). | "Here — one ignition 31 times more intense than anything we saw before." |
| 4 | **Peak** | Playback resumes into 12–13 Feb: **151 then 149 fires/day**, the activity curve spikes. *If population data is ready:* halo + "≈ N people within 5 km". | "In 24 hours the region goes from 68 to 151 active fires." |
| 5 | **Close** | Pause on the peak, 14-day activity curve visible. | "This works for any region and period — the same pipeline, fresh from FIRMS every few hours." |

## Controls (presenter)
| Key | Action |
|---|---|
| `Space` | Play / pause |
| `P` | Jump to the peak day |
| `S` | Jump to the spark (strongest hotspot) |
| `←` / `→` | Step one hour back / forward |
| `R` | Restart from 9 Feb |

- The shared link (no parameter) **loops automatically** for the stand and for people opening the link alone; it pauses on spark and peak like the presenter does.
- `?demo=1` opens **paused on 9 Feb**: the presenter controls the timing with the keyboard.

## What the backend must precompute
- **Exclude FIRMS `type 2`** (static land sources): 250 of 1,075 detections, concentrated in two ~1 km cells that fire every day — most likely industrial sites, not wildfires. Only `type 0` (presumed vegetation fire) is kept.
- `daily_summary.json`: fires per day, FRP max per day, cumulative count.
- **Story markers, computed from the data — never hard-coded**: `peak_day` (day with the most fires), `spark` (hotspot with the highest FRP: time, position, FRP, ratio to the previous max). They must still work if the area or dates change.
- `hourly_series.json`: active fires and FRP per hour, for the activity curve.
- "People within 5 km" only if population and exposure (W3-B3, W3-B1) are ready and checked; otherwise the line is not shown.

## Fallbacks
- No population data → no alerts on screen at all (no placeholder numbers).
- Network or tiles down → a screen recording of the playback (to record once the MVP is published).

## Real figures (vegetation fires, per day)
| Feb | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Fires | 35 | 94 | 5 | 7 | 16 | 33 | 21 | 32 | 44 | 59 | 68 | **151** | **149** | 111 |
| FRP max (MW) | 17.7 | 13.0 | 9.2 | 3.8 | 15.3 | 28.7 | 28.6 | 36.0 | 28.3 | 32.1 | **1111.1** | 95.1 | 217.7 | 63.7 |
