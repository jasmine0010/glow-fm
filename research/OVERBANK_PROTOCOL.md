# Overbank protocol: one frozen test of v4 and its trust signal on five unread rivers

**Written** before any radar backscatter, flood layer or truth over these rivers was read.
**Receipt:** `research/freeze_receipt_overbank.json`, with SHA-256 hashes of this file, the scene list, the locked rainfall, the site files, the run code and all scientific modules. The run refuses to start if any of them has changed. The freeze commit is the dated record.

**Questions:**
1. Does unchanged v4 find flooding under forest when a river is clearly above flood level? v4 failed on three floods that stayed below flood stage: Pee Dee 0.10, Neuse 0.06, lower Sabine 0.05.
2. Does a trust signal fixed in advance tell a user when to believe the map?

## 1. What has and has not been seen

**Used to select and set up:** catalog metadata, USGS gauge records, NWS flood values, lidar, WorldCover, GFM's static reference-water layer, each listed wet and dry scene's projection, grid limits and valid-sample mask, and IMERG rainfall. Gauge facts are in `overbank_gauges.json`, and the screen is in `overbank_screen.json`.

**Not seen:** any NISAR backscatter, browse image or interferogram over these rivers, any GFM or DSWx flood layer, and any truth at any time.

**Code check on a used river:** the scoring code was run once on Yellow River Oct 16 in a temporary folder (`scripts/check_overbank_code.py`). It reproduced v4's development CSI of 0.890845 exactly. No data from the five rivers was involved.

## 2. Passes, fixed now

The selection rule is `SECOND_EVENT_PROTOCOL.md` §2(b). On each river the pass with the largest mean rise is primary and the others are secondary. Rivers are ordered by the mean rise of their primary pass. All scenes are 40 MHz. Each listed wet and dry scene has HH and HV and at least 60% valid samples over the reach. Scenes are listed in `overbank_scenes.json`.

| Order | River | Pass | Role | Wet (UTC) | Dry (UTC) | Baseline scenes | Gauge rises | Mean rise |
|---|---|---|---|---|---|---|---|---|
| 1 | **Satilla, GA** | 047A Oct 15 | Primary | Oct 15 10:45 | Oct 3 | 5 | 3.34, 3.15, 2.87 m | 3.12 m |
| 1 | Satilla | 098D Oct 19 | Secondary | Oct 19 00:11 | Sep 25 | 5 | 2.80, 2.73, 2.95 m | 2.83 m |
| 2 | **Alapaha, GA/FL** | 047A Oct 15 | Primary | Oct 15 10:45 | Oct 3 | 5 | 2.49, 3.08, 2.52 m | 2.70 m |
| 2 | Alapaha | 148A Oct 22 | Secondary | Oct 22 10:54 | Sep 28 | 5 | 1.27, 3.09, 2.53 m | 2.30 m |
| 3 | **Ochlockonee, GA/FL** | 026D Oct 14 | Primary | Oct 14 00:20 | Oct 2 | 5 | 2.12, 2.79, 2.97, 2.83 m | 2.68 m |
| 4 | **Withlacoochee, GA/FL** | 047A Oct 15 | Primary | Oct 15 10:45 | Oct 3 | 5 | 2.94, 3.75, 1.97, 1.68 m | 2.58 m |
| 4 | Withlacoochee | 148A Oct 10 | Secondary | Oct 10 10:54 | Sep 28 | 6 | 2.60, 2.39, 0.97, 0.59 m | 1.64 m |
| 5 | **St Marys, GA/FL** | 098D Oct 7 | Primary | Oct 7 00:11 | Aug 20 | 5 | 2.90, 1.44 m | 2.17 m |
| 5 | St Marys | 047A Oct 15 | Secondary | Oct 15 10:45 | Sep 21 | 5 | 1.88, 1.97 m | 1.92 m |

**The headline is the first river in this order with at least 500 ha of estimated flooding and coverage of at least 0.60.** No other substitution is allowed.

**Passes removed by rule, before any radar was read:**
- Satilla 026D Oct 14 had the largest rise (3.19 m), but only 58% valid samples.
- Ochlockonee 148A, Alapaha 026D and Withlacoochee 026D are in a different map projection from their river's first qualifying pass, and the frozen reader can't use them.

**Gauges left out:** Woodbine on the Satilla and Kingsland on the St Marys are tidal. Bloxham on the Ochlockonee is below Lake Talquin. A straight water surface can't span any of them.

