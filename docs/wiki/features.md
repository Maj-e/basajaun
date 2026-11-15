# Features

What the published page does today (state of `dev`, 15 Nov 2026). For the file formats behind each item see [Front-end layers](../frontend_layers.md); for the story told on stage see the [demo script](../demo-script.md).

## One dataset from two satellites

**MODIS** (Terra, Aqua; ~1 km) and **VIIRS** (S-NPP, NOAA-20, NOAA-21; ~375 m) are downloaded from NASA FIRMS, normalized to one schema and deduplicated: a fire seen by both becomes **one hotspot** with `detected_by: ["MODIS", "VIIRS"]`. On the map, hotspots are coloured by fire intensity (FRP); MODIS pixels are drawn as rings and VIIRS as dots, so the origin is still readable. See [Data sources](data-sources.md) and the [harmonization table](../../README.md#modis--viirs-harmonization).

## Episodes

Each episode is a place and a period with its own data and manifest (`web/data/episodes.json`), chosen from the selector in the header.

| Episode | What it shows |
|---|---|
| **Sierra Bermeja (Málaga) · 8–20 Sep 2021** (default) | the story: 1,467 detections, every layer, real alerts |
| **Galicia · 15–19 Aug 2025** | regional scale: 4,301 hotspots, 238 fires, peak of 1,227 burning 1 km cells |
| **Chile–Argentina border · 1–14 Feb 2026** | the same pipeline on another continent |
| **Live** (published site only) | last 48 h of the Iberian Peninsula, refreshed every 30 min; not in the selector yet |

## Playback

- Timeline strip with the **fires per day** (lighter bar = peak day), a clock, play / pause, speed ×1 ×2 ×4, **Peak day** button, and keys `Space` `P` `←` `→` `R`.
- Opens **paused on the peak**; stops at the last day instead of looping; the strip marks the **last detection** and says when only burned area remains.
- **Fire perimeters grow and shrink with the clock**: each is rebuilt from the hotspots detected so far. Spread, evacuation and risk are computed **every 6 h of each fire's life** and follow the clock too. A fire with no detections for 24 h stops being active: its zones disappear and the perimeter stays faint as burned area.
- **Wind particles** (surface wind, 10 m, hourly) move while it plays and freeze when it is paused. Rain can be switched on.
- Header figures (**active fires**, **strongest fire**) and the timeline follow the **visible area**: zoom on a zone, or click a fire, and everything is recomputed for it.

## Map layers

Switched on at start: hotspots, fires, roads, groundwater, wind. Others in the Map panel: 6 h spread, population density, rain, water, rivers, fire stations, water points for firefighting, regions, evacuation zone, fire risk.

**Base maps**: Topo (relief), Satellite (cloud-free Sentinel-2) and Dark; plus the *Satellite image of the day* (NASA GIBS) over any of them. Licences and attribution: [`docs/licenses.md`](../licenses.md).

## Predictive ignition risk (AI)

A calibrated logistic-regression model scores, for every cell of a **12 × 12 grid** and every day, the probability that a fire starts there, from weather, distance to roads / fire stations / water, population and slope. The layer shows four levels (critical → low, relative to the episode), a popup with the **drivers** and a **recommended action**, and stays on the map for the whole day. It answers *where could a fire start*, while the layers below describe fires that already exist. How it works and its limits: [AI module](ai-risk.md).

## Alerts, risk and evacuation

- **Typed alerts** per fire: **population** (people within 1 / 5 / 10 km, wind toward them), **smoke** (people downwind), **strong wind** and **water contamination** (ash leachate over a vulnerable aquifer).
- **Risk score** per fire (low / medium / high / extreme) from fire intensity, people, smoke and wind; **evacuation estimate**: people inside the fire + 1 km + 6 h spread, plus the people on warning within 5 km.
- One alert panel with a per-fire **detail view**; clicking a fire isolates it on the map.

## Reliability

Everything the page draws is a file validated against the [data contract](../data_contract.md) in CI; the published URL is checked end to end (`scripts/check_site.py`), and an invalid refresh never reaches the site. See [Operations](operations.md).

## Known limits

Listed with ideas to fix them in [`TODO.md`](../../TODO.md#5-future-improvements-found-while-polishing-the-demo-15-nov-2026) (section 5): the map can look slightly behind the timeline on slow machines, bars count per day, Galicia is heavy (9 MB), some licences are still to verify.
