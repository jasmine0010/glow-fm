# C-band against L-band on the same flooded forest

**Written before any Sentinel-1 file was downloaded or read.** It was not in a commit before the run.

## Question

The site says C-band radar (Sentinel-1, behind today's global flood maps) mostly scatters in the leaves, so it sees little water under trees, while NISAR's L-band reaches the forest floor. That claim has not been measured in this project. Does C-band brighten over flooded forest the way L-band does, on the same forest within two days?

## Data, fixed now

- **River:** Pearl, LA/MS, the June–July 2026 flood after Tropical Storm Arthur. It is the only flood here with a Sentinel-1 scene within two days of a usable NISAR pass. Satilla had no Sentinel-1 scene during the flood, and Yellow's scenes (Oct 10 and 22) fall beside a red-light pass and a pass the method declines to map.
- **L-band:** NISAR 105A, Jul 3, HH and HV change from the per-pixel median of other same-track scenes, exactly as already published in `app/data/manifest.json` (`drivers.contrast` for `pearl/105A_jul03`). Those numbers are fixed now: HH +0.98 dB below water and −0.15 dB above, a contrast of **+1.12 dB**; HV +0.11 and −0.11, a contrast of +0.22 dB.
- **C-band:** Sentinel-1 radiometrically terrain-corrected gamma-0, VV and VH, relative orbit 165. Before the flood: **Jun 16**, Sentinel-1A (scene `S1A_IW_GRDH_1SDV_20260616T000216`), the day before Arthur's rain began. During the flood: **Jul 5**, Sentinel-1D (scene `S1D_IW_GRDH_1SDV_20260705T000135`), about 37 hours after NISAR's pass. Change is dB(Jul 5) minus dB(Jun 16), area-averaged from linear power onto the project's 50 m Pearl grid.
- **Source, changed before any radar was read:** this protocol first named OPERA RTC-S1 from NASA's ASF archive. ASF refused the files until the account accepted a further licence, so the same two scenes are read instead from Microsoft Planetary Computer's `sentinel-1-rtc` collection (RTC by Catalyst, 10 m, CC-BY-4.0, anonymous access). Only the Pearl box is read. No Sentinel-1 value had been seen from either source when this changed, and nothing else in this protocol changed.
- **Water:** the gauge-and-lidar estimate at each sensor's own time (Jul 3 for NISAR, Jul 5 for Sentinel-1), unchanged from `V3_YELLOW_PROTOCOL.md` §3.

## Measure, fixed now

The same as `src/hidden_floods/drivers.py` `summarize`, so the two bands are read identically:

- Ground: ESA WorldCover tree cover, inside the corridor, gauge-supported, not permanent water, with valid radar.
- **Flood contrast** = median change where the estimate puts water 0.5–2 m above the ground, minus median change where the ground is 1–3 m above the water.
- Also the response curve: median change in 0.5 m bins of water above ground, bins under 10 ha left out.
- Both groups need at least 10 ha, or there is no reading.

A calibration offset between Sentinel-1A and 1D shifts both groups equally, so the contrast cancels it.

## Reading, fixed now

Use the **larger** of the VV and VH contrasts, which is the reading most generous to C-band.

| Best C-band contrast | Reading | What the site may say |
|---|---|---|
| Under 0.5 dB | **C-band shows little of it** | On the Pearl, C-band barely changed over flooded forest while L-band brightened. |
| 0.5 dB up to +1.12 dB | **C-band shows it, but less** | C-band saw some of it, less clearly than L-band. |
| +1.12 dB or more | **C-band shows it as well or better** | The site must drop the claim that C-band can't see under these trees, and say the gap in GFM is its mask, not the physics, on this river. |

## Limits stated first

- One river, one flood, one pair of dates. It says nothing general about C-band.
- The dates differ by about 37 hours, and the water dropped or rose in between. Each band is read against its own day's estimate.
- NISAR's change uses a median of several earlier scenes; Sentinel-1's uses one scene. Single-scene change is noisier, which medians over many pixels partly absorb.
- Incidence angles and polarizations differ: NISAR has HH, Sentinel-1 has VV and VH, and HH is the polarization that favours double bounce.
- The Pearl helped build NISAR's method, so NISAR's numbers here are development numbers. Sentinel-1's are not tuned to anything.
- The estimate is a model, not a sighting of water.
