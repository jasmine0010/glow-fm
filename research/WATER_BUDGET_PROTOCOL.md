# Hidden water budget: does the river's own flow agree with the estimated water on the floodplain?

**Written** before any storage was compared with any river flow. Seen so far: one rough Satilla volume on one date (about 40 million m³), its peak flows, drainage areas, and which gauges report discharge.

**Weaker record:** this file's hash is recorded in the results, but it was not in a commit before the run. The run happens once, and the script refuses to overwrite its results.

**Question:** the estimate says how much water sits on a floodplain, from gauges and lidar. River flow gives a separate account: if more water enters a reach than leaves, the difference is being stored. Do they agree?

## Why this is a useful test

Every earlier score compares maps with an estimate built on lidar. Discharge is measured separately from lidar, so it can challenge the estimate's *amount and timing*. It shares the gauge sites, and USGS discharge usually comes from stage through a rating curve, so it isn't fully independent of the gauges. It also says nothing about radar directly.

## Two storage records, per reach

A reach is the valley between two consecutive gauges that report discharge.

**Estimated storage** uses the frozen estimate's logic through time. Every 6 hours, water surface is interpolated between all of that river's gauges with stage and compared with lidar. Ground counts if depth is above 0.5 m and it connects to reference water through ground below the water. Permanent water is excluded. Storage is the depth summed over counted pixels inside the corridor between the two gauges, without the 10 km gauge limit, so it covers the whole reach.

**Flow storage** uses no lidar:

- Expected outflow = upstream discharge, delayed by the reach's travel time, × downstream drainage area / upstream drainage area. The area ratio is a rough stand-in for ungauged inflow.
- Travel time is the delay from 0 to 240 hours that best correlates upstream with downstream discharge in the window. It uses discharge only.
- Flow storage is the running total of expected minus measured outflow. The mean difference over the window's first 3 days is subtracted, so a steady mismatch doesn't accumulate. The total starts at zero.

**Window:** 20 days before to 25 days after each river's reference pass, or to the latest available reading.

| River | Reference pass |
|---|---|
| Satilla | Oct 15 | 
| Ochlockonee | Oct 14 |
| St Marys | Oct 7 |
| Pee Dee | Jul 27 |
| Neuse | Jul 26 |
| Lower Sabine | Jul 17 |
| Yellow | Oct 16 |
| Choctawhatchee | Oct 17 |
| Pearl | Jul 3 |
| Tangipahoa | Jun 21 |
| Pine Island Bayou | Sep 7 |
| Village Creek | Sep 3 |

**Which reaches are judged:** both gauges have drainage areas, discharge covers at least 90% of the window's hours, at most 40% of the downstream drainage area is ungauged, and peak estimated flooding in the reach is at least 500 ha. Others are reported without a verdict. Reaches under 500 ha also serve as a descriptive check on whether flow storage stays small when the estimate says little flooded.

## Fixed readings

A judged reach is **consistent** only if all three hold:

1. **Amount:** peak flow storage divided by peak estimated storage is between 1/3 and 3. The range is wide because rating curves, the area ratio and rain all carry large errors.
2. **Timing:** the two peaks are within 3 days.
3. **Shape:** the Spearman rank correlation of the two records is at least 0.6.

Otherwise it is **inconsistent**. Each reach's failed conditions are reported.

**Overall:** consistent on at least two-thirds of judged reaches, **supported**. On at most one-third, **not supported**. Otherwise **mixed**. Fewer than 3 judged reaches gives **no verdict**. Reaches on one river and storm aren't independent, so the count is descriptive.

**Satilla, the headline river,** is reported on its own, reach by reach, whatever the overall result. If no Satilla reach qualifies, no discharge support is claimed for its headline volume.

## The volume range

For the public number, the Satilla's volume on Oct 15 is computed on ground within 10 km of a gauge, as the site's estimate does, with the water surface unchanged and shifted by −0.5 m and +0.5 m. A hidden-gauge error of about 1 m is possible over long gaps, so this range isn't a limit on the error. The comparison with peak flow is only for scale.

## Expected biases, stated first

- **Flow storage should tend to run higher.** It includes rising water in the channel, shallow water under the 0.5 m margin, and water outside the corridor. Estimated storage doesn't.
- **Rain and ungauged tributaries** can arrive unevenly, and the area ratio will misplace them.
- **Rating curves** are least certain out of bank, and these provisional USGS records may later be revised.
- **Dams and backwater** can break the balance, including tidal effects near a coast.

No frozen score changes, whatever this finds. Agreement wouldn't validate the estimate's *location* of water, only its broad amount and timing. It wouldn't validate radar.
