# Independent check against optical imagery

**Written** before any reflectance or aerial image over these points was opened. Only catalog metadata, cloud-mask classes, tile availability and gauge levels were used to choose scenes.

**Weaker record:** this file's hash is recorded in the results, but it was not in a commit before the run, so its timing is self-attested.

**Question:** the method's scores all compare radar with a gauge-and-lidar estimate. Does imagery that uses no radar, gauges or lidar agree with (a) the estimate, and (b) radar flags, including flags beyond the estimate's 4 km corridor?

## What this can't do

Optical imagery can't see water under closed canopy. Most test ground is forest, so most points may be undecidable. Decidable points are biased toward open ground and canopy gaps. **This check can't validate mapping under closed canopy.** It tests the parts that imagery can see.

## Cases, chosen from metadata

| Case | Radar | Map | Imagery | Why |
|---|---|---|---|---|
| Satilla, strong | Oct 15 10:45 UTC, CSI 0.73, held out | v4 | Sentinel-2 L2A, Oct 14 16:14 UTC | 18.5 h before radar, 0% scene cloud, gauges within 0.09 m |
| Lower Sabine, failed | Jul 17 11:35 UTC, CSI 0.05, held out | v4 | Sentinel-2 L2A, Jul 16 and Jul 18 17:05 UTC, the nearer clear scene per point | Same sensor as the Satilla. Pee Dee's clear Landsat came after gauges fell up to 2.9 m, and Neuse is 7% clear over flagged ground |
| Lower Yellow, strong, aerial | Oct 16 00:36 UTC, CSI 0.88, frozen v3 | v3 | NOAA Hurricane Isaias aerial mosaics, Oct 11–12 | The only tested flood NOAA flew. River-level gaps are stated below |

**Yellow timing:** the flights came 4–5 days before radar. At Milton, the gauge nearest the flown reach, stage was about 0.5–0.6 m lower at the flights than at radar. Water seen is therefore likely still present at radar, while no visible water doesn't refute a radar flag. It isn't a held-out comparison for scene choice, because the storm also helped develop later methods. The case is secondary.

**Before scenes:** the latest Sentinel-2 scene per tile with at most 10% scene cloud, ending before the rise: Sep 14, 2026 for the Satilla, and on or before Jul 10, 2026 for the Lower Sabine. For Yellow, the "usual" panel is the undated Esri World Imagery mosaic.

## Points

**Sentinel-2 cases:** within scored ground (`region & mapped`), seven strata, 25 points each.

| Stratum | Definition |
|---|---|
| A flagged, estimate wet | flagged and labelled flooded |
| B flagged, estimate dry | flagged and labelled dry |
| C flagged, near water line | flagged, inside the corridor, without a label |
| D flagged, beyond corridor | flagged, outside the corridor |
| E not flagged, estimate wet | not flagged and labelled flooded |
| F not flagged, estimate dry | not flagged and labelled dry |
| G not flagged, beyond corridor | not flagged, outside the corridor, land cover the method allows, under 6 m above the river. The control for D |

**Yellow:** the same strata, 20 points each, inside flown tiles.

**Sampling:** random order with seed 20261106, accepting a point only if it is at least 300 m from accepted points in its stratum, cloud classes are clear in both scenes (Sentinel-2) or the flown tile has data (Yellow). If a stratum has too few points, all are used and the shortfall is reported.

## Blind review

- Points from all rivers and strata are shuffled, with random IDs. Reviewers see no river, date, stratum, radar, estimate or hypothesis.
- **Two independent reviewers** classify the marked 50 m box in each chip. They don't see each other's answers. Reviewers are AI vision agents, not trained photo-interpreters, which is a real limit.
- **Classes:** `FLOOD` water or flooded ground visible in the event panel and not the before panel, `PERMANENT` water in both, `DRY` ground or vegetation clearly without water, `CANOPY` tree crowns hide the ground, `CLOUD` cloud, shadow or no data, `UNSURE`.
- **Consensus:** both reviewers must agree. Disagreements count as `UNSURE`, with no tie-break. Agreement is reported with Cohen's kappa.

**Decidable** means consensus `FLOOD`, `PERMANENT` or `DRY`. **Flood share** is `FLOOD` over decidable points. Wilson 95% intervals are descriptive.

**Automatic second measure, Sentinel-2 only:** a point counts as new water if at least half of the box's pixels have MNDWI above 0 in the event scene, and fewer than half do in the before scene.

## Fixed readings

A stratum with fewer than 10 decidable points gives **no claim**. Comparisons need at least 10 decidable points on each side, and pool strata as stated.

1. **Does imagery support the estimate?** Flood share of estimate-wet (A + E) against estimate-dry (B + F). **Supported** if the 95% interval for the difference (Newcombe) is entirely above zero.
2. **Do radar flags beyond the corridor carry flood information?** D against G. **Supported** if the interval is entirely above zero. This is the main question.
3. **Does radar add anything to the estimate where imagery can see?** Within estimate-wet, A against E. Descriptive, because of sample size.
4. **Strong against failed:** report readings 1 and 2 side by side. **The expected pattern** is reading 2 supported on the Satilla and not on the Lower Sabine. Anything else is reported as found.

If a comparison lacks points, the reading is **imagery can't decide**, and that is a valid result. No frozen score changes, whatever this finds. Failing to find visible water under trees doesn't refute radar.
