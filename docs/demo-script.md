# Demo script

The page is the support of a short story told to the jury. This script decides what the playback screen shows; figures come from the real FIRMS data of each episode (vegetation fires only). The peak (day with most detections) and the strongest fire are **computed by the page**, never hard-coded.

## Main episode — Sierra Bermeja (Málaga, Spain), 8–12 Sep 2021

Default episode of the site. **1,467 detections** (MODIS + VIIRS), every layer computed, **real population alerts**.

| # | Beat | Screen | Presenter says |
|---|---|---|---|
| 1 | **Open** | Dark map of the Costa del Sol, caption *"MODIS + VIIRS merged · Sierra Bermeja (Málaga)"*. Playback paused on **8 Sep**. | "Two NASA instruments, two formats — we merged them into one view." |
| 2 | **Ignition** | `Space`: the first detections appear on the evening of **8 Sep** (12 detections). At **22:19 UTC** the first alert fires: **critical, ≈59,000 people within 5 km**. | "Within hours of the first detection, we know who is threatened: almost 60,000 people within 5 km." |
| 3 | **Peak** | `P` (or the *Peak day* button) jumps to **9 Sep**: **625 detections** in one day, strongest fire **970 MW** (FRP, fire intensity) at 02:07 UTC. In the alert panel, click the fire: the list gives way to its detail (people within 1 / 5 / 10 km, each alert, the fire's figures); alerts are typed — **population** (≈59,000 people within 5 km), **smoke** (*smoke toward ≈135,000 people*), **water** (ash leachate risk for the Marbella aquifer); *All fires* returns to the list, filter it with the chips. | "Day two: 625 detections in 24 hours — and we see who breathes the smoke and which aquifer is at risk." |
| 4 | **Second front** | Playback into **12 Sep**: a second surge (**490 detections**) and two new high alerts. Optional: tick *Satellite image of the day* (NASA VIIRS) to show the burn scar. | "And on day five it flares up again — the alerts follow, fire by fire." |
| 4b | **Rain** | Tick **Rain** in the Map panel, play into **13–15 Sep**: blue rain patches cover the area and the detections fall to **zero** from 13 Sep. | "And then the rain arrives — the satellites stop seeing fire." |
| 5 | **National scale** | Episode list → **Galicia · Aug 2025** (`?demo=1` is kept; it is the default episode): 15–19 Aug 2025. Peak **1,227 burning 1 km cells on 17 Aug**, strongest fire **4,847 MW**, 238 fires; the heatmap shows Ourense ablaze. Zoom in: figures follow the zoom. | "From one fire to a whole country in a click — the record August 2025 season." |
| 6 | **Anywhere** | Episode list → **Chile–Argentina, Feb 2026**: same screen, same pipeline. | "Any fire, anywhere on Earth: the same pipeline, fresh from NASA FIRMS." |

**Zoom tip:** at beat 3, zoom on the fire or click its outline: every figure and alert is recomputed for that fire only (*Show whole area* returns).

## Other episode — Chile–Argentina border, 1–14 Feb 2026

| # | Beat | Screen | Presenter says |
|---|---|---|---|
| 1 | **Open** | Dark map of the Chile–Argentina border. Caption always visible: *"Active fires detected by NASA satellites — MODIS + VIIRS merged · Chile–Argentina border, 33–38° S · 1–14 Feb 2026"*. Select *Chile–Argentina border* in the episode list. Playback paused on **9 Feb**. | "Two NASA instruments, two formats — we merged them into one view." |
| 2 | **Calm** | `Space` starts playback 9 → 11 Feb. Big date ticking. Counter around **44–68 fires/day**. | "A normal summer week: a few dozen fires a day." |
| 3 | **Strongest fire** | Step to **11 Feb, 20:42 UTC** (`→` hour by hour): the *Strongest fire* readout jumps to **1,111 MW** fire intensity (FRP), near 35.94° S, 70.07° W, in **Mendoza, Argentina**, ~30 km east of the border — **31× the strongest fire of the previous 10 days** (36 MW). | "Here — one ignition 31 times more intense than anything we saw before." |
| 4 | **Peak** | Playback resumes into 12–13 Feb: **151 then 149 fires/day** (on 12 Feb: 110 in Argentina, 41 in Chile), the activity curve spikes. *If population data is ready:* halo + "≈ N people within 5 km". | "In 24 hours the region goes from 68 to 151 active fires." |
| 5 | **Close** | Pause on the peak, 14-day activity curve visible. | "This works for any region and period — the same pipeline, fresh from FIRMS every few hours." |

## Controls (presenter)
| Key | Action |
|---|---|
| `Space` | Play / pause |
| `P` | Jump to the peak day |
| `←` / `→` | Step one hour back / forward |
| `R` | Restart from 9 Feb |

- The shared link (no parameter) **loops automatically** for the stand and for people opening the link alone; it no longer pauses by itself (the spark callout and the automatic pauses were removed on 15 Nov 2026).
- `?demo=1` opens **paused**: the presenter controls the timing with the keyboard. It is kept when switching episode in the list (the separate Demo button was removed).
- The small tab on top of the timeline folds the chart down to the clock and the controls, to free the map.

## What the backend must precompute
- **Exclude FIRMS `type 2`** (static land sources): 250 of 1,075 detections, concentrated in two ~1 km cells that fire every day — most likely industrial sites, not wildfires. Only `type 0` (presumed vegetation fire) is kept.
- `daily_summary.json`: fires per day, FRP max per day, cumulative count.
- **Story markers, computed from the data — never hard-coded**: `peak_day` (day with the most fires); the strongest hotspot shows in the *Strongest fire* readout (no separate spark marker any more). They must still work if the area or dates change.
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
