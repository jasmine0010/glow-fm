# Method v3 through time on the Yellow River

**v3 tracks the flood well once it is established, but it mapped false flooding on Oct 5, before the main rise.** All six usable passes were scored with v3 unchanged. Only Oct 16 is the pre-registered test (`V3_YELLOW_RESULTS.md`). The rest are follow-up scores: chosen after that test, on scenes that were never used to change the method.

**Data:** `v3_yellow_series.json`, from `scripts/score_yellow_series.py`. Each track keeps the dry pass the protocol's rule chose for it: 055D Sep 22, 076A Sep 23, 127D Sep 27. Oct 12 (track 004A) is left out because it has no valid radar on any labelled pixel.

| Pass | Gauge timing (Oak Grove / Milligan / Milton) | Largest rise since dry pass | Threshold | Mapped | Confirmed | Mapped on dry ground | CSI (95% range) |
|---|---|---|---|---|---|---|---|
| Oct 4 | rising / rising / rising | 0.1 m | 0.50 dB (floor) | 391 ha | 8 ha | 221 ha | 0.00 (0.00–0.01) |
| Oct 5 | rising / rising / near crest | 0.3 m | 1.10 dB | 2,705 ha | 1,031 ha | **1,678 ha** | **0.09 (0.03–0.14)** |
| Oct 9 | rising / rising / rising | 0.4 m | 1.07 dB | 1,435 ha | 1,003 ha | 192 ha | 0.58 (0.43–0.63) |
| **Oct 16, frozen test** | receding / receding / near crest | 1.5 m | 1.50 dB | 2,192 ha | 1,869 ha | 41 ha | **0.88 (0.80–0.92)** |
| Oct 17 | receding at all three | 0.8 m | 1.27 dB | 1,767 ha | 1,680 ha | 117 ha | 0.83 (0.67–0.89) |
| Oct 21 | late recession at all three | 0.3 m | 0.88 dB | 0 ha (abstains) | 916 ha | 0 ha | not scored |

Areas cover ground in the valley corridor, within 10 km of a gauge, excluding permanent water. Timing labels look 10 days back and 3 days ahead, so "near crest" at Milton on Oct 5 likely reflects a small early peak, not the main flood.

## What this shows

- **Good on two independent geometries.** Oct 16 (track 055D) and Oct 17 (track 076A) agree closely, a day apart, from different orbits.
- **No crest image.** The river crested Oct 11 to 14, and the nearest usable passes are Oct 9 and Oct 16.
- **False alarms before the flood.** v3 has no way to say "no flood here". Otsu always finds a split. On Oct 4 the 0.5 dB floor limited the damage, and on Oct 5 it did not.
- **Abstention has a real cost.** On Oct 21, v3 maps nothing while gauges and lidar still confirm 916 ha.

## A scene-wide warning sign (post-hoc)

On Oct 5, upland forest well above the river brightened by +0.98 dB in HH and +1.11 dB in HV, so the whole scene changed, not only the floodplain. Wet canopy or ground from rain could cause that: `RAINFALL.md` finds heavy rain before this pass. Comparing every judgeable pass suggests a general pattern that is visible without any truth:

| Pass | Upland HH change | v3 CSI |
|---|---|---|
| Yellow Oct 5 | **+0.98 dB** | 0.09 |
| Tangipahoa Jun 21 | **+0.66 dB** | 0.29 |
| Yellow Oct 9 | **+0.57 dB** | 0.58 |
| Pearl Jun 25 | +0.30 dB | 0.54 |
| Pearl Jul 3 | +0.21 dB | 0.68 |
| Choctawhatchee Oct 21 | −0.03 dB | 0.90 |
| Choctawhatchee Oct 17 | −0.08 dB | 0.82 |
| Yellow Oct 16 | −0.21 dB | 0.88 |
| Yellow Oct 17 | −0.36 dB | 0.83 |

The three passes above 0.5 dB include the two worst scores. This is nine passes from two storms, the rule was seen after the data, and several passes share a river and a storm, so it is a hypothesis. It would need a fresh test before being trusted.

**Update:** the first fresh test is in `EDOUARD_RESULTS.md`. The warning fired on both passes it could check, and both scored below 0.60. No unwarned pass could be tested there.

## A limit of the truth on this reach

Confirmed flooding went from 8 ha on Oct 4 to 1,031 ha on Oct 5, while the Milton gauge rose by about 0.4 m. That gauge sits on very low ground near sea level, where a small change in water level moves the label across a lot of land. Scores on this lower reach are therefore sensitive to gauge and lidar error, and low-lying swamp may already have been wet on the dry pass, which change detection cannot see. Nearly all of the frozen test's flooding is in this reach.