**All five rivers passed the screen:** forest and wetland make up 72–85% of the gauge-supported corridor, and all have reference water.

| River | Forest + wetland | Crop, grass or shrub | Corridor |
|---|---|---|---|
| Satilla | 76% | 20% | 34,552 ha |
| Alapaha | 81% | 18% | 28,433 ha |
| Ochlockonee | 80% | 19% | 45,530 ha |
| Withlacoochee | 72% | 25% | 46,909 ha |
| St Marys | 85% | 14% | 15,939 ha |

### Only some of these passes are above flood level

| Pass | Level minus NWS flood level at each gauge (timing) | Flood-stage pass? |
|---|---|---|
| **Satilla Oct 15** | +0.21 m (receding), −0.05 m (near crest), +0.08 m (receding) | **Yes, 2 of 3 gauges** |
| **Satilla Oct 19** | −0.15 m (receding), −0.37 m (receding), +0.34 m (rising) | **Yes, 1 of 3 gauges** |
| **St Marys Oct 15** | −0.85 m (late recession), +0.19 m (receding) | **Yes, 1 of 2 gauges** |
| St Marys Oct 7 | −0.05 m (near crest), −0.30 m (rising) | No |
| Ochlockonee Oct 14 | −1.24 m (late recession), −1.15 m (near crest), −0.88 m (near crest), −1.46 m (rising) | No |
| Alapaha Oct 15 | −1.30 m (receding), −3.51 m (rising), −2.83 m (rising) | No |
| Alapaha Oct 22 | −2.33 m (late recession), −3.35 m (receding), −2.73 m (near crest) | No |
| Withlacoochee Oct 15 | +0.04 m (near crest), −1.91 m (rising), −4.02 m (rising), −4.35 m (rising) | No: the one positive margin is smaller than the datum uncertainty |
| Withlacoochee Oct 10 | −0.61 m, −3.28 m, −4.99 m, −5.41 m (all rising) | No |

NWS lists the Alapaha and Withlacoochee values as elevations (for example 223 ft at a gauge reading 11 ft), so those compare stage plus the USGS datum. NWS's datum for them isn't stated, so their margins are approximate by tens of centimetres.

**So Satilla Oct 15 is the decisive overbank pass.** It is the headline river's primary pass and the only primary pass with gauges clearly above flood level. Most other passes test large rises rather than floods above flood stage. NWS flood level is set by local impacts and isn't a measurement of water on the forest floor.

## 3. Frozen method

Method v4 is unchanged, from `research/freeze_receipt_v4.json` and `V4_PROTOCOL.md` §3. Truth is unchanged from `V3_YELLOW_PROTOCOL.md` §3: USGS stage minus lidar ground, ±0.5 m margin, −5 m dry limit, 4 km corridor, connected to reference water, within 10 km of a gauge, permanent water excluded. It is an estimate of flooding and not an observation.

## 4. Trust signal, fixed now

**Green** (trust the map) if the v4 confidence label is High **and** the pass isn't rainy. **Red** otherwise.

- **Rainy** means at least 5 mm in the prior 24 hours or at least 25 mm in the prior 72 hours, as the IMERG V07 Late Run mean over the study box (`RAINFALL.md`).
- **Rainfall is locked now** in `overbank_rain.json`. Only two passes are rainy:

| Pass | 24 h | 72 h | Rainy |
|---|---|---|---|
| Withlacoochee Oct 10 | 47.7 mm | 53.6 mm | Yes |
| St Marys Oct 7 | 9.0 mm | 75.7 mm | Yes |
| The other seven | 0.0 mm | 0.0 mm | No |

The zeros were checked by reading single half-hours on Oct 13 and Oct 15, where every cell over the Satilla box read exactly 0, against non-zero cells on Oct 9 and Oct 10.

**Prediction:** green predicts v4 CSI of 0.60 or higher, and red predicts below 0.60. This rule was tuned on the 15 used passes, where green was right 6 of 6 times and red 7 of 9. **That record is in-sample, and this is the rule's first fair test.**

## 5. What is reported

For every pass: **v4 CSI on mapped, gauge-supported, non-permanent-water pixels**, with a 2 km block bootstrap (2,000 draws, seed 0), estimated flooding in hectares, the share of labelled ground that is flooded, and coverage of estimated flooding. Also the signal, its two inputs and the upland warning.

