# Hidden water budget results

**Rules:** `WATER_BUDGET_PROTOCOL.md`, SHA-256 `0bad3de2f7012df4d4cceba51cd9d5b442e28a4a79e16751ea6f7a513feb90e7` at analysis, unchanged then; `12156b31e81eb89450e2b7d4629f63737594921e98fa0034d5880915836ccf48` after dates were removed. It was not in a commit before the run. Data: `water_budget_results.json`, `water_budget_posthoc.json`. Scripts: `scripts/water_budget.py`, `scripts/water_budget_posthoc.py`.

**Run note:** a first launch failed before the script started, because the log folder didn't exist. Nothing had been read. After the run, `water_budget.py` got style-only lint edits. It wasn't run again.

**No frozen score changes.**

## Answer

- **River flow did not support the estimate's storage: 0 of 8 judged reaches were consistent.** Under the fixed rule, this reads **not supported**. The Satilla's one judged reach failed too, so no discharge support is claimed for its volume.
- **The test was probably too noisy to decide either way.** This is a post-hoc finding, below. It means the failure doesn't show the estimate is wrong, and it doesn't rescue the estimate.
- **The volume stays an estimate with a wide range.** On Oct 15 on the Satilla, within 10 km of a gauge, it is **40 million m³, and 13–69 million m³** if the water surface is 0.5 m lower or higher. That is **0.7–3.6 days** of the 218 m³/s peak flow at Atkinson, as a comparison of scale. Larger water-level errors are possible.
- **Don't claim the forest stored this river water, or that it protected anyone downstream.** Nothing here shows either.

## Did the estimate reproduce the frozen one?

Yes. At each reference pass with a stored frozen area, the through-time code gave the same flooded area, such as 3,623 ha on the Satilla Oct 15 and 1,868 ha on the Yellow Oct 16. Choctawhatchee, Pearl and Tangipahoa had no stored area to compare.

## Judged reaches

Storage is in million m³. The peaks are compared across the whole window.

| Reach | Length | Ungauged share | Peak estimated | Peak from flow | Ratio (1/3 to 3) | Peak gap (3 days or less) | Spearman (0.6 or more) | Reading |
|---|---|---|---|---|---|---|---|---|
| **Satilla, GA 158 to near Waycross** | 24 km | 28% | 26.3 | 12.2 | 0.46 ✓ | 24.4 days ✗ | −0.21 ✗ | Inconsistent |
| Ochlockonee, near Concord to near Havana | 17 km | 12% | 7.4 | 1.7 | 0.23 ✗ | 5.8 days ✗ | 0.13 ✗ | Inconsistent |
| Pee Dee, Bennettsville to Pee Dee | 54 km | 12% | 11.1 | 29.2 | 2.64 ✓ | 1.9 days ✓ | 0.49 ✗ | Inconsistent |
| Neuse, Cox Mill to Goldsboro | 20 km | 30% | 11.2 | 4.4 | 0.39 ✓ | 15.0 days ✗ | 0.12 ✗ | Inconsistent |
| Neuse, Kinston to Fort Barnwell | 30 km | 31% | 16.5 | 78.0 | 4.73 ✗ | 19.5 days ✗ | 0.10 ✗ | Inconsistent |
| Lower Sabine, Bon Wier to Ruliff | 54 km | 12% | 6.9 | 11.6 | 1.67 ✓ | 3.5 days ✗ | 0.06 ✗ | Inconsistent |
| Choctawhatchee, Pittman to Caryville | 20 km | 8% | 37.3 | 52.1 | 1.39 ✓ | 23.6 days ✗ | −0.25 ✗ | Inconsistent |
| Choctawhatchee, Caryville to Bruce | 38 km | 20% | 198.7 | 101.9 | 0.51 ✓ | 5.8 days ✗ | −0.09 ✗ | Inconsistent |

**By condition:** amount passed on 6 of 8, timing on 1 of 8, and shape on 0 of 8. Amount alone proves little, because the window is long and the range is wide. On the Satilla's judged reach, flow storage peaked in the last hours of the record, so it was still climbing when the data ended.

**The Satilla's other reach** (near Waycross to Atkinson, 56% ungauged) wasn't judged. It gave 20.4 estimated against 103.8 from flow, 9 days apart.

## Post-hoc: was the test able to decide?

This came after the run, and it changes no reading.

- **Flow storage wanders without flooding.** On days when estimated storage was near zero, flow storage still spanned a median range of **40.5 million m³** on judged reaches. The median estimated peak was 13.6 million m³. Those days fall both before and after the flood, so this range includes whatever the balance failed to return afterward, as well as day-to-day noise.
- **One reach makes this plain.** Sabine, Burkeville to Bon Wier, peaked at 12 ha of estimated flooding, and flow storage reached 49 million m³.
- **Flow storage doesn't close.** By the end of the window, its size was a median of 1.5 times the estimated peak. A balance that captured storage would return near zero after a flood drains.
- **Rising limbs alone do little better.** From the estimate's rise to its peak, 3 of 8 judged reaches had flow storage within 1/3 to 3 of estimated storage, and 2 had the wrong sign. On the Satilla the estimate rose by 25.0 while flow rose by 4.3.

**The likely problems are in the flow side:** the area ratio assumes inflow arrives like upstream flow, one travel time is used for a whole event, and out-of-bank rating curves are uncertain. A running total also accumulates every error. These are explanations, not tested results.

## A warning this doesn't remove

Noise doesn't excuse every gap. On some large floodplains, the estimate is far above anything flow storage shows at the same moment. On the lower Choctawhatchee, it rose by 195 million m³ while flow rose by 7. On the lower Yellow, unjudged at 53% ungauged, it rose by 126 while flow fell by 13.

Rain on the floodplain could add water the river never carried. Or the estimate could overstate depth on large, low floodplains, because it assumes water spreads flat at river level. **This check can't tell which.** The second possibility would mean volumes, and perhaps areas, run high.

## Limits

- **Not independent of the gauges.** USGS discharge usually comes from stage through rating curves.
- **Provisional records.** They may be revised.
- **Not radar.** This says nothing direct about NISAR.
- **Reaches share storms,** so 8 reaches aren't 8 independent tests.
- **The design was mine and it was weak.** Its failure is informative about the design as much as the estimate. Redesigning it now, with these numbers seen, wouldn't be a fresh test.

## What can be claimed

**Supported:** "The gauge-and-lidar estimate implies about 40 million m³ of water on the Satilla floodplain on Oct 15, and 13–69 million m³ for a water level 0.5 m lower or higher. A test against river flow didn't confirm this, and a later check suggests that test was too noisy to decide."

**Not supported:** that the volume is measured, that river flow agrees with it, that the forest stored this water or reduced a flood peak, or that it protected a community.
