# Method v4: frozen results on three new rivers

**Weak on all three rivers: CSI 0.10, 0.06 and 0.05.** v3 was just as weak. The confidence label marked all three passes low confidence before any truth was read, and it was right each time. Estimated flooding was only 4–5% of labelled ground, so this may have been a poor test of flood mapping, but flood stage alone doesn't explain it (see the correction below). It does not show that v4's development gain carries over to new floods.

**Protocol:** `V4_PROTOCOL.md`. **Freeze commit:** `a4dd49d5`. **Attempts logged:** 1 per river. **Files changed since freeze:** none, apart from dates removed later. **Output, unedited apart from removed run times:** `v4_<river>_<pass>_frozen_metrics.json`.

## Results

All three rivers are judgeable, with 100% coverage, and the Pee Dee is the headline by the order fixed in advance.

| River | Wet pass | Confirmed flooding | **v4 CSI (95% range)** | Recall | Precision | v3 CSI (95% range) | v4 minus v3 (95% range) | Label | Upland warning |
|---|---|---|---|---|---|---|---|---|---|
| **Pee Dee** | Jul 27 | 743 ha | **0.10 (0.02–0.20)** | 0.26 | 0.14 | 0.08 (0.03–0.13) | +0.03 (−0.02 to +0.07) | Low (−0.25 dB) | Warned (+0.65 dB) |
| Neuse | Jul 26 | 890 ha | **0.06 (0.03–0.10)** | 0.31 | 0.07 | 0.05 (0.02–0.08) | +0.01 (+0.00 to +0.03) | Low (+0.19 dB) | Warned (+1.01 dB) |
| Lower Sabine | Jul 17 | 791 ha | **0.05 (0.00–0.13)** | 0.39 | 0.06 | 0.07 (0.00–0.19) | −0.02 (−0.06 to +0.00) | Low (+0.04 dB) | Warned (+1.00 dB) |

**Mean over the three rivers: v4 0.074, v3 0.067.**

## Reading, using the rules fixed in advance

- **Every river is weak** (below 0.40).
- **The rule for replacing v3 is met, narrowly and without much meaning.** v4's mean is at least v3's, and no paired interval is entirely below zero. The Sabine's upper bound is only +0.0015. A difference of 0.007 at this level has no practical importance.
- **v4 beats v3 only on the Neuse,** by +0.013, which is too small to matter.
- **Confidence label: 3 of 3.** All three were labelled low and scored below 0.60. No fresh pass has been labelled high, so that half is still untested.
- **Upland warning: 3 of 3.** All three were warned, and v3 scored below 0.60 on each. Including Edouard it is 5 of 5, and it has never been tested on an unwarned fresh pass. Three passes cannot establish either label.

## Post-hoc checks (`scripts/posthoc_v4.py`; none of these replaces the numbers above)

**This looks like a test with little floodplain flooding in it.** Confirmed flooding is only 4–5% of labelled ground, and its median height is below the channel profile (−0.3 to −1.1 m). That points to low ground along the channel, not water spreading across the floodplain. This is an inference, since no independent map of the water exists.

**Radar shows no clear flood response here, unlike the earlier floods:**

| River | Forest 1–3 m above river level, HH change | Forest 0.5–1 m below, HH change | Forest 1–2 m below, HH change | AUC, ΔHH | AUC, ΔHH−ΔHV |
|---|---|---|---|---|---|
| Pee Dee | −0.23 dB | −0.11 dB | +0.96 dB (175 ha) | 0.64 | 0.72 |
| Neuse | +1.60 dB | +1.53 dB | +2.14 dB | 0.46 | 0.52 |
| Lower Sabine | +0.40 dB | +0.45 dB | +0.31 dB | 0.54 | 0.66 |
| *For contrast, Yellow Oct 16* | *+0.34 dB (1–3 m above)* | | *+2.49 dB (0.5–2 m below)* | *0.97* | *0.96* |

**A lidar-only map scores 0.74 on the Pee Dee, with a height limit picked using the truth.** The Neuse and Sabine reach 0.38 and 0.23. On the Pee Dee, labelled flooding is almost entirely a thin strip of very low ground.

**False alarms are the main loss.** v4 mapped 1,158 ha on dry Pee Dee ground, down from v3's 3,340 ha. On the Neuse (3,378 against 3,221 ha) and Sabine (4,956 against 5,140 ha) it did about the same as v3. Both methods map something on every pass, because Otsu always finds a split. In practice the low-confidence label is the only safeguard against this.

## Correction: flood stage does not explain these failures

This file first attributed the failures to the rivers staying below flood stage. A later check of NWS flood stage at every gauge (`scripts/flood_stage_check.py`, `research/flood_stage_by_pass.json`) doesn't support that. Gauges with a listed flood stage were also below it on the Yellow Oct 16 (0.88 for v3, Milligan only) and Choctawhatchee Oct 17 (0.82 in development) passes. The share of labelled ground estimated as flooded separates these results better, at 4–5% here against 13–72% on judgeable passes elsewhere, but that is post-hoc and not a clean split either. Why these three rivers failed remains an open question: little floodplain flooding, a method failure, and errors in the estimate on long reaches are all still possible.

## What this means across all frozen tests

| Test | Storm | Method | CSI | Flood stage at the wet pass |
|---|---|---|---|---|
| Yellow | Isaias, also a development storm | v3 | 0.88 | Below (1 of 3 gauges has a value) |
| Pine Island Bayou | Edouard | v3 | 0.71 | Above |
| Village Creek | Edouard | v3 | 0.47 | Above |
| Tangipahoa | Arthur | v2 | 0.29 | Below |
| Pearl | Arthur | v1 | 0.23 | Mixed |
| Pee Dee | July front | v4 | 0.10 | Below |
| Neuse | July front | v4 | 0.06 | Below |
| Lower Sabine | Mid-July rain | v4 | 0.05 | Below |

- **Supported:** on these three rivers the methods had nothing useful to map, and a truth-free label warned about that. Whether the rises stayed in the channel is an inference.
- **Not supported:** that v4 is better than v3 on new floods. Its gain so far exists only in development, and these rivers could not test it fairly.
- **Still open:** whether v4 beats v3 on a real overbank flood it has never seen. The screen's best remaining options (the Wabash and Satilla) need a reader change or overlap Isaias, so this needs a decision.

**Wording for the app and pitch:** "On three further rivers, the method scored CSI 0.05–0.10 and mapped mostly false alarms. A confidence label fixed before the test marked all three as low confidence, so a low label is a warning not to use the map. No fresh test has yet confirmed what a high label means."
