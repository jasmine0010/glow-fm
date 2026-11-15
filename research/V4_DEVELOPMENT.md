# Method v4: development record (not a validation)

**v4 raised development CSI from 0.59 to 0.63 leave-one-storm-out, and every fold chose the same setting.** The gain is concentrated where v3 failed in rain, Village Creek, and false alarms fell on most weak passes. These are development numbers on rivers already spent, so v4 has not been tested.

**Code:** `src/hidden_floods/v4.py`, `src/hidden_floods/stack.py`, `scripts/fetch_stacks.py`, `scripts/dev_v4.py`, `scripts/explore_v4_vs_trees.py`.

## What v4 changes

| Change | Failure it targets | Outcome |
|---|---|---|
| **Baseline:** per-pixel median of same-track scenes within 60 days, at least 3 scenes, wet date excluded | One unlucky dry date | Kept |
| **Adaptive signal:** if higher valley forest (4–8 m above the river) brightened by more than 0.5 dB, use HH change minus HV change | Rain brightening the whole scene | Kept |
| **Flood check:** low valley forest must brighten more than higher valley forest | Otsu can't say "no flood" | Kept as a label only. As a hard gate it blanked real weak floods, so every fold rejected it |

Land-cover gate, 6 m height gate, Otsu, 0.5 dB floor and late-recession abstention are unchanged from v3. The grid had 24 settings. The 0.5 dB switch was set before this run and not tuned.

**Corridor-only reads:** each scene takes about 30 seconds and caches about 6 MB, instead of a 6 GB download. A read of a scene already on disk matched exactly (maximum difference 0.0 dB). All 78 baseline scenes were fetched with no failures.

## Leave-one-storm-out results

Settings were chosen on two storms and scored on the third. All three folds chose median baseline, adaptive signal, no gate.

| Pass | Confirmed | v3 CSI | **v4 CSI** | v3 on dry ground | v4 on dry ground | Low − high | Label |
|---|---|---|---|---|---|---|---|
| Choctawhatchee Oct 17 | 6,765 ha | 0.82 | **0.85** | 490 ha | 476 ha | +2.44 dB | High |
| Choctawhatchee Oct 21 | 2,613 ha | 0.90 | **0.91** | 118 ha | 146 ha | +1.42 dB | High |
| Yellow Oct 16 | 1,868 ha | 0.88 | **0.89** | 40 ha | 35 ha | +1.16 dB | High |
| Yellow Oct 17 | 1,680 ha | 0.83 | **0.85** | 117 ha | 106 ha | +0.84 dB | High |
| Pearl Jul 3 | 19,128 ha | 0.68 | **0.70** | 311 ha | 236 ha | +0.86 dB | High |
| Pine Island Bayou Sep 7 | 1,965 ha | 0.71 | **0.70** | 545 ha | 541 ha | +1.64 dB | High |
| Village Creek Sep 3 | 1,844 ha | 0.47 | **0.65** | 1,084 ha | 704 ha | +1.26 dB | High |
| Village Creek Sep 7 | 624 ha | 0.30 | **0.49** | 958 ha | 483 ha | +0.65 dB | High |
| Yellow Oct 9 | 1,003 ha | 0.58 | **0.61** | 192 ha | 137 ha | +0.25 dB | Low |
| Pearl Jun 25 | 17,123 ha | 0.54 | **0.46** | 1,193 ha | 1,151 ha | +0.10 dB | Low |
| Tangipahoa Jun 21 | 2,397 ha | 0.29 | **0.31** | 3,811 ha | 1,713 ha | −0.07 dB | Low |
| Yellow Oct 5 | 1,030 ha | 0.09 | **0.08** | 1,678 ha | 511 ha | −0.12 dB | Low |
| Pine Island Bayou Sep 3 (too small to judge) | 163 ha | 0.02 | 0.02 | 2,895 ha | 3,357 ha | +0.04 dB | Low |
| Yellow Oct 4 (no flood) | 8 ha | 0.00 | 0.01 | 221 ha | 67 ha | −0.07 dB | Low |

"Confirmed" counts all ground near a gauge, including where the method abstains, which is why two Arthur and Isaias figures exceed the scored area. **Mean over the 12 judgeable passes: v3 0.591, v4 0.626.** High-confidence passes average 0.76. Low-confidence judgeable passes average 0.37. The 0.5 dB label cut was chosen after seeing these values, so that split is optimistic.

Where it got worse: Pearl Jun 25 fell from 0.54 to 0.46, and false alarms rose on Pine Island Bayou Sep 3. Arthur's early passes have few earlier scenes, so their baselines lean on later dates.

## Learned models, trained on two storms and scored on the third

scikit-learn loads now. Height above the river is not a feature. "Scene-scaled" subtracts each scene's valley-floor median and divides by its spread, which is a fair way to give trees some self-calibration.

| Method | Mean CSI, 12 judgeable passes |
|---|---|
| **v4 rule** | **0.626** |
| v3 rule | 0.591 |
| Random forest, scene-scaled | 0.531 |
| Boosted trees, scene-scaled | 0.517 |
| Random forest, raw | 0.414 |
| Boosted trees, raw | 0.414 |

Scene-scaling helped the trees a lot, which supports self-calibration as the key idea. Trees did beat the rules on some hard passes: Yellow Oct 5 (0.29 against 0.08) and Tangipahoa (up to 0.34 against 0.31). They lost on the clean passes, by up to 0.36 (Yellow Oct 16). With three storms, this is not enough evidence to rule out learned models in general, but it gives no reason to prefer them now.

## Honest status

**Update:** the frozen test is in `V4_RESULTS.md`. All three rivers stayed below flood stage and scored 0.05–0.10, so it could not confirm or refute the gain below.

- These are development numbers. The ideas came from studying these same passes, so even leave-one-storm-out estimates are optimistic.
- A gain of 0.035 is modest, and much of it comes from one river.
- The real test is one frozen run on rivers v4 has never seen, under a protocol written first.
