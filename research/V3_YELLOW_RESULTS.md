# Method v3: frozen Yellow River result

**v3 scored CSI 0.88 (95% range 0.80–0.92) on its one frozen test, the Yellow River on Oct 16, 2026.** That is strong by the bar set in advance, and it beats v1 and v2 on the same pixels. It does not show v3 works across storms: this is the same storm as the Choctawhatchee, and 95% of the confirmed flooding sits in one lower reach.

**Protocol:** `V3_YELLOW_PROTOCOL.md`. **Freeze commit:** `bbd91052`. **Attempts logged:** 1. **Files changed since freeze:** none, apart from dates removed later. **Output, unedited apart from removed run times:** `v3_yellow_055D_frozen_metrics.json`.

## The primary pass changed before the run

The protocol named track 004A (Oct 12) as primary. Its pre-run metadata check failed: the grid stops at x = 536,395 m and the Oak Grove gauge is at x = 542,096 m. So, as the protocol requires, **055D Oct 16 against Sep 22 became primary**, and no secondary pass remains. This was decided before any Yellow River backscatter was read.

004A was then run anyway, labelled post-hoc, and has no valid radar on any labelled pixel. Its printed CSI of 0 is not a score, so it says nothing about the method.

## Result

Scored on 1,869 ha of confirmed flooding and 4,418 ha of confirmed dry ground, in the gauge-supported region with permanent water excluded. Threshold 1.50 dB. Coverage 100%: late-recession abstention removed nothing on this pass.

| Method, same pixels | CSI (95% range) | Recall | Precision |
|---|---|---|---|
| **v3, primary** | **0.88 (0.80–0.92)** | **0.90** | **0.98** |
| v1, fixed 2 dB | 0.68 (0.56–0.73) | 0.72 | 0.92 |
| v2, upland percentile | 0.54 (0.26–0.71) | 0.96 | 0.55 |

| Secondary reading of v3 | CSI (95% range) |
|---|---|
| Ponding-tolerant scoring | 0.88 (0.80–0.92), no ambiguous pixels on this pass |
| No abstention | 0.88 (0.80–0.92) |
| Full corridor, including beyond gauge support | 0.83 (0.79–0.87) |
| Tree cover only | 0.88 (0.80–0.93) |

| Paired difference in CSI | Value (95% range) |
|---|---|
| v3 minus v1 | +0.20 (+0.17 to +0.25) |
| v3 minus v2 | +0.35 (+0.19 to +0.55) |

## Reading, using the rules fixed in advance

- **CSI 0.88 is at or above 0.60:** strong on this pass.
- **Both paired intervals are above zero:** v3 beats v1 and v2 here.
- **Coverage 100%, above the 60% minimum, and 1,869 ha, above the 500 ha minimum:** the test is judgeable and the claim can be made.

## Post-hoc checks (`scripts/posthoc_v3_yellow.py`; none of these replaces the number above)

**The radar, not the lidar gate, does the work.** The 6 m gate leaves CSI at 0.30 by itself. Removing it from v3 and recomputing the threshold still gives 0.87. Truth is built from the same lidar, so this was the leak worth checking.

**A lidar-only map gets close once you know where the river flooded.** With its height limit picked by looking at the truth, an unfairly generous benchmark, a no-radar map reaches 0.46 over the whole test. Inside the two flooded quarters of the labelled ground it reaches 0.84 and 0.85, against v3's 0.86 and 0.94. So radar's clearest advantage here is finding where flooding occurred without being told, and its within-reach advantage is smaller. On the Choctawhatchee development pass this same benchmark scores 0.85 against v3's 0.82.

**The test is mostly one reach.** Only 8 of 22 labelled 2 km blocks contain confirmed flooding, and 95% of it (1,779 of 1,869 ha) lies from km 42 to the downstream end near the Milton gauge. That gauge was near crest, the condition the development record already found easiest. The upper reach supplies mostly a false-alarm test: 14 ha mapped on 1,901 ha of dry ground from km 0 to 20.

## What this does and does not support

- **Supported:** with no change after freezing, v3 mapped confirmed flooding well on a new river, with new scenes and viewing geometry. Its farmland gate was barely tested, because the region holds only 126 ha of dry farmland, and this was nearly all forest (1,816 of 1,869 ha of the flooding).
- **Not supported:** that v3 works this well in general. Isaias also supplied the Choctawhatchee, where v3 scored 0.83–0.90 in development. In the other storm, v3 scored 0.61 (Pearl) and 0.30 (Tangipahoa) in leave-one-flood-out development. A strong signal in this storm is the simplest explanation for the high score, though this test cannot establish that.
- **Next real test:** one frozen pass from a storm v3 has never seen, including a mainly falling-limb pass.

**Wording for the app and pitch:** "In one frozen test on a new river, the Yellow, in the same storm as our development flood, v3 scored CSI 0.88 (95% range 0.80–0.92). Most of that flooding was in one reach near a gauge at crest. In development on another storm, it scored 0.61 and 0.30."
