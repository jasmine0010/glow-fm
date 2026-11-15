# Where v3 fails, and what might fix it

**Exploration on rivers already spent, so nothing here is a validated result.** Scripts: `scripts/explore_model_ideas.py`, `scripts/explore_model_logistic.py`. Fourteen passes, three storms. Scored the way v3 is scored, with the same land-cover and height gate. Height above the river is never a model feature, because the truth uses the same lidar.

## Evidence, pass by pass

"Best threshold" is picked by looking at the truth, so it is a ceiling and not a method. "Low − high" is the median HH change on valley forest under 2 m above the river, minus forest 4–8 m above it. "Upland" is the median HH change on forest over 12 m above the river.

| Pass | Confirmed | v3 (ΔHH, Otsu) | Best threshold, ΔHH | ΔHH−ΔHV, Otsu | Best threshold, ΔHH−ΔHV | Best threshold, wet HH | AUC ΔHH | AUC ΔHH−ΔHV | Low − high | Upland |
|---|---|---|---|---|---|---|---|---|---|---|
| Choctawhatchee Oct 17 | 6,765 ha | 0.82 | 0.83 | 0.81 | 0.82 | 0.75 | 0.96 | 0.96 | +2.35 | −0.04 |
| Choctawhatchee Oct 21 | 2,439 ha | 0.90 | 0.91 | 0.84 | 0.84 | 0.76 | 0.99 | 0.97 | +1.29 | −0.01 |
| Yellow Oct 5 | 1,030 ha | 0.09 | 0.13 | 0.17 | 0.22 | 0.29 | 0.43 | 0.65 | +0.03 | +0.93 |
| Yellow Oct 9 | 1,003 ha | 0.58 | 0.58 | 0.61 | 0.62 | 0.49 | 0.90 | 0.90 | +0.30 | +0.55 |
| Yellow Oct 16 | 1,868 ha | 0.88 | 0.88 | 0.85 | 0.85 | 0.78 | 0.97 | 0.96 | +1.16 | −0.14 |
| Yellow Oct 17 | 1,680 ha | 0.83 | 0.84 | 0.77 | 0.79 | 0.76 | 0.96 | 0.95 | +0.81 | −0.32 |
| Pearl Jul 3 | 19,128 ha | 0.68 | 0.79 | 0.68 | 0.80 | 0.80 | 0.90 | 0.88 | +0.90 | +0.23 |
| Pearl Jun 25 | 11,027 ha | 0.54 | 0.60 | 0.45 | 0.67 | 0.71 | 0.70 | 0.75 | +0.17 | +0.31 |
| Tangipahoa Jun 21 | 2,397 ha | 0.29 | 0.31 | 0.26 | 0.28 | 0.35 | 0.79 | 0.75 | −0.18 | +0.65 |
| Village Creek Sep 3 | 1,844 ha | **0.47** | 0.52 | **0.62** | 0.62 | 0.68 | **0.72** | **0.88** | +1.23 | +1.89 |
| Village Creek Sep 7 | 624 ha | **0.30** | 0.30 | **0.39** | 0.43 | 0.59 | **0.81** | **0.90** | +0.61 | +1.73 |
| Pine Island Bayou Sep 7 | 1,965 ha | 0.71 | 0.73 | 0.69 | 0.72 | 0.73 | 0.97 | 0.97 | +1.80 | n/a |
| Pine Island Bayou Sep 3 (too small to judge) | 163 ha | 0.02 | 0.02 | 0.03 | 0.03 | 0.13 | 0.53 | 0.61 | +0.10 | n/a |
| Yellow Oct 4 (no flood) | 8 ha | 0.00 | — | 0.00 | — | — | — | — | +0.01 | +0.01 |

Upland values differ slightly from `V3_YELLOW_SERIES.md` because this script applies the 3×3 smoothing first.

## Models trained on two storms and scored on the third

Mean CSI over the 12 judgeable passes:

| Method | Mean CSI |
|---|---|
| **Otsu per scene on ΔHH−ΔHV** | **0.60** |
| **Otsu per scene on ΔHH (v3)** | **0.59** |
| Logistic, wet HH and HV only, no dry pass | 0.53 |
| Logistic, ΔHH−ΔHV | 0.49 |
| Logistic, ΔHH | 0.46 |
| Logistic, changes plus levels | 0.39 |
| Logistic, ΔHH and ΔHV | 0.36 |

scikit-learn's compiled modules were blocked by a Windows Application Control policy on this machine. The block was left in place, and these are plain numpy logistic models. Boosted trees were not tested.

## What this shows

1. **Thresholds are not the main problem.** On clean passes Otsu sits within 0.01 of the truth-picked best. Further threshold work has little left to find, though Pearl has more room (0.68 against 0.79).
2. **Self-calibration beats training on these data.** A fixed boundary learned on two storms does worse than Otsu per scene, and the learned weights swing by fold. More complex models on three storms would likely do worse.
3. **The polarization physics shows up on its own.** The weight on ΔHV is negative in all three folds, and it was not told to be. Rain raises HV as well as HH, and double bounce raises mainly HH.
4. **Rain has a measurable remedy, but it costs on clean passes.** On Village Creek, ΔHH−ΔHV raises AUC from 0.72 to 0.88 and CSI from 0.47 to 0.62. On clean passes CSI drops by 0.01 to 0.06, so the mean barely moves.
5. **A wet-date image alone carries a lot.** No dry reference is needed, and it gives the best ceilings at Village Creek (0.68, 0.59) and Pearl.
6. **Otsu cannot say "no flood".** Bimodality measures did not help: Ashman's D was 2.2 on the no-flood pass and 2.5–4.2 elsewhere.
7. **Low − high may say it.** Above +0.5 dB: eight passes, CSI 0.30–0.90. Below: six passes, CSI 0.00–0.58. It works on flat rivers, where upland cannot be computed, and uses no gauge. The 0.5 dB cut was chosen after seeing these values.
8. **Tangipahoa looks out of reach for one image pair.** All ceilings are 0.28–0.35, so its problem may be the 60-day reference, land cover or the truth.

## Coherence (Choctawhatchee only, 3 interferograms on disk)

| Pair | Median coherence, flooded | Median coherence, dry | Separation (AUC, flooded lower) |
|---|---|---|---|
| Oct 5 → 17, spans the flood | 0.22 | 0.25 | 0.76 |
| Oct 9 → 21, spans the flood | 0.24 | 0.30 | 0.77 |
| Sep 15 → 27, before the flood (control) | 0.67 | 0.67 | 0.49 |

The control shows no separation, so the signal arrives with the flood. Coherence also collapsed across the corridor. Its separation is weaker than ΔHH here, but it is a separate physical signal.

## Independent truth: catalog check

The biggest scientific gap is that truth is gauge level minus lidar, and lidar alone scores up to 0.95 against it.

- **SWOT** raster and pixel-cloud products exist over the Yellow (Oct 8–19) and Village Creek (Sep 1–10), so water levels independent of gauges may be available. Coverage of the river itself is unconfirmed.
- **ICESat-2** ATL08 and ATL13 are only published through Jul 20 so far, and no granule was found over the Pearl in Arthur's window.
- **USGS high-water marks:** the service returned a web page rather than data, so this is unresolved.
- **Sentinel-1 RTC** exists over the Yellow (Oct 10, 22) and Village Creek (Sep 1). **GPM IMERG** rainfall exists throughout.
