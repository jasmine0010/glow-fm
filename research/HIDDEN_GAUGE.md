# Hidden-gauge test: can the water estimate predict a gauge it hasn't seen?

**Question:** the flood estimate draws a water surface between river gauges. If one gauge is hidden, how well do the others predict its reading?

## Rules, written before any held-out error was computed

**Passes:** the 15 used passes on rivers with at least 3 gauges: Choctawhatchee, Pearl, Tangipahoa, Yellow, Pee Dee, Neuse and lower Sabine. Village Creek and Pine Island Bayou have only 2 gauges, so nothing can be hidden there.

**Method:** hide each gauge that lies between two others, one at a time, and interpolate along the valley from the remaining gauges exactly as the estimate does. No radar is used.

**Measures:**
1. **Water-level error:** predicted minus measured level at the hidden gauge, compared with the estimate's ±0.5 m margin.
2. **Effect on the map:** rebuild the estimated flooding without the hidden gauge, then compare it with the full estimate within 10 km of that gauge. Agreement is shared flooded area divided by combined flooded area. Permanent water is left out. Cases where neither version has at least 50 ha are left out of this measure.

**Fair comparison:** the real estimate only uses ground within 10 km of a gauge, so its gauges are effectively no more than 20 km from the ground they describe. Hiding a gauge widens the gap, so the test is harder than real use. Results are reported for all cases, and for cases where the two remaining neighbours are at most 40 km apart, because a pixel in such a gap is at most 20 km from a gauge.

**Reading, fixed now, on all cases:**

| Share of errors within ±0.5 m | Reading |
|---|---|
| 80% or more | The margin holds up |
| 50% to 80% | The margin is partly supported |
| Below 50% | The margin is too small for these gaps |

**Limits stated first:**
- This tests water level along the channel. It can't test whether water under the trees, away from the channel, sits at the same level.
- Gauges are on the main channel, and backwater, tributaries and dams can all break a straight-line surface.
- Errors on one river and storm aren't independent, so this is a description and not a formal test.
- These rivers were already used, so nothing here is held out from the development of the estimate's settings.

## Results (`scripts/hidden_gauge.py`, `research/hidden_gauge.json`)

**The estimate does not predict hidden gauges well over long gaps. Under the rule above, the ±0.5 m margin is too small for these gaps.** Only 27% of the 22 hidden-gauge cases fell within it, and the median error was 1.14 m.

| River | Cases | Median error | Within ±0.5 m | Average predicted minus measured | Median map agreement |
|---|---|---|---|---|---|
| **All** | **22** | **1.14 m** | **27%** | **+1.29 m** | **0.72** |
| Pee Dee | 3 | 0.46 m | 67% | −0.25 m | 0.70 |
| Choctawhatchee | 2 | 0.41 m | 50% | −0.41 m | 0.62 |
| Pearl | 4 | 0.77 m | 50% | +0.57 m | 0.86 |
| Lower Sabine | 1 | 0.43 m | 100% | +0.43 m | not enough flooding |
| Yellow | 6 | 1.14 m | 0% | +1.04 m | 0.87 |
| Neuse | 2 | 1.85 m | 0% | +1.85 m | 0.12 |
| Tangipahoa | 4 | 4.20 m | 0% | +4.31 m | 0.03 |

**What this shows:**
- **Long gaps are the problem, and this test can't separate them from a real limit near gauges.** Hiding a gauge left neighbours 37–91 km apart, and only 3 cases were 40 km or less. The real estimate only scores ground within 10 km of a gauge, a situation no case here reproduces, so its actual error near gauges remains unmeasured. It should be smaller, but that is an expectation and not a result.
- **The error is mostly in one direction.** On most rivers the straight line predicts water higher than measured, by 1.29 m on average, though the Pee Dee and Choctawhatchee go the other way. A straight line isn't a good model of a river's real profile over these distances, and it would overstate flooding midway between distant gauges.
- **The map effect varies a lot.** On low-relief reaches the flooded area barely moves (Pearl 0.86, Yellow 0.87, though Yellow's comparison has under 100 ha near its gauge). On steeper ones it collapses (Tangipahoa 0.03, Neuse 0.12).
- **The largest errors have a likely physical cause, not yet checked.** Tangipahoa's 7 m error, at Amite, spans a steep part of the river, where a straight line between distant gauges fails badly.

**What this means for the project's claims:**
- Scores at and near gauges are likely the most reliable, and "estimated flooding" must stay labelled as an estimate.
- This adds to the open question of why the v4 rivers failed. On the Neuse, flooding near the Kinston gauge would change from 0 ha to 1,437 ha without that gauge, so the estimate there depends heavily on gauge placement.
- A useful follow-up check is whether scores change when limited to ground within 5 km of a gauge. It is built into the overbank test (`OVERBANK_PROTOCOL.md`).
