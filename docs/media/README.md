# Media for the README

| File | What |
|---|---|
| `demo-placeholder.svg` | stand-in shown in the README until the real GIF exists |
| `basajaum_video_historic.gif` | the animated demo shown at the top of the README (640 × 444, 47 s, 18 MB) |

## The demo GIF

**What it should show** (8–15 s, looping): the playback of **Sierra Bermeja (Málaga), Sep 2021**, the default episode — the hotspots of **MODIS (rings) and VIIRS (dots) appearing on the map as one harmonized dataset**, the perimeter growing, the wind particles moving, and the clock and the timeline bars advancing.

Suggested take (follow [`docs/demo-script.md`](../demo-script.md)):
1. Open the site (it opens paused on the peak); press `R` to go back to 8 Sep, then `Space`, speed ×4.
2. Let it run to about 12 Sep, so the fire grows and the alerts appear.
3. Optional last second: tick *Satellite image of the day*.

**How to record it**
- Window about 1280×720, browser zoom 100 %. Record with any screen recorder (e.g. [peek](https://github.com/phw/peek) on Linux, [LICEcap](https://www.cockos.com/licecap/), or OBS and convert with `ffmpeg`).
- Keep it **under ~8 MB** so GitHub renders it quickly: 10–15 fps, width 960–1200 px. With ffmpeg:
  ```bash
  ffmpeg -i demo.mp4 -vf "fps=12,scale=1100:-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse" docs/media/demo.gif
  ```

**In the README** the GIF is the image at the top (`docs/media/basajaum_video_historic.gif`). If you record a new one, replace that file or change the path there. The placeholder SVG is no longer used; delete it when you like.

**Size:** the current GIF is 18 MB; GitHub shows it, but it loads slowly. A 10–15 s cut at 12 fps and about 800 px wide would be around 3–5 MB (see the `ffmpeg` command above).
