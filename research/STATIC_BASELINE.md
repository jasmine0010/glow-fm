# What radar adds beyond a lidar map

**Question:** if you had only a lidar elevation map and no radar, how far would you get against the gauge-and-lidar estimate?

## Rule, written before this baseline was computed

- **Static map:** valley-floor pixels in tree cover, herbaceous wetland or "other" land cover, **less than 2 m above the river profile**. It is the same map on every date for a river. It uses no radar, no gauge and no truth.
- **Why 2 m:** it is the "low valley ground" limit already in v4 (`LOW_MAX_M` in `src/hidden_floods/v4.py`), set before this comparison.
- **Sensitivity only:** 1 m and 3 m are reported beside it, and they don't replace it.
- **Scoring:** the same pixels as the radar map on each pass, under instant truth.
- **Radar map:** v4, from the frozen rule. Scores on passes from rivers that helped build v4 are development numbers, and the Pee Dee, Neuse and Sabine are its frozen scores.

**This rule isn't fully blind.** Limits picked using the truth (0.5–2 m) were already known from earlier post-hoc checks, and 2 m sits inside that range. No fresh test is claimed here. The purpose is an honest comparison, not a new result.

## Results (`scripts/static_baseline.py`, `research/static_baseline.json`)

**Lidar alone scored higher on 10 of 15 judgeable passes, though NISAR v4 had the higher mean, 0.52 against 0.47.** The two win in different places, and radar's real addition is telling one date from another.

| Pass | NISAR v4 | Lidar only, 2 m | Lidar only, 1 m | Lidar only, 3 m |
|---|---|---|---|---|
| Yellow Oct 16 | **0.89** | 0.39 | 0.45 | 0.33 |
| Yellow Oct 17 | **0.85** | 0.32 | 0.37 | 0.28 |
| Yellow Oct 9 | **0.61** | 0.21 | 0.25 | 0.18 |
| Village Creek Sep 3 | **0.65** | 0.53 | 0.56 | 0.46 |
| Village Creek Sep 7 | **0.49** | 0.20 | 0.24 | 0.17 |
| Choctawhatchee Oct 17 | 0.85 | 0.85 | 0.64 | 0.77 |
| Choctawhatchee Oct 21 | 0.91 | **1.00** | 0.95 | 0.88 |
| Pine Island Bayou Sep 7 | 0.70 | **0.75** | 0.94 | 0.37 |
| Pearl Jul 3 | 0.70 | **0.93** | 0.93 | 0.87 |
| Pearl Jun 25 | 0.46 | **0.90** | 0.92 | 0.84 |
| Tangipahoa Jun 21 | 0.31 | **0.38** | 0.42 | 0.27 |
| Yellow Oct 5 | 0.08 | **0.21** | 0.25 | 0.19 |
| Pee Dee Jul 27 (frozen v4) | 0.10 | **0.15** | 0.50 | 0.08 |
| Neuse Jul 26 (frozen v4) | 0.06 | **0.15** | 0.32 | 0.10 |
| Lower Sabine Jul 17 (frozen v4) | 0.05 | **0.08** | 0.14 | 0.06 |

The Choctawhatchee Oct 17 pair is shown as a tie at two decimals, and the summary count uses unrounded values.

- **A high score against this estimate doesn't prove radar skill.** On the Pearl, a height limit beats radar by over 0.2 with no satellite at all. The estimate is built from the same lidar, so this comparison favours lidar, and it doesn't show that lidar is the better flood map.
- **Radar's clear wins are the Yellow and Village Creek.** Those are the passes where only part of the low ground was estimated as flooded.
- **Lidar can't tell dates apart.** On the Yellow it gives the same area on Oct 4, when almost nothing is estimated as flooded, as at the peak. That is the argument for radar: "lidar knows where water could go, and radar says whether it is there on this pass."
- **Limits:** 12 of the 15 are v4 development scores, and the storms and rivers repeat.
