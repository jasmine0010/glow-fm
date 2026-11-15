# Method v3 protocol: one frozen test on a storm it has never seen

**Written** before any radar backscatter over Village Creek or Pine Island Bayou was read.
**Receipt:** `research/freeze_receipt_edouard.json`, with SHA-256 hashes of this file, both site files, the run code and all scientific modules. The run refuses to start if any of them has changed. The freeze commit is the dated record.

**Question:** does v3, unchanged, still map flooded forest in a third storm? Isaias and Arthur supplied every earlier test and all v3 development. The Yellow River test (CSI 0.88) shared a storm with a development river.

## 1. What has and has not been seen

**Used to select and set up:** catalog metadata, USGS gauge records, NWS flood stages, news reports, lidar, WorldCover, GFM's static reference-water layer, and each scene's projection, grid limits and valid-sample mask.

**Not seen:** any NISAR backscatter, browse image or interferogram over either river, any GFM or DSWx flood layer (not downloaded), and any truth at any time. Selection is recorded in `THIRD_STORM_SCREEN.md`.

**The upland check was computed on land cover and lidar only**, so it counts pixels without looking at radar.

## 2. Passes, fixed now

Same selection rule as `SECOND_EVENT_PROTOCOL.md` §2(b). All scenes are 40 MHz, PROVISIONAL, EPSG:32615. Every scene passed the pre-run check: all gauges inside the grid, HH and HV present, and 100% valid samples over the reach.

| Order | Role | River | Track | Wet (UTC) | Dry (UTC) | Gauge rises | Timing |
|---|---|---|---|---|---|---|---|
| 1 | **Primary** | Village Creek | 134A | Sep 3 11:35 | Aug 22 11:35 | 4.44 m, 5.64 m | Rising, about a day before crest |
| 2 | **Second river** | Pine Island Bayou | 012D | Sep 7 01:01 | Jul 9 01:01 | 4.71 m, 2.93 m | At crest |
| 3 | Secondary pass | Village Creek | 012D | Sep 7 01:01 | Aug 26 01:01 | 2.85 m, 4.29 m | Receding, under 3 days after crest |
| 4 | Secondary pass | Pine Island Bayou | 134A | Sep 3 11:35 | Aug 22 11:35 | 3.07 m, 1.27 m | Rising, about 3 days before crest |

**Fallback:** if Village Creek's primary pass has fewer than 500 ha of confirmed flooding, it is reported as unjudgeable and Pine Island Bayou becomes the headline result. No other substitution is allowed.

## 3. Frozen method

v3 exactly as in `freeze_receipt_v3.json`: `V3OtsuRule(smooth_px=3, hand_max_m=6, valley_m=4000, min_threshold_db=0.5, landcover=(tree, herbaceous wetland, other), abstain_timing=(late recession,))`.

Truth is unchanged from `V3_YELLOW_PROTOCOL.md` §3: stage at the wet time, ±0.5 m margin, −5 m dry limit, 4 km corridor, connectivity to GFM reference water, within 10 km of a gauge along the valley, permanent water excluded.

The regression check on the Yellow River (Oct 16) reproduced every frozen number exactly, including CSI 0.882268, using this run's code.

## 4. What is reported

For each pass: **v3 CSI on mapped, gauge-supported, non-permanent-water pixels, under instant truth**, with a 2 km block bootstrap (2,000 draws, seed 0) and coverage of confirmed flooding.

Also for each pass: ponding-tolerant scoring, the full corridor, v1 and v2 on the same pixels with paired intervals, and results by land cover. v2 needs 500 upland reference pixels, so it cannot run at Pine Island Bayou, which has 6. That is reported as not computable.

## 5. Reading, fixed in advance

| CSI | Reading |
|---|---|
| 0.60 or higher | Strong on this pass |
| 0.40 to 0.60 | Moderate on this pass |
| Below 0.40 | Weak on this pass |

- **v3 holds up in a third storm** only if **both** rivers' first-listed passes reach 0.40, with Village Creek or the fallback at 0.60 or higher.
- **v3 does not transfer** if **both** first-listed passes are below 0.40.
- **Anything between** is reported as mixed.
- **Beats earlier methods** only if the paired 95% interval is above zero against each method that could run.
- **Coverage below 0.60** of confirmed flooding means no claim for that pass. **Fewer than 500 ha** of confirmed flooding means unjudgeable.
- **Reference, not a target:** Yellow River 0.88 frozen; Pearl 0.61 and Tangipahoa 0.30 in v3 development.

## 6. The upland warning, tested for the first time

`V3_YELLOW_SERIES.md` noticed, after the fact, that low scores came with scene-wide brightening. This is its first test on unseen data.

**Rule:** the median HH change over upland forest (tree cover, more than 12 m above the river, within 15 km of the valley, at least 500 pixels). The warning fires if its size exceeds **0.5 dB**. It uses no truth.

**Prediction:** a warned pass scores below 0.60, and an unwarned pass scores 0.60 or higher.

**Reading:** only Village Creek's two passes can test this, since Pine Island Bayou has too few upland pixels (6). Two right means it survives for further testing. Fewer means it is not supported. Two passes cannot establish it either way.

## 7. Limits stated in advance

- **One storm, one forest region.** This is one new storm over Big Thicket forest. Both rivers feed the Neches and share scenes.
- **Small targets.** Each reach is about 16–17 km between two gauges. Reference water covers only 8 ha of Village Creek's corridor and 65 ha of Pine Island Bayou's, so connectivity seeds and the refined valley line rest on few pixels.
- **Rain on the primary pass.** Edouard's rain was still in the region on Sep 3, so wet soil and canopy may raise the change outside flooded ground.
- **Backwater.** Pine Island Bayou's lower gauge sits above a pump plant, and backwater from the Neches may make it act unlike a free-flowing channel.
- **Long dry gap.** Pine Island Bayou's primary dry pass is 60 days before the wet pass, the edge of the window.
- **Open land.** 10% of Village Creek's corridor and 20% of Pine Island Bayou's is crop, grass or shrub, which v3 never maps.

## 8. After the run

Results go to `outputs/<river>/<pass>/frozen_edouard_metrics.json` once, and are copied unchanged into `research/`. Each attempt is logged before imagery is read. A crash before scoring may be rerun and is disclosed. A bug fix after scoring counts as post-hoc, is labelled that way, and does not replace the first number. Later analysis is labelled post-hoc.
