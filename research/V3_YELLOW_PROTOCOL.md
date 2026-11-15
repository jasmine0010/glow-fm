# Method v3 protocol: one frozen test on the Yellow River

**Written** before any NISAR pixel over the Yellow River corridor was read.
**Receipt:** `research/freeze_receipt_v3.json`, with SHA-256 hashes of this file, the site file, the run script and all scientific modules. The run refuses to start if any of them has changed. The freeze commit is the dated record.

## 1. What has and has not been seen

**Already seen for this river, and disclosed here:**
- gauge records, the lidar DEM and GFM reference water;
- GFM and OPERA DSWx-S1 flood layers on Oct 10 and Oct 22, opened for the blind-spot audit;
- gauge-and-lidar truth at those two Sentinel-1 times, reported as hectares in `BLIND_SPOT_AUDIT.md` (1,545 ha and 832 ha).

**Not seen:** any NISAR backscatter, browse image or interferogram over this corridor, and truth at either NISAR test time. No NISAR map has been compared with truth here. v3 development used only the Choctawhatchee, Pearl and Tangipahoa (`V3_DEVELOPMENT.md`).

## 2. Pair selection (catalog metadata and gauge stage only)

The rule is unchanged from `SECOND_EVENT_PROTOCOL.md` §2(b): on each track, **dry** is the acquisition with the lowest mean gauge stage within ±60 days, **wet** is the one highest above its dry value, and at least one gauge must be more than 1.0 m above its dry stage.

Earlier notes planned to use the 076A and 127D scenes shared with the Choctawhatchee. The catalog also lists track 004A, whose Oct 12 pass falls at the crest, so the rule selects it. The audited October gauge record was extended back to Aug 10 for this check, and the overlap matched exactly.

| Rank | Track | Wet (UTC) | Dry (UTC) | Mean rise | Largest gauge rise | Timing at Oak Grove / Milligan / Milton |
|---|---|---|---|---|---|---|
| **1, primary** | **004A** | **Oct 12 11:10** | **Aug 13 11:10** | **5.19 ft** | **2.15 m** | rising / near crest / rising |
| **2, secondary** | **055D** | **Oct 16 00:36** | **Sep 22 00:36** | **3.79 ft** | **1.50 m** | receding / receding / near crest |
| 3, not used | 076A | Oct 17 11:02 | Sep 23 11:02 | 2.08 ft | 0.81 m (fails 1 m) | receding at all three |
| not used | 127D | Oct 21 00:28 | Sep 27 00:28 | 1.03 ft | 0.34 m (fails 1 m) | late recession at all three |

Crests: Milligan Oct 11 15:30, Oak Grove Oct 13 13:00, Milton Oct 14 03:30 UTC. The dry scene for 004A is exactly 60 days before the wet scene, the edge of the window, and it stands as the rule selected it.

**Pre-run metadata check:** each scene must use EPSG:32616 and contain all three gauges. If 004A fails this, 055D becomes primary and the failure is recorded.

## 3. Frozen method v3

`V3OtsuRule(smooth_px=3, hand_max_m=6, valley_m=4000, min_threshold_db=0.5, landcover=(tree, herbaceous wetland, other), abstain_timing=(late recession,))`

- **Change:** ΔHH (dB) on the 50 m grid, smoothed by a NaN-aware 3×3 mean.
- **Valley floor:** valid pixels in tree cover, herbaceous wetland or "other" (ESA WorldCover 2021), under 6 m above the river profile, within 4 km of the valley line. Fewer than 500 pixels stops the run.
- **Threshold:** Otsu's split of the change over the valley floor, floored at 0.5 dB. It uses no truth.
- **Flooded:** eligible pixels with change above the threshold, except where the nearest gauge is in late recession (more than 6 days after its crest), where the method abstains.

**Truth:** unchanged from v2. Stage at the wet time, ±0.5 m margin, −5 m dry limit, 4 km corridor, connectivity to GFM reference water, within 10 km of a gauge along the valley. Permanent water is excluded.

## 4. What is reported

**Primary: v3 CSI on the 004A Oct 12 pass, on mapped, gauge-supported, non-permanent-water pixels, under instant truth.** Interval: 2 km block bootstrap, 2,000 draws, seed 0. Coverage of confirmed flooding is always reported beside it.

Instant truth is primary because earlier frozen tests used it, although some v3 development tables used ponding-tolerant scoring.

Secondary, and unable to rescue the primary:
- the same pass with ponding-tolerant scoring, without abstention, and on the full corridor;
- v2 and v1 on the same pixels, with paired intervals for the CSI differences;
- results by land cover;
- the whole set again on 055D Oct 16.

## 5. How the result will be read (fixed in advance)

| Primary CSI | Reading |
|---|---|
| 0.60 or higher | Strong on this pass |
| 0.40 to 0.60 | Moderate on this pass |
| Below 0.40 | Weak; v3 stays a development result and the app says so |

- **Beats earlier methods** only if the paired 95% interval for CSI difference is above zero against both v1 and v2.
- **Coverage below 0.60** of confirmed flooding means the claim is not made, whatever the CSI (the threshold from `V3_DEVELOPMENT.md`).
- **Fewer than 500 ha** of confirmed flooding in the primary region means the test is unjudgeable, and it is reported that way.
- **Reference, not a target:** the development leave-one-flood-out mean is 0.59. Earlier frozen held-out results are 0.23 (v1, Pearl) and 0.29 (v2, Tangipahoa), on other rivers.

## 6. Limits stated in advance

- **One river, one storm.** Hurricane Isaias also produced the Choctawhatchee development flood, so season and storm are not independent. Scenes, geometry, river, forest and gauges are new on 004A and 055D.
- **A crest-time primary pass is favourable by design.** The development record already showed near-crest passes doing best, and the rule picked this pass because the flood was highest. A good score says little about falling-limb passes, which is why 055D is reported too.
- **Only 3 gauges, with sparse support.** Labels exist only within 10 km along the valley of a gauge.
- **A 60-day dry reference** spans late summer to mid-October, so seasonal change may add noise.
- **Truth is not flood mapping from the air.** It is a hydraulic estimate from gauges and lidar, as in every earlier test.

## 7. After the run

Results go to `outputs/yellow/<pair>/frozen_v3_metrics.json` once, and are copied unchanged into `research/V3_YELLOW_RESULTS.md`. Each attempt is logged before imagery is read. A crash before scoring may be rerun and is disclosed. A bug fix after scoring counts as post-hoc, is labelled that way, and does not replace the first number. Later analysis is labelled post-hoc.
