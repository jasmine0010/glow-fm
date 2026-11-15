# C-band against L-band: results

**Rules:** `C_BAND_PROTOCOL.md`, written before any Sentinel-1 value was read. It was not in a commit before the run. Data: `c_band_results.json`. Script: `scripts/c_band_check.py`.

**Run note:** the protocol first named NASA ASF's OPERA RTC-S1 files. ASF refused them until the account accepted a further licence, so, before any radar was read, the protocol was changed to read the same two Sentinel-1 scenes from Microsoft Planetary Computer's open `sentinel-1-rtc` collection. A first run stopped before reading anything, because GDAL was told to accept only `.tif` and the files end in `.tiff`. The measurement was then run once. Later runs only added the site's pictures and reproduce `c_band_results.json` byte for byte. One of them stopped on the picture check: NISAR's recomputed contrast came out +1.06 dB, because the live catalog query that lists NISAR's baseline scenes came back short. The script now pins the baseline to the five dates the published build used (Jun 21, Jul 15, Jul 27, Aug 20, Sep 1) and stops if the catalog lists anything else. No reported number changed.

**No frozen score changes.**

## Answer

**C-band shows little of it.** On the same flooded forest on the Pearl, Sentinel-1's C-band barely changed, while NISAR's L-band brightened.

| Band | Date | Flooded forest (0.5–2 m under water) | Dry forest (1–3 m above water) | Flood contrast |
|---|---|---|---|---|
| **C-band VV** (Sentinel-1) | Jul 5 | −0.59 dB | −0.75 dB | **+0.15 dB** |
| C-band VH (Sentinel-1) | Jul 5 | −0.56 dB | −0.72 dB | +0.16 dB |
| **L-band HH** (NISAR) | Jul 3 | +0.98 dB | −0.15 dB | **+1.12 dB** |
| L-band HV (NISAR) | Jul 3 | +0.11 dB | −0.11 dB | +0.22 dB |

The C-band groups cover 15,392 ha of flooded forest and 2,965 ha of dry forest. The best C-band contrast, +0.16 dB, is under the protocol's 0.5 dB line, so the reading is fixed by the rules.

The whole Sentinel-1 scene reads about 0.7 dB darker on Jul 5 than on Jun 16, on dry and flooded forest alike. That is consistent with a calibration difference between Sentinel-1A and 1D or a change in the forest, and the contrast cancels it, as the protocol intended.

## The response curves

Median change in 0.5 m bins of water above ground (tree cover, gauge-supported). C-band stays between −0.8 and −0.5 dB from 5 m above the water to 2 m under it. L-band HH sits near −0.2 dB on dry ground, then rises through +0.4 dB at the waterline to +1.2 dB with 1.5–2.5 m of water. HV stays within about 0.3 dB throughout, the double-bounce pattern the site describes.

## Pictures on the site (description, not part of the test)

`app/data/pearl/105A_jul03/cband.png` and `lband.png` draw each band's change on the site's shared scale, relative to its own dry forest, the reference the contrast uses. The script recomputes NISAR's change and stops unless it reproduces the published +1.12 dB.

- Forest more than 1 dB brighter than dry forest: about **14,200 ha** in L-band, about **2,000 ha** in C-band, much of it scattered single-scene noise.
- **NISAR's map is not complete.** Its valid radar covers the whole reach, but HH barely changed along the middle third of the river, where the estimate says the forest was flooded. Either L-band missed it there or the estimate is wrong there; the hidden-gauge test found the estimate unreliable across long gaps between gauges. This isn't resolved here.

## What the site may say

- On the Pearl, in July, C-band barely changed over flooded forest (+0.2 dB against dry forest) while L-band brightened (+1.1 dB).
- The official map (GFM, built on Sentinel-1) marked 0.75 ha of the 16,731 ha the gauges point to on Jul 5.

**Must accompany it:** one river, one flood, two dates 37 hours apart; NISAR's numbers on this river are development numbers; NISAR missed or under-saw the middle reach.

**Not supported:** that C-band never sees flooded forest, anywhere or in any season, or that this gap explains GFM's mask, which excludes dense forest by design.
