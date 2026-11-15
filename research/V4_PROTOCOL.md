# Method v4 protocol: one frozen test on three new rivers

**Written** before any radar backscatter over the Pee Dee, Neuse or lower Sabine was read.
**Receipt:** `research/freeze_receipt_v4.json`, with SHA-256 hashes of this file, the scene list, the site files, the run code and all scientific modules. The run refuses to start if any of them has changed. The freeze commit is the dated record.

**Question:** does v4 hold up on floods it has never seen, and is it better than v3 on the same pixels? v4 scored 0.63 against v3's 0.59 in development (`V4_DEVELOPMENT.md`). That gain may not survive.

## 1. What has and has not been seen

**Used to select and set up:** catalog metadata, USGS gauge records, NWS flood stages, lidar, WorldCover, GFM's static reference-water layer, and each wet and dry scene's projection, grid limits and valid-sample mask. Selection is recorded in `THIRD_STORM_SCREEN.md`.

**Not seen:** any NISAR backscatter, browse image or interferogram over these rivers, any GFM or DSWx flood layer (not downloaded), and any truth at any time.

## 2. Passes, fixed now

The selection rule is `SECOND_EVENT_PROTOCOL.md` §2(b). All scenes are 40 MHz and PROVISIONAL. Wet and dry scenes passed the pre-run check: all gauges inside the grid, HH and HV present, and 100% valid samples over the reach. Scenes are listed in `v4_test_scenes.json`.

| Order | River | Track | Wet (UTC) | v3's dry pass (UTC) | v4 baseline scenes | Gauge rises | Timing | Event |
|---|---|---|---|---|---|---|---|---|
| 1 | **Pee Dee, SC** | 098D | Jul 27 00:10 | Jul 3 | 7 | 2.91, 3.76, 3.94, 3.96, 3.14 m | Receding at Cheraw, near crest at Bennettsville, rising below | July front |
| 2 | **Neuse, NC** | 090A | Jul 26 10:21 | Sep 12 | 7 | 2.98, 2.83, 1.88, 1.07 m | Rising at all four | July front |
| 3 | **Lower Sabine, TX/LA** | 134A | Jul 17 11:35 | Aug 22 | 9 | 1.32, 1.37, 2.89 m | Receding at two, near crest at Ruliff | Mid-July rain |

**The headline is the first river in this order with at least 500 ha of confirmed flooding.** Rivers under 500 ha are reported as unjudgeable. No other substitution is allowed.

## 3. Frozen method

`V4Rule(baseline=median, signal=adaptive, flood_check_db=None, confidence_db=0.5, wet_scene_db=0.5, smooth_px=3, hand_max_m=6, valley_m=4000, min_threshold_db=0.5, landcover=(tree, herbaceous wetland, other), abstain_timing=(late recession,))`

- **Baseline:** per-pixel median of every listed same-track scene within 60 days, excluding the wet date, needing at least 3 values at a pixel.
- **Signal:** HH change, unless higher valley forest (4–8 m above the river) brightened by more than 0.5 dB. Then HH change minus HV change.
- **Threshold:** Otsu on the smoothed signal over the valley floor, floored at 0.5 dB.
- **Confidence label:** High if low valley forest (under 2 m) brightened more than higher valley forest by more than 0.5 dB. Low otherwise. The map is produced either way.

Truth is unchanged from `V3_YELLOW_PROTOCOL.md` §3.

**Regression check:** using this run's code, v3 reproduced its frozen Yellow River 0.882268 and Village Creek 0.470287 exactly, and v4 reproduced its development 0.890845 and 0.651786 exactly.

## 4. What is reported

For each river: **v4 CSI on mapped, gauge-supported, non-permanent-water pixels, under instant truth**, with a 2 km block bootstrap (2,000 draws, seed 0) and coverage of confirmed flooding. Also on the same pixels: v3 (its own rule-selected dry pass) and v1, with paired intervals for the differences. Also: ponding-tolerant scoring, the full corridor, v4 with a single dry pass, results by land cover, the confidence label and the upland warning.

## 5. Reading, fixed in advance

| v4 CSI | Reading |
|---|---|
| 0.60 or higher | Strong on this pass |
| 0.40 to 0.60 | Moderate on this pass |
| Below 0.40 | Weak on this pass |

- **v4 replaces v3 in the app only if** its mean CSI over judgeable rivers is at least v3's on the same pixels, **and** no judgeable river has a paired 95% interval entirely below zero. Otherwise v3 stays.
- **v4 beats v3 on a river** only if the paired 95% interval is entirely above zero.
- **Coverage below 0.60** of confirmed flooding means no claim for that river. **Fewer than 500 ha** of confirmed flooding means unjudgeable.
- **If no river is judgeable,** the test gives no result, and that is reported.

## 6. Two labels, tested as predictions

- **Confidence label:** High predicts CSI of 0.60 or higher. Low predicts CSI below 0.60. Its 0.5 dB cut was set after seeing development data, so this is its first fair test.
- **Upland warning** (`EDOUARD_PROTOCOL.md` §6, applied to the single dry pass): warned predicts v3 CSI below 0.60, and unwarned predicts 0.60 or higher. It scored 2 of 2 on Edouard, with no unwarned pass tested.

Each is reported as hits out of the judgeable passes. Three passes cannot establish either one.

## 7. Limits stated in advance

- **These floods may be small.** All three stayed below NWS flood stage at the wet pass, so much of the rise may have stayed in the channel. Any river could be unjudgeable.
- **Same truth as before.** It is gauge level minus lidar, so part of any score reflects geometry.
- **Regulated rivers.** Dams upstream of the Pee Dee and Toledo Bend above the Sabine affect flow.
- **Open land.** 36% of the Neuse corridor, 16% of the Pee Dee's and 5% of the Sabine's is crop, grass or shrub, which v4 never maps. Flooding there counts as a miss.
- **Baselines can contain other events.** The Sabine's includes passes during Arthur and Edouard. A median limits their effect but may not remove it.
- **Causes of the events were not established** beyond the sources in `THIRD_STORM_SCREEN.md`.
- **Scene windows are read over the network.** A read failure before scoring may be rerun and is disclosed.

## 8. After the run

Results go to `outputs/<river>/<pass>/frozen_v4_metrics.json` once, and are copied unchanged into `research/`. Each attempt is logged before imagery is read. A bug fix after scoring counts as post-hoc, is labelled that way, and does not replace the first number. Later analysis is labelled post-hoc.
