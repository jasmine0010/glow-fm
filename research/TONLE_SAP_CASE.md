# Tonle Sap case: rules written before reading any radar

**Written** before any NISAR backscatter, GFM flood layer, Copernicus elevation or land cover over this area was opened. Only catalog metadata and each scene's projection, spacing and valid-sample mask were read.

**This is an unvalidated demonstration and not a frozen test.** There are no gauges or lidar in this analysis, so nothing here is scored. The predictions below can show that the signal behaves like a seasonal flood. They can't show that the map is accurate. The rules are not yet in a commit, so the dated record is weaker than for the frozen tests. The run records this file's hash.

**Why here:** the challenge asks for "locations around the world" and for the "patterns and rhythms" of Earth's surface. Tonle Sap in Cambodia is a large lake that typically swells through the wet season, flooding the forest and shrubland around it.

## Fixed now

**Study box:** 103.35–104.35°E, 12.75–13.40°N, covering Prek Toal and the northwest lake margin. It was chosen for its ecology, using scene coverage only.

**Scenes:** track 083A, frame 008, mode 2005_DHDH, on 2026-06-19, 07-01, 07-13, 07-25, 08-18, 08-30, 09-11, 09-23, 10-05 and 10-17. These have HH and HV at 20 m spacing, and the mid-record scene has 100% valid samples over Prek Toal. The earlier 40 MHz scenes don't reach this area.

**Grid:** 60 m, because 20 m pixels fit it exactly. Every frozen test used 40 MHz data on a 50 m grid, so this mode and grid have not been tested.

**Method:** the hashed v4 rule with no parameter changed, except for what this place makes impossible:

| Part of v4 | Here | Why |
|---|---|---|
| Baseline: median of scenes within 60 days | **Median of the first three scenes (Jun 19, Jul 1, Jul 13)** | A flood lasting months would be compared with itself, hiding it |
| Height above the river, from lidar | From Copernicus GLO-30, above the lake | No lidar here |
| Valley line through gauges | Distance from the lake, and position along the lake's long axis | No gauges here. The lake is the largest connected body in GFM's reference water |
| Late-recession rule, from gauges | Not applied | No gauges here |

**Maps shown:** the v4 map and the raw HH change for each of the seven later passes.

## Expected to under-map

- **The height limit:** v4 only maps ground under 6 m above the water. Copernicus includes tree height, and on the Satilla this limit cost about half of recall (`NO_LIDAR_RESULTS.md`). This lake's seasonal rise could also exceed the limit.
- **Land cover:** v4 leaves out WorldCover's shrub, grass and crop classes, and much of this floodplain may fall in them.
- **The baseline:** NISAR's record starts in June, so flooding already there by mid-July counts as no change.

So the raw change and the seasonal numbers below may say more than the map's area. No limit, class or threshold will be changed after seeing the data, and any further analysis will be labelled post-hoc.

## Predictions, fixed now

Zones use WorldCover tree cover. Distances are from the lake. Change is from the baseline, in dB.

| # | Prediction | Why |
|---|---|---|
| 1 | Median HH change in tree cover within 15 km of the lake reaches its highest value on Sep 11 or later | The lake typically peaks around September to October |
| 2 | On that peak date, HH change exceeds HV change by at least 1 dB in that zone | The double-bounce pattern: water and trunks boost HH more than HV |
| 3 | Tree cover at least 30 km from the lake changes by less than 1 dB in HH on every date | A control. Forest beyond the flood's reach shouldn't follow it |
| 4 | Across the seven dates, tree cover within 30 km with HH change above 2 dB rises with the water area GFM maps in the box, with a rank correlation of at least 0.6 | GFM is an independent record of water, using a different satellite and method |

**Reading:** if all four hold, the signal **behaves like a seasonal flood**. If some fail, the write-up says which and what that suggests. Neither outcome validates the map.

**GFM dates:** for each NISAR date, the nearest GFM date within 3 days that covers at least 90% of the box. A date with none is left out of prediction 4, and fewer than five usable dates means no reading for it.

## Limits stated now

- **Nothing here is scored.** No map accuracy can be claimed.
- **Seven dates from one season at one place, and they aren't independent.** Rainy-season changes in leaves and soil moisture also change backscatter, which is why prediction 3 exists. Local forest near the lake could still differ from forest far from it.
- **GFM isn't truth.** It maps open water, and it is known to miss water under trees, which is the point of this project. So prediction 4 only compares timing.
- **Human activity:** fishing villages, rice fields and reservoirs in this area can all change backscatter. None were separated out.
