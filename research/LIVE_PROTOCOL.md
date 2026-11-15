# Live cases: protocol

**What this is:** the frozen method v4, run automatically on floods happening now, so anyone can see it work on a flood the
method has never seen. US results are scored against the gauge-and-lidar estimate. Results elsewhere are published
unscored. This file is fixed before the first scored run, and `research/freeze_receipt_live.json` records its hash with
the code's. `scripts/live_cases.py` refuses a scored run if any of those files has changed.

## Which floods

- **US:** every NOAA river gauge whose latest reading is at minor, moderate or major flood stage, linked to a USGS gauge.
  The flood began when the current run above minor flood stage began in NOAA's 30-day record. If the run fills the whole
  record, the record's start is used and the case says so. Up to 6 cases per run, major first.
  Tidal gauges (water levels against mean lower low water, or named as tide gauges) are left out: they measure
  coastal water, and the method maps river floods. Gauges on lakes (named "... Lake near" or "... Lake at") are left
  out for the same reason.
- **Elsewhere:** GDACS floods outside the US with at least one NISAR pass in the saved worldwide list
  (`app/data/dashboard/world_floods.json`), red and orange alerts first, then most passes. Up to 4 per run. GDACS gives
  one point per flood, so the box may not contain the flooding.

## Which NISAR scenes

- The box is 24 km square around the gauge or GDACS point, on a 50 m grid in the scene's UTM zone, lined up with the
  scene's own pixel edges, read from the scene file.
- **Flood scene:** the newest 40 MHz dual-polarization (HH and HV) GCOV scene covering the point, acquired after the flood
  began. That is the kind of scene the tested rivers used; floods with only other kinds aren't run, and say so.
- **Earlier scenes:** up to the 6 newest scenes from the same track, frame and mode in the 60 days before the flood began.
  At least 3 are needed, or the case isn't run, and the reason is published.
- Scenes come from `NISAR_L2_GCOV_PROVISIONAL_V1` before 2026-10-21 17:07 UTC and `NISAR_L2_GCOV_V1` from then on, so no
  pass counts twice.

## Inputs

| Input | US | Elsewhere |
|---|---|---|
| Heights | 3DEP lidar, bare earth | Copernicus GLO-30 surface model, which includes trees |
| River | USGS river line through the gauge (NLDI main stem, 20 km up and down), re-centred on mapped water | Nearest water in ESA WorldCover |
| Height above river | Along the river line, as on the tested rivers | Height above the nearest mapped water |
| Land cover | ESA WorldCover 2021 | ESA WorldCover 2021 |
| Flood timing | USGS gauges on the main stem in the box; nearest gauge along the river | None, so no pass is skipped for timing |

## Method

Method v4 with the settings in `research/freeze_receipt_v4.json`, unchanged: median of the earlier scenes as the
baseline, HH change or HH minus HV chosen by the scene, forest and wetland within 6 m of the river, Otsu's cut-off with a
0.5 dB floor, late-recession pixels skipped, and the confidence label.

The method itself maps permanent water too (its land-cover rule counts water as "other"). Published areas and maps
leave out permanent water, as the score does: ESA WorldCover water, plus the USGS river line for US cases.

## Score (US only)

- The estimate uses the tested rivers' rules: water surface from USGS gauges in the box at the flood scene's time (water
  elevation above NAVD88, USGS 63160, where a gauge publishes it; otherwise stage plus the gauge datum), the
  4,000 m corridor, the ±0.5 m margin, 5 m dry-height limit and connection to the channel. Gauge heights use the gauge
  datum with no NGVD29-to-NAVD88 offset, as on the tested rivers.
- Scored ground lies within 10 km of a gauge along the river, or 3 km when only one gauge is usable, minus mapped water.
- The score is the overlap score (CSI) on mapped pixels, with a 95% range from 2,000 resamples of 2 km blocks along the
  river. Every result is published as run, including failures.
- No usable gauge (no NAVD88 elevation and no known datum, or no reading at the scene's time): the case is published
  unscored and says why.

## Development before the freeze

Development runs on the floods listed when this was written built inputs and flood maps, never the estimate or a score.
They led to these data-handling rules, each made to get the inputs right, not to change the method: tidal and lake gauges
left out, only 40 MHz scenes used (others have 20 m pixels), the grid lined up with each scene's pixel edges, permanent
water left out of published areas, NAVD88 water elevation used where a gauge publishes it, and one retry after a
dropped connection.

## Running once

- Each case is a flood and its flood scene. It runs once. A published case is never rerun or overwritten, so a later run
  can add new cases but can't replace an old score.
- Each attempt is logged in `research/live_attempts.log` before any imagery is read.
- Development runs (`--dev`) build inputs and run the method, but never build the estimate or a score. They're written to
  `outputs/live_dev`, which isn't published.

## What it isn't

- Live cases aren't part of the tested results on the story and evidence pages, which stay as they are.
- A US score is one fresh test on one river. It can be low, and a single case says little about the method in general.
- The browser lets visitors change the method's settings and see the map and score change. Only the frozen run's score
  counts; settings chosen after seeing a score are tuning, not testing.
