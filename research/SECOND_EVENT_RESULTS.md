# Second-event (held-out) results: Pearl River, Tropical Storm Arthur

Protocol: `SECOND_EVENT_PROTOCOL.md`. Receipt: `freeze_receipt.json`. The integrity check at run time reported **no changes** to the hashed scientific modules. Raw outputs are in `outputs/pearl/<pair>/frozen_metrics.json`, written once.

## Frozen result (reported as is)

Rule: dry-date HV > −16 dB AND ΔHH > 2.0 dB, 50 m grid. Truth: gauge water surface minus lidar ground, ±0.5 m margin, connectivity to GFM reference water, 4 km corridor.

| Pair | Truth wet / dry (ha) | CSI (95% CI) | F1 (95% CI) | Recall | Precision |
|---|---|---|---|---|---|
| **Primary: 105A Jul 3 vs Aug 20** | 28,455 / 10,118 | **0.23 (0.17–0.30)** | 0.38 (0.29–0.46) | 0.24 | 0.96 |
| Secondary: 156D Jun 25 vs Aug 24 | 26,059 / 10,325 | 0.13 (0.09–0.17) | 0.23 (0.16–0.29) | 0.13 | 0.84 |

For comparison (development, not held-out): the Isaias lower reach scored CSI 0.67 (0.61–0.73) and 0.61 (0.56–0.66).

**The fixed-threshold detector does not transfer.** Its precision stays high: when it flags flooded forest, it's right 84–96% of the time. But it misses most of the flooded area.

## Post-hoc diagnostics (do not change the result above)

Script: `scripts/posthoc_pearl.py`. Output: `outputs/pearl/105A_jul03/posthoc_diagnostics.json`.

**1. The radar signal is weaker at Pearl, even where the truth is best constrained.** Median ΔHH of truth-wet pixels:

| | Isaias 076A | Pearl 105A | Pearl 156D |
|---|---|---|---|
| All truth-wet pixels | **+3.0 dB** | **+1.0 dB** | +0.6 dB |
| Reach between the two closest gauges (Bogalusa–Pools Bluff, 10 km) | — | +1.8 dB | +0.95 dB |
| Truth-dry pixels | +0.4 dB | +0.2 dB | +0.5 dB |

The double-bounce brightening exists at Pearl, but it is about half as strong, so a 2 dB cut (picked where the signal was about +3 dB) misses most of it. Lowering the cut to 1.0 dB would raise recall on newly flooded pixels from 0.22 to 0.46. That figure is post-hoc and must not be reported as a held-out result.

**2. The truth is weakest in the middle reach.**
- Pools Bluff to Pearl River, LA is 39 km with no usable gauge between. The river also splits into the East and West Pearl, and a navigation canal with locks runs alongside.
- The water surface drops about 14.6 m there on Jul 3, and linear interpolation over that distance can misplace it.
- Recall by reach: 0.43 upper (0–10 km), **0.16 middle**, 0.38 lower. Truth-wet ΔHH in the middle reach is only +0.5 dB, which is close to the dry-pixel distribution. That suggests many middle-reach "wet" labels may be wrong.

**3. It isn't mainly water that was already there.** Only 6,568 of 28,455 ha of truth-wet pixels were already wet on the Aug 20 reference date. Recall on newly flooded pixels (0.22) is about the same as overall.

## What this means

- **This is a real scientific result.** A fixed ΔHH threshold calibrated on one flood doesn't generalize, because the size of the L-band double-bounce change varies by event. Plausible reasons:
  - forest type and structure: Florida tupelo–cypress versus Louisiana bottomland hardwood;
  - season and moisture: June–July versus October;
  - flood duration and depth: the Pearl was 4+ m deep at Bogalusa and flooded for weeks;
  - viewing geometry.
  
  The project should say this openly. It is the kind of result expert judges respect, and it argues for validating against independent truth instead of trusting a pretty map.
- **Truth quality depends on gauge spacing.** The truth generator should report a per-reach confidence (distance to the nearest gauge, any channel split) and exclude or down-weight reaches between gauges more than about 15 km apart. That rule has to be fixed before it is applied to any new event.
- **Next methodological step (to pre-register before any new test):** a *self-calibrating* threshold chosen from each scene's own data, using only information available without truth. Options:
  - the ΔHH distribution of upland forest far from the river as the "no change" reference, flagging pixels above its 95th–99th percentile;
  - bimodal (Otsu) splitting inside the valley mask.
  
  It must then be tested on a **third** event. Isaias and Pearl are both spent for threshold selection.
