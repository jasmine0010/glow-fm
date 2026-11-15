# Tributary gauge check: do radar flags beyond the corridor match measured water?

**Written** before any stage reading or flag near these gauges was read. The inventory (`scripts/tributary_inventory.py`) used only gauge location, datum, drainage area, and whether a reading existed that day.

**Weaker record:** this file's hash is recorded in the results, but it was not in a commit before the run. The run happens once, and the script refuses to overwrite its results.

**Question:** radar flags thousands of hectares outside the estimate's corridor, and the imagery checks couldn't judge them. Near stage gauges the estimate doesn't use, do flags fall on ground below the water those gauges measured?

## What this can and can't test

- **It tests false alarms on weak rivers.** No unused gauge reports on the Satilla, St Marys or Ochlockonee, so **it can't confirm flags on the strong rivers.**
- **It isn't independent of lidar.** Water level is new, but ground height is still lidar. It is independent of the estimate's gauges and water line.
- **It assumes a flat water surface within 1 km of the gauge.** Slope makes the surface wrong upstream and downstream, and tributary slopes can reach about a metre per kilometre.
- **Rain and ponding aren't river water.** A flag above the gauge's water surface may still be real ponding. It disagrees with measured river water, which isn't proof it is dry.
- **Maps are frozen v4 maps, unchanged.** All passes are already spent.

## Gauges and passes

Every gauge inside the scene with a stage reading that day and not used by that river's estimate, except springs.

| River and pass | Gauges | Datum available |
|---|---|---|
| Pee Dee, Jul 27 | Crooked Creek at Bennettsville, Black Creek near Quinby, Jefferies Creek near Florence, Lynches River at Effingham, Lynches River at US 378, Big Shoe Heel Creek | All six |
| Neuse, Jul 26 | Contentnea Creek at Hookerton | Yes |
| Lower Sabine, Jul 17 | Big Cow Creek near Newton, Bear Head Creek near Starks, Big Cow Creek at FM 1416 | Newton only |
| Withlacoochee, Oct 15 and Oct 10 | Withlacoochee at Skipper Bridge, Suwannee at Ellaville | Both |

Madison Blue Spring is excluded, because spring stage doesn't describe a flood.

## Measures

**Discs:** each gauge gets a 1 km disc. Only pixels outside the estimate's corridor count. Mappable means the method could flag the pixel: allowed land cover, under 6 m above the main river, valid radar and `mapped`. A disc with fewer than 100 mappable pixels gives no result for that gauge.

**A. Was the tributary up?** Rise is stage at radar time minus the median stage at that pass's baseline scene times, needing at least 3. **Elevated** means a rise of at least 1 m. NWS flood stage is reported where listed. Stage needs a reading within 6 hours of the radar time.

**B. Do flags sit below measured water?** For gauges with a datum, water surface = stage + gauge datum, converted to NAVD88. Depth = water surface minus lidar ground.
- **Local wet:** depth above 0.5 m, connected through ground below the water to within 300 m of the gauge.
- **Local dry:** depth between −5 m and −0.5 m.

**A datum check, before any stage is read:** a gauge is dropped from B if its datum is more than 5 m above, or more than 15 m below, the lowest lidar ground within 200 m.

**Local precision** = flagged wet / (flagged wet + flagged dry). **Chance** = wet share of mappable labelled pixels, which is what flags would score if unrelated to the water. **Lift** = local precision minus chance.

## Fixed readings

**1. Do flags track measured water?** Use gauge-pass pairs with at least 20 flagged labelled pixels. Pool counts, and bootstrap over pairs (2,000 draws, seed 20261108) for the lift. Needs at least 3 pairs.
- 95% interval entirely above zero: **flags track measured water.**
- Otherwise: **not shown.**
- Fewer than 3 pairs: **no verdict.**

**2. How much do flags disagree with measured water?** Report the share of flagged labelled pixels that are local dry. **Mostly above measured water** if pooled at least 80%, and **mostly below** if at most 20%. Otherwise **mixed**.

**3. Do flags follow the tributary's state?** Flagged share of mappable pixels at elevated against not-elevated gauges, as the mean across pairs and the Spearman rank correlation with rise. Descriptive, because of sample size. Withlacoochee's two passes share gauges, so they aren't independent.

**4. By river:** report all of this per river. Pee Dee supplies most pairs, so a pooled result may mostly describe one river.

No frozen score changes, whatever this finds.
