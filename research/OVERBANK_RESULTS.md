# Overbank test results

**Run once from freeze commit `684bc80`, with one logged attempt per pass.** The rules are in `OVERBANK_PROTOCOL.md`. Results are in `overbank_<river>_<pass>_frozen_metrics.json`.

## Answer

- **Overbank question: yes on the decisive pass, partly overall.** v4 scored **0.73 on Satilla Oct 15**, a held-out flood with two of three gauges above flood level. Across the judgeable primary passes it reached 0.60 on 1 of 3, which the fixed rule reads as **partly holds**.
- **Trust signal: too few passes for a verdict.** It was right on 3 of 4 judgeable passes, and the rule needed at least 5.
- **Radar was not shown better than lidar.** A lidar height cutoff with no radar scored about the same (mean 0.61, against v4's 0.62), and no paired interval excluded zero. The estimate is built from the same lidar, which favours the cutoff.
- **Five of nine passes couldn't be judged.** Four read 0 ha on the Alapaha and Withlacoochee. The check below found this comes partly from the estimate's connectivity rule and partly from rises that stayed mostly in the channel.

## Results

| River and pass | Role | Above flood level | Estimated flooding | v4 CSI (95% interval) | Recall | Precision | Lidar CSI | v4 minus lidar (95% interval) | Reading |
|---|---|---|---|---|---|---|---|---|---|
| **Satilla Oct 15** | Primary, decisive | 2 of 3 gauges | 3,623 ha | **0.73** (0.66–0.84) | 0.79 | 0.92 | 0.83 | −0.10 (−0.22 to +0.07) | Strong |
| Satilla Oct 19 | Secondary | 1 of 3 | 2,266 ha | **0.72** (0.49–0.82) | 0.82 | 0.86 | 0.69 | +0.03 (−0.07 to +0.22) | Strong |
| Ochlockonee Oct 14 | Primary | None | 1,453 ha, coverage 0.79 | **0.43** (0.29–0.55) | 0.64 | 0.57 | 0.39 | +0.05 (−0.03 to +0.11) | Moderate |
| St Marys Oct 7 | Primary | None | 945 ha | **0.58** (0.34–0.68) | 0.80 | 0.67 | 0.54 | +0.04 (−0.04 to +0.15) | Moderate |
| Alapaha Oct 15 | Primary | None | 0 ha | Not judgeable | | | | | No claim |
| Alapaha Oct 22 | Secondary | None | 0 ha | Not judgeable | | | | | No claim |
| Withlacoochee Oct 15 | Primary | None | 0 ha | Not judgeable | | | | | No claim |
| Withlacoochee Oct 10 | Secondary | None | 0 ha | Not judgeable | | | | | No claim |
| St Marys Oct 15 | Secondary | 1 of 2 | 398 ha, coverage 0 | Not judgeable | | | | | No claim |

**The headline river is the Satilla**, the first in the fixed order with enough estimated flooding. On St Marys Oct 15, all the estimated flooding lay near a gauge in late recession, where v4 doesn't map. The protocol named this risk in advance.

**Compared with v3 on the same pixels:** v4 was higher on all four judgeable passes, and the interval excluded zero on Satilla Oct 19 (+0.02, 0.01 to 0.05) and the Ochlockonee (+0.05, 0.00 to 0.09).

**Within 5 km of a gauge (descriptive):**

| Pass | v4 | Lidar | Estimated flooding |
|---|---|---|---|
| Satilla Oct 15 | 0.69 | 0.92 | 2,650 ha |
| Satilla Oct 19 | 0.71 | 0.81 | 1,783 ha |
| Ochlockonee Oct 14 | 0.47 | 0.44 | 1,062 ha |
| St Marys Oct 7 | 0.56 | 0.58 | 522 ha |

v4's score barely changes near gauges, so long gauge gaps don't appear to explain its misses here. Lidar's score rises sharply near gauges on the Satilla.

## Trust signal and labels

| Pass | Label | Rainy | Signal | CSI | Signal right? | Upland warning | Warning right? |
|---|---|---|---|---|---|---|---|
| Satilla Oct 15 | High | No | Green | 0.73 | Yes | No | Yes |
| Satilla Oct 19 | High | No | Green | 0.72 | Yes | No | Yes |
| Ochlockonee Oct 14 | High | No | Green | 0.43 | **No** | Yes | Yes |
| St Marys Oct 7 | High | Yes | Red | 0.58 | Yes | Yes | Yes |

- **Trust signal: 3 of 4.** Green was right on 2 of 3, and red on 1 of 1. Always green or always red would each get 2 of 4. Under the fixed rule, this is **too few** for a verdict.
- **High label alone: 2 of 4.** This was its first fresh test of a High label, and High did not reliably mean a good map. Every Low label fell on a pass with no judgeable flooding, so Low wasn't tested.
- **Rain made the difference on one pass, by a thin margin.** St Marys Oct 7 was High but rainy, so red, and it scored 0.58 against the 0.60 line.
- **The upland warning was right on all 4.** The two Satilla passes are the first unwarned fresh passes it has faced. Its rule was fixed in `EDOUARD_PROTOCOL.md` and scores v3 (0.72, 0.70, 0.39, 0.58). With the 5 of 5 before this test, its frozen record is 9 of 9. These passes aren't independent, and only two of the nine are unwarned, both on one river. Preferring it to the trust signal would be a post-hoc choice, so it needs its own test before replacing the signal.

## Post-hoc check: why 0 ha?

This was not part of the frozen test, and it doesn't change any result above (`scripts/diagnose_overbank_zero.py`, `overbank_zero_diagnosis.json`). It uses saved layers, lidar and reference water, and reads no new radar.

The estimate only counts flooded ground connected to GFM reference water. On these narrow rivers, reference water hardly touches the flooded area: 0 pixels on the Alapaha and 3–4 on the Withlacoochee. So the check starts connectivity from pixels within 500 m of each gauge instead.

| Pass | Frozen estimate | Estimate started from gauges | v4 CSI | Lidar CSI |
|---|---|---|---|---|
| Satilla Oct 15 (control) | 3,623 ha | 3,623 ha | 0.73 | 0.83 |
| Ochlockonee Oct 14 (control) | 1,829 ha | 1,841 ha | 0.49 | 0.42 |
| St Marys Oct 7 | 945 ha | 1,557 ha | 0.61 | 0.66 |
| **Withlacoochee Oct 15** | **0 ha** | **534 ha** | **0.52** (0.31–0.68) | **0.16** (0.04–0.33) |
| Alapaha Oct 15 | 0 ha | 34 ha | Too little flooding | Too little flooding |
| Alapaha Oct 22 | 0 ha | 4 ha | Too little flooding | Too little flooding |
| Withlacoochee Oct 10 | 0 ha | 5 ha | Too little flooding | Too little flooding |

**What this shows:**
- **Most of the zeros are real by this estimate.** On three of the four passes, even the gauge-started estimate finds almost no flooding, so those rises stayed mostly in the channel. A 2–3 m rise alone doesn't mean an overbank flood.
- **The connectivity rule can hide flooding the estimate would otherwise count.** It removed 534 ha on Withlacoochee Oct 15 and about 610 ha on St Marys Oct 7. Audit totals may be low on narrow rivers for the same reason, though this check didn't test that.
- **Withlacoochee Oct 15 is the most interesting pass.** Radar scored far above the height cutoff there, probably because the cutoff marks much of the low valley as flooded when only about 12% of labelled ground is. This is post-hoc, on one pass, so it suggests where radar adds value without showing it.
- **These numbers can't change the reading.** St Marys Oct 7 passes 0.60 here (0.61), but the frozen result remains 0.58.

## Limits

- **One river carries the good result.** Both strong passes are on the Satilla, and they share a flood.
- **The rises overlap in time.** Three primary passes share one satellite pass, and all but St Marys Oct 7 follow a storm used in development.
- **The estimate isn't an observation.** It uses the same lidar as the height cutoff, and its water-level interpolation is unreliable over long gaps (`HIDDEN_GAUGE.md`).
- **Radar's added value remains unproven on accuracy.** Its clear advantage is still that it can tell one date from another. A static cutoff can't show whether a flood is happening, or where it reached today.
- **No tuning.** v4 stays unchanged, and these passes are now spent.

## What can be claimed

**Supported:** "On a held-out flood above flood level, a method fixed in advance scored CSI 0.73 against a gauge-and-lidar estimate." v4 also uses lidar to limit where it looks, so the estimate isn't fully independent of it.

**Must accompany it:** performance varied (0.43–0.73 on judgeable passes, and 0.05–0.10 on the three rivers in the previous test), and a lidar height cutoff scored about the same on this estimate.

**Not supported:** that the trust signal is proven, that a High label guarantees a good map, or that radar beats lidar on accuracy.
