# Bare-earth test results

**Run once from freeze commit `e8580f7`, with one logged attempt** (15:00:16 UTC, eight seconds after the commit). The rules are in `BARE_EARTH_PROTOCOL.md`, and results are in `bare_earth_results.json`. The run reproduced every recorded Copernicus and lidar score, and the replayed frozen map matched the saved one on every scored pixel of all seven passes.

## Answer

- **Does a bare-earth model recover what losing lidar cost? Partly supported, under the fixed rule.** NISAR with FABDEM averaged 0.35, up from 0.25 with Copernicus GLO-30. It won clearly on 4 of 7 passes and lost on 1. "Supported" needed it to lose on none. The loss is small (−0.01 on the Pee Dee, a pass where the method already fails), but the rule is the rule.
- **Most of the cost is recovered.** The gap to NISAR with lidar shrinks from 0.13 to **0.03, "small"** by the fixed reading. That is about three quarters of the loss recovered.
- **The gain isn't hiding in unchecked ground.** NISAR with FABDEM mapped 0.86 times the area NISAR with lidar did, with 0.85 times its labelled share. The guard (more than 1.5 times the area, or under half the share) wasn't triggered.
- **Tree height was the cause, as predicted.** On Satilla Oct 15, ground the estimate calls flooded sits a median 0.39 m above the river by FABDEM, against 4.92 m by Copernicus and −0.39 m by lidar (P1 holds). FABDEM put that ground closer to lidar than Copernicus did on 6 of 7 passes (P2 holds).
- **Does radar still beat a bare-earth height map? Partly supported, and not robust.** NISAR averaged 0.35 against 0.34 for the FABDEM height map. It won on 2 passes and lost on 1. **At its best limit for each pass, the height map would average 0.38 and the reading would be "not supported."** That limit uses the answer, so no real user could pick it, but the margin is too thin to claim radar beats a bare-earth map on accuracy alone.

## Results

CSI against the gauge-and-lidar estimate, on the pixels each frozen v4 run scored. Paired 95% intervals from a 2 km block bootstrap (2,000 draws, seed 0). A map wins on a pass only if the interval is entirely on its side of zero.

**Question 1: NISAR with FABDEM against NISAR with Copernicus**

| Pass | NISAR with FABDEM | NISAR with Copernicus | Difference (95% interval) | Winner | NISAR with lidar |
|---|---|---|---|---|---|
| Satilla Oct 15 | **0.64** | 0.42 | +0.23 (+0.18 to +0.29) | FABDEM | 0.73 |
| Satilla Oct 19 | **0.62** | 0.42 | +0.20 (+0.08 to +0.28) | FABDEM | 0.72 |
| Ochlockonee Oct 14 | **0.44** | 0.32 | +0.13 (+0.03 to +0.21) | FABDEM | 0.43 |
| St Marys Oct 7 | **0.58** | 0.47 | +0.10 (+0.02 to +0.16) | FABDEM | 0.58 |
| Pee Dee Jul 27 | 0.03 | **0.04** | −0.01 (−0.02 to −0.00) | Copernicus | 0.10 |
| Neuse Jul 26 | 0.07 | 0.07 | −0.00 (−0.03 to +0.03) | Neither | 0.06 |
| Lower Sabine Jul 17 | 0.08 | 0.03 | +0.05 (−0.00 to +0.15) | Neither | 0.05 |
| **Mean** | **0.35** | **0.25** | **+0.10** | | **0.38** |

On the Ochlockonee and St Marys, NISAR with FABDEM matches NISAR with lidar (0.44 against 0.43, 0.58 against 0.58). On the Satilla it is still about 0.10 behind.

**Question 2: NISAR with FABDEM against the FABDEM height map** (forest, wetland or other land cover under 2 m above the river; no radar)

