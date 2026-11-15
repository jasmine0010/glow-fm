# Blind-spot map

**What it answers:** where else could a flood be hidden from a satellite flood map, the way it was on the Satilla? It's a map of risk. It doesn't show flooding, and it doesn't use NISAR.

**Scripts:** `scripts/build_atlas.py`, `scripts/atlas_check.py`. **Data:** `blind_spot_atlas_check.json`, `app/data/atlas/summary.json`.

## Method

- **Floodplain:** Copernicus CEMS GloFAS 100-year flood hazard maps v2.1 (3 arc seconds, about 90 m), without permanent water or the depths the dataset flags as spurious.
- **Trees:** ESA WorldCover 2021 tree cover and mangroves, read from the 80 m overview of each 10 m tile.
- **Result:** the share of each 0.025° cell that is floodplain under trees, shown on the map as five classes.
- **Place check:** floodplain and the part under trees within about 25 km, from a 0.1° grid. High risk means at least 50% is under trees and that covers at least 100 km². Moderate means at least 20% and 25 km². Those cutoffs are ours and weren't calibrated. The area limits were added after Rio de Janeiro and Recife passed an earlier, share-only rule with little forested floodplain.

## Worldwide result

Mapped floodplain totals 12.5 million km², and 2.4 million km² of it (19%) is under trees, an area bigger than Greenland. Russia, Brazil, the US, Indonesia and Argentina hold the most.

Of the towns of 5,000+ people in GeoNames, 1,859 of 69,358 meet the high-risk rule. This says what ground lies within about 25 km. It doesn't say a town floods, and it isn't a count of people at risk.

## Does "floodplain under trees" match what GFM says it can't map?

Checked on floodplain pixels in every area where GFM's own exclusion masks are saved. A pixel counts as excluded if any saved scene excludes it.

| Area | Floodplain under trees | GFM excludes, under trees | GFM excludes, elsewhere | Share of GFM's exclusions under trees |
|---|---|---|---|---|
| Satilla, Georgia | 58% | 94% | 27% | 83% |
| Choctawhatchee and Yellow, Florida | 76% | 91% | 35% | 89% |
| Pearl, Louisiana and Mississippi | 63% | 96% | 33% | 83% |
| Tangipahoa, Louisiana | 50% | 95% | 29% | 77% |
| Tonle Sap, Cambodia | 20% | 69% | 9% | 66% |
| **All five** | | **92%** | **22%** | **79%** |

The stand-in holds up on these areas: trees predict GFM's exclusion well in all five, though less strongly in Cambodia.

## Limits

- **Not a random sample.** These five areas are where the project already had masks, four of them in the southeastern US. This check doesn't establish how well the stand-in works worldwide.
- **GFM isn't the only flood map.** The map is about tree cover hiding water, and other products have different gaps.
- **It misses other blind spots.** GFM also excludes ground that isn't under trees, 22% here, and this map doesn't show those places.
- **Modelled floodplains.** The hazard map is a model. It leaves out small streams and can be wrong, particularly where its documentation warns about very deep values.
- **A fixed picture.** Land cover is from 2021, and tree cover here says nothing about the season or how open a given canopy is.
- **No detection claim.** L-band radar like NISAR's can reach water under trees, but this project's method has only been tested on US rivers, with mixed results, and it failed its one test outside the US.

## What can be claimed

**Supported:** "About 2.4 million km² of the world's mapped river floodplains sit under trees. In the five areas we could check, Copernicus GFM's own mask excluded 92% of that kind of ground."

**Supported:** "About 1,900 towns, home to about 80 million people, sit beside large forested floodplains where satellite flood maps are likely blind." The number is the towns' own GeoNames population (city districts skipped, towns within 10 km merged, rounded to 5 million). It says who lives beside this ground, not who is at risk.

**Not supported:** that floods are being missed in all these places, that a listed town floods, that NISAR maps them, or any count of people at risk or affected.