Also on the same pixels:
- v3, with the paired interval for v4 minus v3.
- **The lidar baseline:** forest, wetland or other land cover less than 2 m above the river. It uses no radar. Paired interval for v4 minus lidar.
- **Within 5 km of a gauge:** v4 and lidar, because the hidden-gauge test (`HIDDEN_GAUGE.md`) found the water estimate unreliable over long gaps. This is descriptive and has no pass mark.

All nine passes run, in one go, with no stopping or selection based on results.

## 6. Reading, fixed in advance

**Judgeable** means at least 500 ha of estimated flooding and coverage of at least 0.60. Anything else makes no claim and is reported as such.

| v4 CSI | Reading on that pass |
|---|---|
| 0.60 or higher | Strong |
| 0.40 to 0.60 | Moderate |
| Below 0.40 | Weak |

**Overbank question.** The answer has two parts, and both are reported:
- **Decisive pass:** the reading on Satilla Oct 15. If it isn't judgeable, no flood-stage claim comes from it, and the other two flood-stage passes are reported on their own.
- **All primary passes:** v4 **holds** if at least two-thirds of judgeable primary passes reach 0.60, **partly holds** if at least one does, and **fails** if none does. With fewer than two judgeable primary passes there is no overall reading.

**Trust signal.** It is scored as hits out of judgeable passes, with green and red shown separately. It is compared with the two trivial rules, always green and always red, on the same passes.
- **Held up:** at least 5 judgeable passes, at least 80% hits, and more hits than either trivial rule.
- **Mixed:** at least 5 judgeable passes and at least 60% hits, without meeting the bar above.
- **Did not hold up:** at least 5 judgeable passes and under 60% hits.
- **Too few:** fewer than 5 judgeable passes.

**Radar against lidar.** On a pass, radar beats lidar only if the paired 95% interval is entirely above zero, and lidar beats radar only if it is entirely below zero. Otherwise neither is shown better.

**What follows from the results:**
- If Satilla Oct 15 is strong, the project can say v4 found flooding on a held-out flood above flood stage, for this one flood.
- If it is weak, the project can't claim that, and the app and pitch must say so.
- **v4 won't be tuned on these passes.** Any later change is a new method that needs its own test.

## 7. Limits stated in advance

- **Not independent.** Four of the five primary passes come from Oct 14–15, and three from the same orbit pass (047A, Oct 15). The Alapaha and Withlacoochee are neighbouring basins. Nine passes aren't nine independent tests, and secondary passes share a flood with their primary.
- **Isaias is a development storm.** All passes follow the Isaias period, except St Marys Oct 7, which follows earlier rain. The rivers are unread, but the storm season, sensor period and forest type are familiar. The cause of each rise wasn't established.
- **The rain half of the signal is barely tested.** Only two of nine passes are rainy, so this is mostly a test of the confidence label.
- **The truth has a measured weakness.** Hidden gauges were predicted within ±0.5 m only 27% of the time, with a 1.14 m median error over 37–91 km gaps (`HIDDEN_GAUGE.md`). Error near gauges remains unmeasured.
- **Part of any score is geometry.** Truth and the lidar baseline both use the same lidar.
- **Water away from the channel isn't observed.** Ponded water can be labelled dry.
- **Late recession.** v4 doesn't map ground nearest a gauge in late recession: Coolidge on the Ochlockonee Oct 14, Alapaha on Oct 22 and Macclenny on St Marys Oct 15. Coverage may fall below 0.60 on those passes.
- **Open land.** v4 never maps crop, grass or shrub, which is 14–25% of these corridors. Flooding there lowers coverage.
- **Baselines can contain other events.** Withlacoochee Oct 10 includes Oct 22, Alapaha Oct 22 includes Oct 10, Satilla Oct 19 includes Oct 7, and St Marys Oct 7 includes Oct 19. A median limits their effect but may not remove it.
- **Rivers left out.** The Wabash uses a 20 MHz mode that the frozen reader can't read. Other rivers were weak or lacked data (`overbank_screen.json`).
- **Setup was restarted.** It restarted three times, for a projection bug, a track-selection bug, and a truncated land-cover tile left by one of those restarts. No radar was read in any of those runs.
- **Scene windows are read over the network.** A read failure before scoring may be rerun and is disclosed.

## 8. After the run

Results go to `outputs/<river>/<pass>/frozen_overbank_metrics.json` once and are copied unchanged into `research/`. Each attempt is logged before imagery is read. A bug fix after scoring counts as post-hoc, is labelled that way, and doesn't replace the first number. Later analysis is labelled post-hoc. Results go in `OVERBANK_RESULTS.md` whichever way they come out.
