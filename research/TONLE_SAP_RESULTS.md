# Tonle Sap results

**Unvalidated demonstration.** There are no gauges or lidar here, and nothing is scored. Rules are in `TONLE_SAP_CASE.md`, whose hash is recorded in `tonle_sap_results.json`. Those rules weren't in a commit before the run, so this record is weaker than the frozen tests. The other files are `tonle_sap_results.json` and `tonle_sap_posthoc.json`.

## Answer

- **Three of the four predictions failed.** So under the rules fixed first, this case doesn't show that the signal "behaves like a seasonal flood".
- **The v4 map shouldn't be used here.** Its label reads low confidence on all seven passes, and its mapped area swings from 155,862 ha on Aug 30 to 22,584 ha on Oct 17. So the site doesn't present it as a flood map.
- **A different signal, found after the run, looks more promising.** Land that goes dark in HH matches GFM's water and spreads outward from the lake through the season. That's a hypothesis for a new test, and it isn't a result.

## The fixed predictions

| # | Prediction | Result | Holds? |
|---|---|---|---|
| 1 | Median HH change in tree cover within 15 km of the lake peaks on Sep 11 or later | Peaked on Aug 30 at +1.6 dB, then fell to −0.8 dB | **No** |
| 2 | HH exceeds HV by at least 1 dB at that peak | 1.9 dB | Yes |
| 3 | Tree cover at least 30 km from the lake stays under 1 dB | Reached +2.4 dB on Sep 11 | **No** |
| 4 | Bright tree cover rises with GFM's water, rank correlation at least 0.6 | −0.5 on five dates | **No** |

Prediction 3 matters most. Forest far from the lake brightened as much as forest near it, so bright forest here can't be attributed to the flood. Seasonal change in leaves or soil moisture is a likely alternative, but this case didn't test it.

**Coverage note:** GFM's July 25 and Aug 18 records didn't meet the 90% coverage rule, so prediction 4 used the five later dates.

## Post-hoc: what the radar did instead

None of this was predicted, and it can't rescue the failed predictions. Thresholds were chosen after seeing the numbers, on one lake in one season.

**1. Dark land matches GFM's water, far more often than chance.**

| NISAR date | GFM date | GFM water that's dark in NISAR | Other land that's dark, within 30 km of the lake | Dark land that GFM calls water |
|---|---|---|---|---|
| Aug 30 | Aug 28 | 88% | 10% | 34% |
| Sep 11 | Sep 9 | 92% | 17% | 27% |
| Sep 23 | Sep 21 | 84% | 25% | 30% |
| Oct 5 | Oct 3 | 86% | 34% | 17% |
| Oct 17 | Oct 15 | 90% | 34% | 15% |

Open water is smooth, so it reflects radar away and looks dark. GFM comes from a different satellite and method. But most dark land is *not* GFM water: dark land reached about 215,000 ha, against 42,000 ha of GFM water. GFM's exclusion mask explains little of that gap (10–19%). The rest could be flooding GFM missed, flooded rice fields, or something else. This check can't tell.

**2. The darkening spreads outward through the season.** Share of land more than 3 dB darker than the baseline, by distance from the lake:

| Date | 0–5 km | 5–10 km | 10–15 km | 15–20 km | 20–30 km | 30–50 km |
|---|---|---|---|---|---|---|
| Jul 25 | 3% | 6% | 3% | 1% | 2% | 0% |
| Aug 18 | 19% | 9% | 6% | 3% | 2% | 2% |
| Aug 30 | 42% | 19% | 13% | 5% | 1% | 1% |
| Sep 11 | 57% | 29% | 21% | 10% | 3% | 1% |
| Sep 23 | 67% | 42% | 30% | 20% | 7% | 9% |
| Oct 5 | 72% | 50% | 35% | 26% | 11% | 24% |
| Oct 17 | 70% | 50% | 36% | 26% | 13% | 22% |

The pattern within 30 km is what a rising lake would produce. The 30–50 km band jumps in October, so something else also darkens the landscape, and rice fields are one possibility.

**3. Forest near the lake brightens, then darkens.** Tree cover 0–5 km from the lake moves from +1.3 dB on Aug 18 to −3.2 dB on Oct 5. At 20–30 km it reaches +2.6 dB on Sep 11 and is still positive in October. One reading is that water first reaches the trunks, which boosts the signal, and later rises high enough to hide them. This is plausible, but it hasn't been tested, and flooded trees here could behave in other ways.

## What can be claimed

**Supported:** "NISAR's radar shows large seasonal change around Tonle Sap from July to October 2026. Water GFM maps is almost always dark in NISAR, and dark land spreads outward from the lake through the season."

**Must accompany it:** this was found after our predictions mostly failed, on one lake in one season, with no ground measurements, and dark land covers far more area than GFM's water.

**Not supported:** that this is a validated flood map, that the US method transfers to the tropics, or that the extra dark land is flooding that GFM missed.

## What this says about the method

The US method was built for short river floods in forest. A months-long lake flood broke its assumptions: forest brightening isn't specific here, and water deep enough to look dark isn't what it looks for.

## What to test next

The dark-spreading idea could get a real test. The same track covers the southeast of the lake, which hasn't been read. Rules could be fixed first: GFM water is dark more often than other land, and darkening spreads outward. It's the same lake and season, so a pass wouldn't show the idea works elsewhere.

## Corrections to earlier statements

- **40 MHz coverage:** the 40 MHz scenes first counted over Tonle Sap only clip the north edge of the search box, and don't reach the lake.
- **20 MHz reader:** 20 MHz data doesn't need a new reader. Its 20 m pixels fit a 60 m grid exactly.
