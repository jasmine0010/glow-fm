# Method v3: frozen results on Tropical Storm Edouard

**Mixed, by the rule set in advance.** On a storm it had never seen, v3 scored CSI 0.47 (95% range 0.35–0.60) on Village Creek, the primary pass, and 0.71 (0.60–0.79) on Pine Island Bayou. Holding up needed the primary at 0.60 or higher, and it fell short. The 0.88 on the Yellow River does not carry over to this storm.

**Protocol:** `EDOUARD_PROTOCOL.md`. **Freeze commit:** `c6a17474`. **Attempts logged:** 1 per pass. **Files changed since freeze:** none, apart from dates removed later. **Output, unedited apart from removed run times:** `edouard_<river>_<pass>_frozen_metrics.json`.

## Results

| Pass | Role | Confirmed flooding | v3 CSI (95% range) | Recall | Precision | v1, same pixels | v2, same pixels | Upland HH change |
|---|---|---|---|---|---|---|---|---|
| **Village Creek, Sep 3** | **Primary** | 1,844 ha | **0.47 (0.35–0.60)** | 0.75 | 0.56 | 0.46 | 0.45 | **+1.93 dB, warned** |
| **Pine Island Bayou, Sep 7** | **Second river** | 1,965 ha | **0.71 (0.60–0.79)** | 0.91 | 0.77 | 0.49 | cannot run | not computable |
| Village Creek, Sep 7 | Secondary | 624 ha | 0.30 (0.16–0.45) | 0.77 | 0.33 | 0.23 | 0.30 | **+1.73 dB, warned** |
| Pine Island Bayou, Sep 3 | Secondary | 163 ha | unjudgeable (under 500 ha) | — | — | — | cannot run | not computable |

Coverage was 100% on every pass, so abstention played no part. On Pine Island Bayou's Sep 3 pass, v3 mapped 2,895 ha on dry ground and 71 ha on confirmed flooding. It is unjudgeable as a score, but it is a clear false-alarm result.

## Reading, using the rules fixed in advance

- **Third storm: mixed.** Both first-listed passes reached 0.40, so v3 did not fail to transfer. The primary is below 0.60, so it did not hold up.
- **Village Creek, primary: moderate, and no better than earlier methods.** Paired differences include zero: +0.01 (−0.05 to +0.07) against v1 and +0.02 (−0.01 to +0.05) against v2.
- **Pine Island Bayou: strong.** It beats v1 by +0.22 (+0.18 to +0.28). v2 could not run there, with only 6 upland pixels.
- **Village Creek, Sep 7: weak.** It beats v1 by +0.07 (+0.02 to +0.14), and its interval against v2 includes zero.
- **Upland warning: 2 of 2 right, so it survives for further testing.** Both warned passes scored below 0.60. No unwarned pass could be tested, because Pine Island Bayou has too few upland pixels. So this run shows the warning firing on bad passes, not staying quiet on good ones.

## Post-hoc checks (`scripts/posthoc_edouard.py`; none of these replaces the numbers above)

**Rain looks like the likely failure at Village Creek (`RAINFALL.md`: about 196 mm in 72 hours by IMERG satellite rainfall, 228 mm by the Kountze rain gauge).** Dry forest brightened by a median +2.4 dB on Sep 3, not far from flooded forest at +3.5 dB. Upland forest moved by about +1.9 dB. Radar had little contrast left to work with.

**Subtracting the upland shift did not rescue it.** Removing that shift and re-running the same threshold rule gave 0.48 and 0.30, against 0.47 and 0.30. The trouble is not only a uniform offset. So a warning is justified by these results, and a correction is not.

**A no-radar map does well here, which limits what these scores can mean.** Truth comes from lidar and gauges, so a lidar height cutoff picked by looking at the truth is an unfairly generous benchmark. It still shows how much of the score is geometry:

| Pass | v3 CSI | Lidar-only CSI, best height limit | Height gate alone |
|---|---|---|---|
| Village Creek, Sep 3 | 0.47 | 0.55 (1.0 m) | 0.38 |
| Pine Island Bayou, Sep 7 | 0.71 | **0.95** (1.0 m) | 0.17 |
| Village Creek, Sep 7 | 0.30 | 0.24 (0.5 m) | 0.14 |

On Pine Island Bayou, confirmed flooding is almost entirely ground below 1 m above the river profile. So a high score there shows radar broadly reproducing a simple geometric pattern, not doing something lidar could not. The benchmark needs the gauges and the truth to set its limit, while v3 needs neither to set its threshold, though it does use gauge timing to decide where to abstain. That is radar's advantage, and it does not make these scores independent proof of accuracy.

## What this means across all frozen tests

| Frozen test | Storm | CSI | Note |
|---|---|---|---|
| Yellow, v3 | Isaias, also a development storm | 0.88 | Mostly one reach, scene quiet (upland −0.21 dB) |
| Pine Island Bayou, v3 | Edouard, new | 0.71 | Few days after rain, upland not computable |
| Village Creek, v3 | Edouard, new | 0.47 | During rain, scene-wide brightening |
| Tangipahoa, v2 | Arthur | 0.29 | Older method |
| Pearl, v1 | Arthur | 0.23 | Older method |

- **Supported:** v3 runs unchanged on a new storm and gives useful maps on some passes, and a truth-free warning flagged the two passes it could check, both of which scored below 0.60.
- **Not supported:** that v3 is reliably accurate, or that it beats earlier methods when rain has brightened the whole scene.
- **Main weakness:** v3 has no way to separate flood brightening from scene-wide wetting when both are strong.

**Wording for the app and pitch:** "On a storm the method had never seen, it scored CSI 0.47 on the primary river and 0.71 on a second, a mixed result by the rule we set in advance. It struggles when rain brightens the whole scene, and a warning we fixed before the run flagged those passes."
