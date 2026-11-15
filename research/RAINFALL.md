# Does rain explain the radar's false alarms?

**Question:** the project has said that rain may explain scene-wide brightening and low scores, without any rainfall data. Is that supported?

**Answer: partly.** With IMERG satellite rainfall, 6 of 7 brightened passes followed rain, and no rainy pass scored above 0.65, while 7 of 9 other passes scored 0.61 or higher. Two low scores, on the Pee Dee and lower Sabine, came with little rain, so rain isn't the whole explanation. This is exploratory, on rivers already studied. The app uses IMERG; see the last section.

## Rules, written before any rainfall was compared with radar

**Rainfall source:** NASA POWER hourly precipitation (MERRA-2) at the centre of each river's study box, plus USGS rain gauges at the river's own gauges where they exist. Both need no account.

**Totals:** rain in the 6, 24 and 72 hours and 7 days before the NISAR pass, and in the 72 hours before v3's dry pass.

**A pass counts as rainy if** at least 5 mm fell in the prior 24 hours, or at least 25 mm in the prior 72 hours. Wet leaves dry within hours, while wet ground lasts for days, which is why there are two windows.

**A scene counts as brightened if** higher valley forest (4–8 m above the river) changed by more than +0.5 dB from its usual level. That is v4's existing rule.

**Questions, all exploratory:**
1. Are rainy passes more often brightened than others?
2. On rainy passes, does HH minus HV separate estimated flooding from estimated dry ground better than HH alone, as physics suggests? AUC on the same pixels, using the median baseline.
3. Do rainy passes score lower?

**Status shown in the drivers panel:**

| Condition | Status |
|---|---|
| Rainy and brightened | Likely contributor |
| Rainy or brightened, not both | Possible |
| Neither | Little sign |

**Nothing about the map changes.** A rain gate or any other method change would need a fresh frozen test.

**Limits stated first:** MERRA-2 is a coarse computer weather model (about 50 km) and not a rainfall observation, so it will smooth out local downpours. These passes are few and share storms, and one earlier post-hoc comparison already suggested the brightening link, so none of this is a clean test. NASA's satellite rainfall product, IMERG, needs a one-time approval on the user's Earthdata account.

## First results, with the weather model (`scripts/rain_check.py`, `research/rainfall_by_pass.json`)

The IMERG results below replace these as the project's answer. They are kept because the rules were written for this run.

**Rain explains part of the scene-wide brightening, and it doesn't explain every failure.** The rainfall source is weak, so treat this as supporting evidence, not proof.

| Question | Result |
|---|---|
| Are brightened scenes rainy? | **6 of 7 brightened passes were rainy.** 4 of 10 rainy passes did not brighten. Rank correlation of 72-hour rain with higher-ground change: 0.52 |
| Does HH minus HV help on rainy passes? | **Yes, modestly.** It beat HH on 6 of 9 rainy passes (mean AUC gain +0.05), and on 3 of 9 others (mean change 0.00) |
| Do rainy passes score lower? | v4 CSI averaged 0.45 on 8 rainy passes and 0.59 on 7 others, a difference that is small against the spread |

**What this supports:**
- Village Creek Sep 3 and Yellow Oct 5 are rainy and brightened, and they fit the rain explanation. So do Tangipahoa Jun 21, Neuse Jul 26 and Pine Island Bayou Sep 3.
- v4's switch to HH minus HV in brightened scenes makes physical sense, and this adds some support.

**What it doesn't support:**
- **Rain doesn't explain all the failures.** The lower Sabine (CSI 0.05) isn't rainy by the model and hasn't brightened, though one of its two gauges read 51 mm. The Pee Dee (0.10) is rainy only by the model and hasn't brightened. Pine Island Bayou Sep 7 scored 0.70 despite counting as rainy and brightened.
- **"Little sign" doesn't mean a dry week.** The rule looks back 72 hours. Pearl Jun 25 had 141 mm in the prior 7 days by the model and scored 0.46, and Yellow Oct 9 had 588 mm by the model, though IMERG gives only 73 mm, and scored 0.61. Neither brightened, and older rain could still matter through wet ground.
- **Ponding can't be separated.** Rain could leave standing water that the gauge-and-lidar estimate calls dry, so a "false alarm" may be real water on some passes. Nothing here distinguishes the two.

**The weather model and the rain gauges often disagree:**

| Pass | Model, 72 hours | USGS rain gauge, 72 hours |
|---|---|---|
| Yellow Oct 4 | 352 mm | 13 mm (Milton) |
| Yellow Oct 5 | 527 mm | 150 mm (Milton) |
| Village Creek Sep 3 | 101 mm | 228 mm (Kountze) |
| Pine Island Bayou Sep 3 | 75 mm | 102 mm (Beaumont) |
| Pee Dee Jul 27 | 35 mm | 13 mm (Bennettsville) |
| Lower Sabine Jul 17 | 18 mm | 51 mm (Ruliff), 3 mm (Bon Wier) |

Gauges are single points and the model covers about 50 km, so neither is the true area average, but gaps this large mean the rainy label can be wrong on individual passes. The IMERG check below tests this directly.

**Nothing in the method changed.** Using rain to gate or adjust maps would need a fresh frozen test.

## IMERG check: rules written before any IMERG total was computed

The only IMERG value seen before this was written is one test half-hour on Oct 16, 2026, which read zero.

**Source:** IMERG V07 Late Run, half-hourly (`GPM_3IMERGHHL`), `precipitation` in mm per hour, so each half-hour counts as half its value. The Final Run would be better because it is adjusted to monthly gauge totals, but it ends in September 2025, so it covers none of these passes.

