# Tributary gauge check results

**Rules:** `TRIBUTARY_GAUGE_PROTOCOL.md`, SHA-256 `761024aa91b77c641c2b6d2d1c4b492d6ca19b9c2059596358abad2d040e0d98` at analysis, unchanged then; `875f4f09f57723d16a1a9b35a9fecaad7574a9e85f0ddac0b86c37b4023a4baf` after dates were removed. It was not in a commit before the run. Data: `tributary_gauge_results.json`. Scripts: `scripts/tributary_inventory.py`, `scripts/tributary_gauge_check.py`.

**Run note:** two attempts crashed on dropped connections to the gauge service before any results were saved, after printing some gauge rows. The final run added retries and caching. Inputs, rules and analysis didn't change, and the water and flag numbers in the printed rows reappeared identically in the final run. Flood stage is the one field that differed, because the second attempt couldn't fetch the NWS list.

**No frozen score changes.**

## Answer

- **Reading 1, do flags track measured water? Not shown.** Pooled local precision was 0.15 against 0.11 by chance, a lift of +0.04 (−0.02 to +0.47). There were only 3 usable pairs, so this says little.
- **Reading 2, how much do flags disagree? Mostly above measured water**, at 85% of flagged labelled pixels. One gauge, Contentnea Creek, supplies 627 of those 665 pixels, so the pooled number mostly describes one disc.
- **Only 3 of 14 pairs could be scored.** Six Pee Dee gauges and Big Cow Creek near Newton had no mappable ground in their discs.
- **It can't confirm flags on strong rivers.** None of those rivers has an unused gauge.

## The three scored pairs

| Gauge and pass | Rise from baseline | Flagged share of mappable ground | Flagged on measured-wet ground | Flagged on ground above the water | Local precision | Chance |
|---|---|---|---|---|---|---|
| Withlacoochee at Skipper Bridge, Oct 15 | 2.92 m | 58% | 113 | 16 | 0.88 | 0.57 |
| Withlacoochee at Skipper Bridge, Oct 10 | 1.64 m | 7% | 1 | 22 | 0.04 | 0.06 |
| Contentnea Creek at Hookerton, Neuse, Jul 26 | 1.08 m | 75% | 0 | 627 | 0.00 | 0.00 |

## All gauges

| River and pass | Gauge | Rise | Mappable pixels | Flagged share | Note |
|---|---|---|---|---|---|
| Withlacoochee, Oct 15 | Suwannee at Ellaville | 1.18 m | 763 | 0% | No flags, with 31 wet and 147 dry pixels |
| Withlacoochee, Oct 10 | Suwannee at Ellaville | 0.27 m | 763 | 7% | Too few labelled flags (3, all dry) |
| Lower Sabine, Jul 17 | Bear Head Creek near Starks | 1.29 m | 1,252 | 60% | No gauge datum, so no water surface |
| Lower Sabine, Jul 17 | Big Cow Creek at FM 1416 | 2.12 m | 425 | 16% | No gauge datum, so no water surface |
| Lower Sabine, Jul 17 | Big Cow Creek near Newton | 0.57 m | 0 | No result | Nothing mappable |
| Pee Dee, Jul 27 | Six gauges | 0.02–0.66 m | 0 | No result | Nothing mappable |

**Reading 3, flags against the tributary's state:** elevated gauges averaged 36% flagged (6 pairs) and the one not-elevated gauge 7%. The Spearman correlation with rise was 0.18. With one not-elevated pair, this says almost nothing.

**NWS flood stage:** not used for any reading. Several listed values don't share a reference with the USGS stage (135 ft against a 14 ft reading at Skipper Bridge), so those comparisons aren't meaningful.

## What this shows, read after seeing the numbers

These points weren't fixed readings, and each rests on one or two gauges.

- **A clear false alarm by this measure.** At Contentnea Creek, radar flagged 75% of mappable ground while measured water stayed about at the lowest nearby ground. No mappable pixel was below the water, and all 627 labelled flags sat 0.5–5 m above it. River water can't explain them. The project's rainfall work already recorded rain before this pass, which could explain brightening without river flooding, but this check didn't test that.
- **One gauge shows flags following the water.** At Skipper Bridge, flagged share went from 7% to 58% as the river rose by another 1.28 m, and flags moved from mostly above the water (1 of 23 wet) to mostly below it (113 of 129 wet). The passes use different tracks, so viewing geometry and scene threshold differ too. It is one gauge, and the passes aren't independent.
- **Evidence against the frozen estimate's 0 ha.** The frozen Withlacoochee Oct 15 estimate read 0 ha. An unused gauge shows water above nearby ground that day, and radar flagged it. This agrees with the earlier post-hoc finding that the connectivity rule hid flooding there. It changes no frozen result.
- **The method can't see most tributary floods.** It only considers ground under 6 m above the *main* river's profile, so ground along higher tributaries is never mappable. That left seven of the 14 pairs without a result. Those gauges rose little (up to 0.66 m), so little flooding was likely missed here, but it is a built-in blind spot.

## Limits

- **Small and unbalanced:** 3 scored pairs, on 2 gauges, 2 rivers, with one disc dominating the pool. The bootstrap over 3 pairs is very coarse.
- **Weak rivers only:** this says nothing about flags on the Satilla.
- **Flat water assumed within 1 km:** slope would misplace the water line, especially on small streams.
- **Lidar still sets the ground height,** and gauge datums carry their own errors of up to several tenths of a metre.
- **River water only:** flags above the river's level could be ponding or wet canopy, not necessarily dry ground.

## What can be claimed

**Supported:** "Near one unused gauge on the Neuse, radar flagged forest well above the measured river level. Near another on the Withlacoochee, flags grew and moved onto measured-wet ground as the river rose."

**Not supported:** that flags beyond the corridor are generally right or wrong. Too few gauges could be scored, and none on the strong rivers.