| Pass | NISAR with FABDEM | FABDEM height map | Difference (95% interval) | Winner | Height map at its best limit |
|---|---|---|---|---|---|
| Satilla Oct 15 | **0.64** | 0.60 | +0.05 (−0.07 to +0.18) | Neither | 0.62 at 6 m |
| Satilla Oct 19 | **0.62** | 0.52 | +0.10 (+0.04 to +0.24) | NISAR | 0.52 at 2 m |
| Ochlockonee Oct 14 | **0.44** | 0.40 | +0.04 (−0.03 to +0.10) | Neither | 0.42 at 1 m |
| St Marys Oct 7 | **0.58** | 0.37 | +0.21 (+0.11 to +0.27) | NISAR | 0.42 at 1 m |
| Pee Dee Jul 27 | 0.03 | **0.13** | −0.10 (−0.18 to −0.06) | Height map | 0.16 at 1 m |
| Neuse Jul 26 | 0.07 | **0.11** | −0.04 (−0.09 to +0.00) | Neither | 0.14 at 1 m |
| Lower Sabine Jul 17 | 0.08 | **0.27** | −0.19 (−0.31 to +0.01) | Neither | 0.37 at 1 m |
| **Mean** | **0.35** | **0.34** | **+0.01** | | **0.38** |

As in the no-lidar test, NISAR does better on the four passes where its signal exists and worse on the three where v4 already failed. On the failures, a plain height map with a low limit does better than radar.

**Area checks** (summed over the seven passes, within the scored pixels)

| Map | Mapped area | On ground more than 5 m above the water by lidar |
|---|---|---|
| NISAR with FABDEM | 53,766 ha | 2,438 ha |
| NISAR with Copernicus | 24,850 ha | 1,011 ha |
| NISAR with lidar | 62,853 ha | 2,967 ha |
| FABDEM height map | 74,980 ha | 2,551 ha |

The FABDEM map is smaller than the lidar map, not larger, so the gain didn't come from mapping more ground the estimate can't check. On the Pee Dee, though, nearly half of NISAR with FABDEM's 1,865 ha sits more than 5 m above the water (865 ha).

**Height of the ground the estimate calls flooded** (median, metres above the river)

| Pass | Lidar | Copernicus | FABDEM | FABDEM closer to lidar? |
|---|---|---|---|---|
| Satilla Oct 15 | −0.39 | +4.92 | +0.39 | Yes |
| Satilla Oct 19 | −0.40 | +5.11 | +0.61 | Yes |
| Ochlockonee Oct 14 | −0.66 | +3.59 | −0.17 | Yes |
| St Marys Oct 7 | −1.60 | +2.42 | −3.57 | Yes |
| Pee Dee Jul 27 | −0.27 | +3.98 | +4.69 | No |
| Neuse Jul 26 | −0.53 | +3.03 | +0.29 | Yes |
| Lower Sabine Jul 17 | −1.06 | +9.54 | +0.98 | Yes |

The one pass where FABDEM didn't bring flooded ground down toward the river, the Pee Dee, is also the one pass FABDEM lost on Question 1. That fits the tree-height explanation, but it is an observation after the run, not a tested prediction.

## What can be claimed

**Supported:** "On seven US flood passes with no lidar in the map, switching to a global elevation model with the trees removed (FABDEM) raised NISAR's mean score from 0.25 to 0.35, within 0.03 of the lidar version. It won on four passes and lost narrowly on one."

**Must accompany it:**
- The FABDEM height map alone averaged 0.34, and 0.38 at its best limit per pass. On mean accuracy alone, radar doesn't clearly beat a bare-earth height map. Its value is on the passes where its signal exists, and in showing when a flood arrives and drains, which a height map can't.
- The test still used gauges for the valley line and the scoring, as in the no-lidar test.
- All seven passes are in the southeastern US, and FABDEM's forest correction may have been trained on lidar from regions like these, which would flatter it here more than in the tropics.

**Not supported:** that this holds in the tropics, where forests are taller and the correction is less certain; or that the method needs no ground-height data. Maps outside the US stay labelled unvalidated.

## Licence and attribution

FABDEM V1-2 (https://doi.org/10.5523/bris.s5hqmjcdj8yo2ibzi9b4ew3sn) is CC BY-NC-SA 4.0. No FABDEM tile or derived layer is committed or published; only scores and summary numbers are recorded here.

Hawker, L., Uhe, P., Paulo, L., Sosa, J., Savage, J., Sampson, C. & Neal, J. (2022). A 30 m global map of elevation with forests and buildings removed. *Environmental Research Letters* 17, 024016.

> FABDEM is produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved.