**Area:** the average of the 0.1° cells (about 10 km) whose centres fall in the river's study box. MERRA-2 was read at the box centre.

**Totals:** 24 hours, 72 hours and 7 days before the pass. A total needs at least 90% of its half-hours, or it is left blank.

**Unchanged:** the rainy and brightened thresholds, the status table and the three questions above.

**Agreement with rain gauges:** for every pass and USGS rain gauge, compare 72-hour rain from the IMERG cell containing the gauge, and from MERRA-2, with the gauge. The measure is the median of |log10((source + 1) / (gauge + 1))|, in mm, where smaller is better. Also count how often each source gives the same rainy label as the gauge.

**Which source the app uses:** IMERG, unless its median gauge error is larger than MERRA-2's. In that case the app keeps MERRA-2 and says why.

**Limits stated first:** IMERG is a satellite estimate, not a ground measurement, and the Late Run has no monthly gauge adjustment. A gauge is a point and a cell is about 10 km across, so even a perfect estimate would differ from a gauge in scattered storms. A gauge can also fail, so a gauge is not perfect truth. These passes are the same ones as before, so this remains exploratory.

**Nothing about the map changes.**

## IMERG results (`scripts/rain_imerg.py`, `research/rainfall_imerg.json`)

**IMERG agrees with rain gauges far better than the weather model, and the rain explanation gets stronger with it. Rain still doesn't explain every failure.**

| Measure | Weather model (MERRA-2) | IMERG |
|---|---|---|
| **Typical gap from a rain gauge, 72 hours** | **2.6×** | **1.5×** |
| Rainy label agrees with the gauge (13 comparisons) | 10 | 11 |
| Rainy passes, of 19 | 10 | 8 |
| Brightened passes that were rainy | 6 of 7 | 6 of 7 |
| Rainy passes that brightened | 6 of 10 | 6 of 8 |
| Rank correlation, 72-hour rain with higher-ground change | 0.52 | **0.80** |
| HH minus HV beats HH, rainy passes | 6 of 9 | **6 of 7** |
| HH minus HV beats HH, other passes | 3 of 9 | 3 of 11 |
| Mean AUC gain from HH minus HV, rainy / other | +0.05 / 0.00 | +0.08 / −0.01 |
| Mean v4 CSI, rainy | 0.45 (8 passes) | **0.34** (6 passes) |
| Mean v4 CSI, other | 0.59 (7 passes) | **0.63** (9 passes) |

**Which source the app uses:** IMERG, under the rule set in advance, since its median gauge error (0.18) is below the model's (0.42).

**Is the gauge comparison fair?** Mostly:
- IMERG was closer on 9 comparisons and further on 2, with 2 ties where both sources and the gauge read zero.
- IMERG had an advantage in being read at the gauge's own cell. Its study-box average, the same area the status uses, still has a gap of only 1.6×.
- Leaving out the ties gives 1.6× against 2.8×.
- The Milton gauge supplies 6 of the 13 comparisons. Taking a median per gauge, IMERG is closer at 5 of 6 gauges, and the exception is Ruliff.

**Where IMERG is weak:** it reads low on the two wettest gauge readings: 99 mm against 150 mm at Yellow Oct 5, and 163 mm against 228 mm at Village Creek Sep 3. At Ruliff it gives 7 mm against 51 mm, while the other lower Sabine gauge reads 3 mm, so that was either a local storm or a gauge problem.

**v4 CSI by rain, on passes that can be judged:**

| | CSI values |
|---|---|
| Rainy | 0.06, 0.08, 0.31, 0.46, 0.49, 0.65 |
| Not rainy | 0.05, 0.10, 0.61, 0.70, 0.70, 0.85, 0.85, 0.89, 0.91 |

**What this shows:**
- No rainy pass scored above 0.65, and 7 of 9 other passes scored 0.61 or higher.
- **Rain doesn't rescue the frozen tests on fresh rivers.** The Neuse (0.06) fits the rain explanation. The Pee Dee (0.10, 14 mm in 72 hours) and lower Sabine (0.05, 9 mm) don't, and they remain unexplained.
- Pine Island Bayou Sep 7 brightened with only 17 mm in 72 hours, and 132 mm in the prior week. Wet ground from the earlier storm is one possible reason. It scored 0.70.

**Corrections to the first results:**
- The model's very large Yellow figures don't hold up. Yellow Oct 4 falls from 352 mm to 15 mm in 72 hours, and Yellow Oct 9's prior week falls from 588 mm to 73 mm.
- Yellow Oct 4 stays rainy, now with a gauge in support, but only just: about 5 mm in 24 hours by IMERG and 7 mm by the gauge.

**Six statuses changed:**

| Pass | Weather model | IMERG |
|---|---|---|
| Choctawhatchee Oct 17 | Possible | Little sign |
| Pearl Jun 25 | Little sign | Possible |
| Yellow Oct 17 | Possible | Little sign |
| Village Creek Sep 7 | Possible | Likely contributor |
| Pine Island Bayou Sep 7 | Likely contributor | Possible |
| Pee Dee Jul 27 | Possible | Little sign |

**Limits:**
- These are the same passes that suggested the idea, and many share a storm. Simple significance tests give p of about 0.05 for HH minus HV and 0.07 for CSI, but they assume independent passes, so they overstate the evidence.
- **Lower scores on rainy passes aren't purely radar failures.** Rain can leave standing water that the gauge-and-lidar estimate calls dry, so some false alarms may be real water.
- Rain and flood timing can go together. Yellow Oct 5, for example, came before the main rise, so its low score may reflect timing as well as rain.

**What would make this stronger:** a warning from rainfall alone, fixed in advance and tested on a future flood, because the Late Run is available within about a day. Nothing here changes the map.
