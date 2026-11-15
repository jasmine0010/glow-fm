# Third-storm screen: candidates for one frozen, held-out test

**Written using:** CMR catalog metadata, USGS gauge records, the NWS gauge report, the 3DEP product catalog and news.
**Not done:** no NISAR GCOV or GUNW file or browse image, and no GFM or OPERA DSWx layer, was opened or downloaded. No lidar elevation was fetched. No truth was computed, and no map was compared with anything.

Labels: **[O]** means observed in a record or catalog. **[I]** means inferred, from general knowledge or from reasoning on the observations.

## 1. Result

**Two candidates pass every criterion and were above NWS flood stage at the wet pass. Both come from Tropical Storm Edouard (landfall Sep 1, 2026) in the Big Thicket of East Texas.**

The recommended primary is **Village Creek, TX, track 134A frame 017, wet Sep 3 11:35 UTC, dry Aug 22**.

Six more ranked candidates pass the stated criteria, but their stage stayed below NWS flood stage at the wet pass. Much of their rise may have stayed in the channel. A corridor like that risks ending under the 500 ha "unjudgeable" floor from `V3_YELLOW_PROTOCOL.md` §5 **[I]**. A few weaker corridors also clear the 1 m bar on small rises and are noted but not ranked (§3.4).

Flood stage was not one of the stated criteria. It was added because a 1 m rise alone does not show the floodplain got wet: the Pee Dee rose 3.96 m and stayed below flood stage.

## 2. What was screened

| Step | Scope | Result |
|---|---|---|
| Storm list | News and NHC-derived reports for all nine named Atlantic storms through Isaias, plus remnants | **[O]** Only Arthur, Bertha, Edouard and Isaias are reported to have reached the US. Hurricane Polo (eastern Pacific) sent remnant moisture to the Southwest and Plains |
| Catalog | All `NISAR_L2_GCOV_PROVISIONAL_V1` granules over 24–50°N, 106–66°W | **[O]** 6,839 granules, 569 stacks. 5,643 have frequency A with HH and HV |
| First pass | USGS daily stage, 28 states; selection rule on 570 river-name clusters with at least 2 gauges | **[O]** 784 river and stack rows with more than 1 m rise, on 328 rivers |
| Flood-stage scan | Daily stage against the NWS all-gauges report, 1,908 gauges with a flood stage | **[O]** 444 gauge and window rows at or above flood stage |
| Second pass | 15-min stage (parameter 00065) for 167 main-channel gauges in 42 groups, with rule and timing on every same-track, same-frame stack | **[O]** Tables below |

**Three catalog facts differ from the brief or matter later [O]:**
- The PROVISIONAL collection lists granules from **Apr 1**, not only from Jun 17. No candidate below uses one.
- The Jul 27 to Aug 10 gap is confirmed, and the catalog ends Oct 23.
- 1,167 granules over this area have **no frequency A**, so the frozen method cannot use them. They were excluded.

## 3. Candidates that qualify

Selection was event-scoped: wet is the pass with the highest mean rise inside the event window, and dry is the lowest-mean pass within ±60 days. For Village Creek and Pine Island Bayou the same passes also win across the whole record on their stacks.

All pairs below use the same mode, `4005_DHDH` (40 MHz, HH and HV), as the Yellow scenes. All are full frame and PROVISIONAL.

### Ranked summary

| Rank | River | Storm | Track/frame | Wet / dry (UTC) | Gauges | Mean rise | Largest gauge rise | Stage against NWS flood stage at wet pass |
|---|---|---|---|---|---|---|---|---|
| **1** | **Village Creek, TX** | **Edouard** | **134A/017** | **Sep 3 11:35 / Aug 22 11:35** | 2 | 16.54 ft | 5.64 m | **Above, both gauges** |
| **2** | **Pine Island Bayou, TX** | **Edouard** | **012D/073** | **Sep 7 01:01 / Jul 9 01:01** | 2 | 12.53 ft | 4.71 m | **Above, both gauges** |
| 3 | Pee Dee, SC | July front | 098D/071 | Jul 27 00:10 / Jul 3 00:10 | 5 | 11.62 ft | 3.96 m | Below at the 2 gauges with a value |
| 4 | Neuse, NC | July front | 090A/019 | Jul 26 10:21 / Sep 12 10:21 | 4 | 7.19 ft | 2.98 m | Below at the 3 gauges with a value |
| 5 | Sabine lower, TX/LA | Mid-July rain | 134A/017 | Jul 17 11:35 / Aug 22 11:35 | 3 | 6.10 ft | 2.89 m | Below (Ruliff within 0.65 ft) |
| 6 | Tar, NC | July front | 090A/020 | Jul 26 10:22 / Jun 20 10:22 | 2 | 6.42 ft | 2.39 m | Well below |
| 7 | Trinity lower, TX | Edouard | 134A/017 | Sep 3 11:35 / Sep 15 11:35 | 4 | 4.46 ft | 2.68 m | Well below; crest had not reached the lower gauges |
| 8 | East Fork San Jacinto, TX | Mid-July rain | 113D/073 | Jul 16 01:10 / Aug 21 01:10 | 3 | 7.21 ft | 2.65 m | Below; one gauge record is suspect (§3.4) |

### 3.1 Rank 1: Village Creek, TX

| | Granule |
|---|---|
| **Wet** | `NISAR_L2_PR_GCOV_029_134_A_017_4005_DHDH_A_20260903T113542_20260903T113616_P05023_N_F_J_001` |
| **Dry** | `NISAR_L2_PR_GCOV_028_134_A_017_4005_DHDH_A_20260822T113542_20260822T113616_P05023_N_F_J_001` |
| Secondary wet (012D/073) | `NISAR_L2_PR_GCOV_030_012_D_073_4005_DHDH_A_20260907T010148_20260907T010222_P05023_N_F_J_001` |
| Secondary dry (012D/073) | `NISAR_L2_PR_GCOV_029_012_D_073_4005_DHDH_A_20260826T010148_20260826T010222_P05023_N_F_J_001` |

Primary pair, 134A/017 **[O]**:

| Gauge | ID | Datum (ft) | Wet (ft) | Dry (ft) | Rise | Crest (UTC) | Timing | Minor / moderate / major (ft) | Distance inside footprint, wet / dry |
|---|---|---|---|---|---|---|---|---|---|
| Village Mills, US 69 | 08041300 | NAVD88, 0.0 | 76.65 | 62.06 | 4.44 m | Sep 4 10:15 (77.16 ft) | Rising, 0.9 d before crest | 70 / 75 / 79 | 90.7 / 91.8 km |
| Kountze | 08041500 | NAVD88, 23.49 | 20.65 | 2.15 | 5.64 m | Sep 4 06:45 (22.50 ft) | Rising, 0.8 d before crest | 17 / 21 / 23 | 78.3 / 79.5 km |

Secondary pair, 012D/073, Sep 7 01:01 / Aug 26 01:01 **[O]**: mean rise 11.72 ft.
- Village Mills 71.37 against 62.00 ft, 2.85 m, receding 2.6 d after crest.
- Kountze 16.11 against 2.04 ft, 4.29 m, receding 2.8 d after crest.
- Kountze has dropped below minor flood stage by this pass.

Other passes on 134A/017 **[O]**, stage in ft at Village Mills and Kountze: Jun 23 65.97 and 8.76; Jul 17 70.80 and 11.65; Aug 10 62.60 and 2.47; Sep 15 64.14 and 5.13; Oct 9 62.89 and 3.53.

| Criterion | Result | Basis |
|---|---|---|
| (a) Gauges | **Pass** | **[O]** 2 gauges on one channel, 15-min spacing at both times, NAVD88 confirmed in the OGC record |
| (b) Pair | **Pass** | **[O]** Same track and frame, both PROVISIONAL, 12 days apart, rises 4.44 and 5.64 m |
| (c) Footprint | **Pass on polygon** | **[O]** UMM polygon contains both gauges and the whole line between them, at least 78 km inside on both dates. Valid radar over the reach cannot be checked without opening the file |
| (d) Timing | **Pass, best class** | **[O]** Both rising, within a day of crest |
| (e) Lidar | **Pass** | **[O]** 1 m DEM tiles at all 5 sample points on the line, project "TX Neches B1 2016" |
| (f) Forest | **Pass** | **[I]** Big Thicket National Preserve, Village Creek Corridor Unit; bottomland hardwood and cypress–tupelo. General knowledge, no land cover computed |
| (g) Independence | **Pass** | **[O]** Not in the Choctawhatchee, Yellow, Pearl or Tangipahoa basins. The rise is from Edouard |
| (h) Area | **Pass on the corridor measure** | **[O]** 15.6 km straight line × 8 km = 12,480 ha. **[I]** The valley floor is far narrower, perhaps 1–2.5 km, so flooded area may be a few thousand hectares |
| (i) Ledger | Partial | **[O]** GFM catalog items on Sep 1 and Sep 6. No DSWx-S1 granules from Aug 31 to Sep 6 |

**Edouard cross-check [O]:** search excerpts of the NWS Lake Charles post-tropical report say Village Creek crested at moderate flood stage at Kountze on Sep 4, and that the Neches and Pine Island Bayou were still above minor flood stage on Sep 6. The gauge record agrees. The PDF itself could not be decoded here, so this rests on the excerpts.

### 3.2 Rank 2: Pine Island Bayou, TX

| | Granule |
|---|---|
| **Wet** | `NISAR_L2_PR_GCOV_030_012_D_073_4005_DHDH_A_20260907T010148_20260907T010222_P05023_N_F_J_001` |
| **Dry** | `NISAR_L2_PR_GCOV_025_012_D_073_4005_DHDH_A_20260709T010150_20260709T010225_P05023_N_F_J_001` |

| Gauge | ID | Datum (ft) | Wet (ft) | Dry (ft) | Rise | Crest (UTC) | Timing | Minor / moderate (ft) | Distance inside footprint, wet / dry |
|---|---|---|---|---|---|---|---|---|---|
| Sour Lake | 08041700 | NAVD88, −1.50 | 27.67 | 12.21 | 4.71 m | Sep 6 21:30 (27.67 ft) | Near crest, +0.1 d | 25 / 29 | 46.0 / 50.7 km |
| Above BI Pump Plant, Beaumont | 08041749 | NAVD88, −0.84 | 11.15 | 1.55 | 2.93 m | Sep 7 04:30 (11.16 ft) | Near crest, −0.1 d | 11 / 14 | 57.6 / 62.3 km |

Secondary pair, 134A/017, the same Sep 3 and Aug 22 granules as rank 1 **[O]**: mean rise 7.11 ft. Rises are 3.07 and 1.27 m, both rising about 3 d before crest.

| Criterion | Result | Basis |
|---|---|---|
| (a) | **Pass** | **[O]** 2 gauges, 15-min spacing at both times, NAVD88 confirmed |
| (b) | **Pass** | **[O]** Rises 4.71 and 2.93 m. Dry is exactly 60 days before wet, the edge of the window, as with the Yellow primary |
| (c) | **Pass on polygon** | **[O]** Line inside by at least 46 km on both dates. Valid radar not checkable |
| (d) | **Pass, best class** | **[O]** Both at crest, within 0.1 d |
| (e) | **Pass** | **[O]** 1 m DEM at all 5 sample points: TX Neches B1 2016 and TX_Houston |
| (f) | **Pass** | **[I]** Big Thicket corridor and Lance Rosier units, with some urban edge near Beaumont |
| (g) | **Pass** | **[O]** Edouard. No overlap with used rivers |
| (h) | **Pass on the corridor measure** | **[O]** 16.2 km × 8 km = 12,949 ha |
| (i) | Partial | **[O]** GFM on Sep 6 and Sep 8. No DSWx-S1 from Sep 4 to Sep 10 |

**Limit specific to this corridor [I]:** the lower gauge sits on a bayou with a pump plant, backwater from the Neches and possible tidal influence. It may not act like a free-flowing channel.

### 3.3 Ranks 3 and 4: July front

The rain came from a slow-moving cold front stalled over the Carolinas, under Flood Watches from Jul 22 to 24 **[O: NWS Raleigh and NCEM excerpts]**. Bertha was over the northern Gulf and moving west at that time **[O]**. Attribution to the front is **[I]**: no post-event summary was found, and one local report mentions remnant moisture feeding the front. It is neither Arthur nor Isaias.

**Rank 3, Pee Dee, track 098D frame 071 [O]**
- Wet: `NISAR_L2_PR_GCOV_026_098_D_071_4005_DHDH_A_20260727T001045_20260727T001120_P05023_N_F_J_001`
- Dry: `NISAR_L2_PR_GCOV_024_098_D_071_4005_DHDH_A_20260703T001046_20260703T001121_P05023_N_F_J_001`

| Gauge | ID | Datum (ft) | Wet / dry (ft) | Rise | Timing | Minor flood stage (ft) |
|---|---|---|---|---|---|---|
| Cheraw | 02130000 | NAVD88, 56.02 | 11.97 / 2.42 | 2.91 m | Receding, 1.6 d | 30 |
| Near Bennettsville | 02130561 | NAVD88, −0.94 | 64.72 / 52.37 | 3.76 m | Near crest, 1.4 d | None listed |
| Peedee | 02131000 | NAVD88, 23.54 | 15.02 / 2.08 | 3.94 m | Rising, −0.5 d | 19 |
| Below Pee Dee | 02131010 | NAVD88, 14.29 | 22.78 / 9.77 | 3.96 m | Rising, −0.6 d | None listed |
| US 378 above Poston | 02131210 | NAVD88, 1.88 | 16.58 / 6.29 | 3.14 m | Rising, −1.7 d | None listed |

Criteria:
- (a) pass, (b) pass, (d) pass.
- (c) pass on polygon: line at least 32.5 km inside on both dates.
- (e) pass: SC_SavannahPeeDee_2019 at all 21 sample points.
- (f) pass **[I]**: floodplain hardwood and cypress–tupelo along most of the reach, with farmland on the terraces.
- (g) pass, with no overlap.
- (h) pass: 59 km supported × 8 km = 47,265 ha.
- (i) partial: GFM on Jul 25, 27 and 29; no DSWx-S1.

**Main weakness [O]:** the Cheraw crest of 15.28 ft is below even the action stage of 20 ft, and the Peedee crest of 15.20 ft is below the action stage of 18 ft. **[I]** The river is also regulated upstream by the Yadkin–Pee Dee dams. This corridor has the best gauge support but may be mostly in-bank.

**Rank 4, Neuse, track 090A frame 019 [O]**
- Wet: `NISAR_L2_PR_GCOV_026_090_A_019_4005_DHDH_A_20260726T102153_20260726T102230_P05023_N_F_J_001`
- Dry: `NISAR_L2_PR_GCOV_030_090_A_019_4005_DHDH_A_20260912T102151_20260912T102229_P05023_N_F_J_001`

| Gauge | ID | Datum (ft) | Wet / dry (ft) | Rise | Timing | Minor flood stage (ft) |
|---|---|---|---|---|---|---|
| Near Cox Mill | 02088119 | NAVD88, 0.0 | 79.12 / 69.34 | 2.98 m | Rising, −1.2 d | None listed |
| Near Goldsboro | 02089000 | NAVD88, 41.9 | 11.82 / 2.53 | 2.83 m | Rising, −2.4 d | 18 |
| Kinston | 02089500 | NAVD88, 9.7 | 8.96 / 2.79 | 1.88 m | Rising, −3.0 d | 14 |
| Near Fort Barnwell | 02091814 | NAVD88, −1.4 | 5.54 / 2.04 | 1.07 m | Rising, −3.0 d | 13 |

Corridor at least 17.7 km inside the footprint; 46,785 ha; lidar NC_HurricaneFlorence_2020 at all sample points; GFM on Jul 27; no DSWx-S1.

**Footprint catch [O]:** Smithfield (02087570) is **outside** the Jul 26 polygon although it is inside the Jul 2 and Jul 14 polygons, because the frame edge moves between cycles. This is the failure the brief warned about, so the corridor starts at Cox Mill. The Cox Mill record only starts Jul 15, which limits the dry choice to later passes.

### 3.4 Ranks 5 to 8

All four pass the stated criteria but are weaker.

| Rank | River, gauges (datum) | Wet granule | Dry granule | Rises and timing | Footprint | Weakness |
|---|---|---|---|---|---|---|
| 5 | Sabine lower: 08026000 (NAVD88), 08028500 (NGVD29), 08030500 (NAVD88) | `NISAR_L2_PR_GCOV_025_134_A_017_4005_DHDH_A_20260717T113544_20260717T113618_P05023_N_F_J_001` | `NISAR_L2_PR_GCOV_028_134_A_017_4005_DHDH_A_20260822T113542_20260822T113616_P05023_N_F_J_001` | 1.32 m and 1.37 m receding 2.3 d; 2.89 m near crest | Gauges at least 15.6 km inside; corridor line not separately sampled | Regulated by Toledo Bend **[I]**. Cause of the mid-July rain not established. Below flood stage (23.35 against 24 ft at Ruliff) |
| 6 | Tar: 02082585, 02083500 (NAVD88) | `NISAR_L2_PR_GCOV_026_090_A_020_4005_DHDH_A_20260726T102229_20260726T102304_P05023_N_F_J_001` | `NISAR_L2_PR_GCOV_023_090_A_020_4005_DHDH_A_20260620T102231_20260620T102306_P05023_N_F_J_001` | 1.52 m and 2.39 m, near crest | Line at least 31.7 km inside | Tarboro 9.11 against flood stage 19 ft. Forest is mixed with farmland **[I]** |
| 7 | Trinity lower: 08066250 (NGVD29), 08066500, 08067000, 08067100 (NAVD88) | `NISAR_L2_PR_GCOV_029_134_A_017_4005_DHDH_A_20260903T113542_20260903T113616_P05023_N_F_J_001` | `NISAR_L2_PR_GCOV_030_134_A_017_4005_DHDH_A_20260915T113541_20260915T113616_P05023_N_F_J_001` | 2.68, 2.11, 0.50, 0.15 m; near crest to rising | Line at least 43.5 km inside | The crest had not reached Liberty or Moss Bluff at this pass. Romayor crest 19.92 against flood stage 40 ft |
| 8 | East Fork San Jacinto: 08069800, 08070000, 08070200 (NAVD88) | `NISAR_L2_PR_GCOV_025_113_D_073_4005_DHDH_A_20260716T011009_20260716T011044_P05023_N_F_J_001` | `NISAR_L2_PR_GCOV_028_113_D_073_4005_DHDH_A_20260821T011007_20260821T011042_P05023_N_F_J_001` | 2.65, 1.65, 2.29 m; near crest to rising | Line at least 10.2 km inside | The 08069800 record starts Jul 6 and repeats 197.30 ft on many dates, so it may be a floor or stale value. Cleveland 9.71 against flood stage 19 ft |

Sabine lower also has 1 m DEM at all 9 sample points (LA_Sabine_River_Lidar_2018) and about 32,000 ha of corridor **[O]**.

**Clear the 1 m bar but are not ranked [O]:** mean rise is small and stage is far below flood stage, and full criteria were not worked up.
- Congaree: 119A/019, Sep 26, 1.31 m, near crest. Columbia 3.8 against 19 ft. Forest is strong here **[I]**, but the rise is small.
- Waccamaw: 018A/019, Sep 7, 1.62 m on one gauge.
- Cape Fear: 090A/019, Jul 26, 1.71 m on one gauge.
- West Fork San Jacinto: 113D/073, Jul 16, up to 2.68 m. Below Lake Conroe, with suburban land **[I]**.
- Angelina: 012D/073, Jul 21, 1.18 m.
- Savannah: passes above 1 m rest on one gauge, with mean rise at most 1.6 ft.

## 4. Near misses

The "Fails or weakness" column includes flood stage and product mode, which are additions to the stated criteria.

| River | Event | Best pair (UTC) | Fails or weakness | Numbers **[O]** unless marked |
|---|---|---|---|---|
| **Wabash, Covington to Terre Haute** | Mid-Aug rain, cause not established | 084D/068, Aug 19 00:50 / Jul 26. `..._028_084_D_068_2005_QPDH_..._20260819T005040...` | **Mode, and (f)** | Rises 5.84, 6.69, 5.87 m, all above minor flood stage. Product is **20 MHz** (`2005_QPDH`). `io/nisar.py` needs an integer ratio of the 50 m grid to source spacing, so a 20 m product would stop the frozen reader **[I]**. Floodplain is largely cropland with forest strips **[I]** |
| Wabash, Riverton to New Harmony | Same | 156D/069, Aug 24 00:42 / Oct 23 | Mode, and (f) partly | Rises 3.75–5.01 m, 20 MHz. Lower Wabash has more bottomland forest **[I]** |
| Little Wabash | Same | 076A/021, Aug 18 11:04 / Sep 11 | Mode; below flood stage | Rises 1.39, 2.60, 2.46 m, 20 MHz |
| Meramec, Patoka, White (IN), Vermilion, Spoon | July to August rain | Various | Mode | Daily stage only. All 20 MHz **[O]**; several above flood stage |
| **Grand River, MO** | Polo remnants | 041D/068, Oct 3 / Sep 9, 40 MHz | **(f)** | About 7.3–7.4 m rises at 3 gauges at crest, above flood stage (daily stage). Cropland floodplain **[I]** |
| Platte (MO), Missouri, Big Blue, Kansas | Polo remnants | Various | (f) | Large rises, agricultural valleys **[I]** |
| Trinity, Cayuga to Crockett | Polo remnants | 062A/017, Oct 4 11:44 / Sep 10. `..._032_062_A_017_4005_DHDH_A_20261004T114401...` | **(c)**; below flood stage | Rises 6.79, 4.10, 0.71 m. Cayuga (08064570) is only **3.2 km** inside the wet polygon, so a 4 km corridor is clipped. Oakwood 16.83 against 35 ft |
| Trinity, Rosser to Trinidad | Polo remnants | 062A/018, Oct 4 11:44 / Sep 10 | (f) uncertain; (e) not queried | Rises 0.92, 2.58, 5.52 m, near crest. Trinidad 25.26 against 33 ft. Mixed forest and pasture **[I]** |
| **St Marys, FL/GA** | Unnamed rain before Isaias | 098D/073, Oct 7 00:11 / Aug 20 | **Weak second gauge; just below flood stage** | Macclenny 2.90 m, near crest, 11.82 against 12 ft. Moniac only 0.81 m. Passes the rule on one gauge. Cause not established |
| **Satilla, GA** | Rain before Isaias, then Isaias period | Before: 098D/073, Oct 7 / Sep 25. After: 047A/017, Oct 15 / Oct 3 | **(g) on the higher pass** | Oct 7 rises 2.03, 1.11, 0.93 m, below flood stage. Oct 15 rises 3.34, 3.15, 2.87 m, about at flood stage, but that crest overlaps Isaias **[I]** |
| Roanoke, Halifax to Scotland Neck | Reservoir release **[I]** | 090A/020, Jul 14 10:22 / Aug 31 | **Not a storm; below flood stage** | Rises 2.28 and 2.46 m, then 0.22 m at Hamilton. Scotland Neck 13.20 against 28 ft |
| Cache, AR | Sep rain | 105A/019, Sep 13 11:20 / Oct 19 | **(a) in effect, (d) at one gauge** | Egypt 4.24 m near crest. Cotton Plant 0.52 m, 10 days past its crest. Gauges 97 km apart. No flood stage listed |
| Neches, Town Bluff to Beaumont | Edouard | 134A/017, Sep 3 / Sep 27 | Below flood stage; regulated | 2.73 m only at the dam tailwater; 0.45 and −0.18 m downstream |
| Menard Creek, TX | Edouard | None usable | **(a)** | 26.93 ft on Sep 3, above moderate. One gauge only |
| Central Texas: Guadalupe, Nueces, Frio, Llano, Medina, San Antonio | Mid-July flood | Various | **(f)** | Many above flood stage. Brush and narrow riparian forest **[I]** |
| White lower, AR | July rain | 012D/070, Jul 9 / Aug 26 | Below flood stage; receding 5+ days | Rises 2.93 and 2.81 m. Newport 11.82 against 26 ft |

### Failed because of Arthur or Isaias (criterion g)

**Arthur period, Jun 17 to Jul 5.** Arthur made landfall on the Texas coast on Jun 17 (reports differ on the exact spot) and moved over Louisiana and Mississippi, with flooding reported from Texas to Alabama and forecast to reach Georgia and the Florida Panhandle **[O]**. June rises in that area cannot be separated from it **[I]**, including rivers that look strong:
- Trinity at Crockett and Midway: 134A/017, Jun 23, rises 6.76 and 5.04 m, near crest. Crockett 24.11 ft against flood stage 41 ft, so still below flood stage.
- Altamaha, 026D/072, Jun 28, 1.80 and 2.14 m. Ogeechee, Satilla, Apalachicola, Flint.
- Pascagoula, Leaf, Chickasawhay, Tombigbee, Conecuh, Big Black.
- Neches, Sabine, Ouachita, Red, Sulphur, White, Little Wabash and Navasota.

Some of the northern and western rivers may have had separate rain, such as the Trinity at Dallas, cresting Jun 20. No source separates them, so they are not cleared.

**Isaias period, Oct 10 onward.** Landfall was near Destin on Oct 9–10 **[O]**. Rises after that across the Southeast are taken as Isaias **[I]**: Suwannee, Withlacoochee, Alapaha, Ochlockonee, Apalachicola, Ogeechee, Yadkin, Broad, Catawba, and the Pee Dee's second rise (098D/071, Oct 19, up to 2.57 m).

### Rivers named in the brief

| River | Outcome |
|---|---|
| Altamaha, Ogeechee, Pascagoula, Apalachicola, Suwannee | Only Arthur-period or Isaias-period rises reach the bar |
| Savannah | Weak: passes above 1 m rest on one gauge, mean rise at most 1.6 ft, below flood stage |
| Pee Dee, Neuse | Qualify, below flood stage (§3.3) |
| Santee | No pass with more than 1 m at any of the three main-channel gauges |
| Congaree | Weak: best 1.31 m on Sep 26, far below flood stage. Its largest rise, about Aug 9 in daily stage, falls in the data gap |
| Roanoke | Near miss |
| Mobile/Tensaw | Few usable gauges. Lower Alabama 1.34 m on Jul 25, well below flood stage. Tombigbee rise is Arthur period |
| Sabine | Rank 5 |
| Neches | Near miss; Village Creek and Pine Island Bayou are its tributaries |
| Trinity | Rank 7 and near misses |
| Ouachita | Arthur period only (late June); nothing above 1 m afterward with two gauges in frame |
| Cache, White | Near misses |
| Wabash | Near miss on mode and forest |
| Lower Mississippi tributaries | Big Black, Yazoo basin and Sunflower: Arthur period only |

## 5. What could not be checked

- **Valid radar over the corridor.** UMM polygons are four-corner outlines. Grid limits and valid pixels are only in the HDF5 files, which were not opened. A later pre-run check should confirm them from metadata, as was done for Yellow.
- **Projection.** Village Creek is near 94.3°W, so probably EPSG:32615 **[I]**. The Pearl projection error shows this needs confirming from the file.
- **Whether water actually left the channel.** NWS flood stage is a proxy for overbank flow, not truth. NWS and USGS stage are assumed to share a datum. That fails at some gauges: Altamaha near Baxley lists flood stage 74.5 ft against a USGS stage near 9 ft, and Goodrich may also differ. Village Creek and Pine Island Bayou crest values match the NWS report's description.
- **Land cover.** Criterion (f) rests on general knowledge. No land-cover layer was read.
- **3DEP.** Checked by catalog at sample points along straight gauge-to-gauge lines, not across the full 8 km width. Not queried for the Trinity upper or St Marys corridors, or the Satilla.
- **Corridor length.** Straight-line, so it understates valley length. Area is corridor area, not expected flooded area.
- **Rain at the wet pass [I].** Edouard's rain was still falling in the region on Sep 3. The primary pass is 06:35 CDT that day, so wet soil and canopy may raise ΔHH outside flooded areas. The Sep 7 passes are later, after the rain ended.
- **Screening gaps [O].**
  - Virginia and West Virginia returned no daily stage series, so the Chowan, Nottoway, Meherrin and James were not screened. The lower Roanoke was checked with 15-min stage.
  - 1,167 of the 3,623 daily-stage gauges had no NWS match, and 548 more had no flood stage.
  - Gauges with no daily stage series are missing from the first pass unless they were in a named group.
  - River clusters come from gauge names and may miss or split channels.
  - Gauges 07077500 and 02081022 returned no 15-min record.
- **Attribution.** Causes of the mid-July, mid-August and early-October rain were not established from sources. "Cause not established" means that.
- **Later floods.** The catalog ends Oct 23.

## 6. Decisions to fix before reading any pixel

These are suggestions **[I]**:
1. **Primary:** Village Creek, 134A/017, Sep 3 / Aug 22. **Secondary:** 012D/073, Sep 7 / Aug 26, following the rule in `SECOND_EVENT_PROTOCOL.md` §2a.
2. **Whether to add Pine Island Bayou.** Both corridors lie in both scenes, but each has its own rule-selected dry pass on 012D. Adding it reduces the risk of too little confirmed flooding on Village Creek alone. It should be decided now, not after seeing either result.
3. **Do not repeat "new storm" as independence.** Edouard is one storm over one forest type. Arthur also raised Village Creek in June, though that pass is not used.

## Sources

Gauge, catalog and flood-stage records:
- [USGS Water Services](https://waterservices.usgs.gov/) and [USGS Water Data OGC API](https://api.waterdata.usgs.gov/ogcapi/v0/)
- [NASA CMR](https://cmr.earthdata.nasa.gov/search/), catalog metadata only
- [NWS all-gauges report](https://water.noaa.gov/resources/downloads/reports/nwps_all_gauges_report.csv)
- [USGS TNM product catalog](https://tnmaccess.nationalmap.gov/api/v1/products), catalog only
- [EODC STAC](https://stac.eodc.eu/api/v1/search), catalog only

Events:
- [NWS Lake Charles post-tropical report, Edouard](https://www.weather.gov/media/lch/TropicalEventSummary/PSHLCH_2026AL05_Edouard_Summary.pdf), read through search excerpts
- [Edouard flood threat wanes after 20 inches on East Texas](https://www.news8000.com/weather/weather_news/edouard-s-flood-threat-finally-wanes-after-dumping-20-inches-on-east-texas/article_889e93df-afc6-59b0-ac14-0e77ddf42681.html)
- [Edouard landfall, Fox](https://www.fox32chicago.com/weather/tropical-storm-edouard-houston-texas-2026.amp)
- [NWS Davenport, Sep 30 to Oct 1 flooding, Polo remnants](https://www.weather.gov/dvn/summary_EndSept_HeavyRain)
- [NWS Omaha, Sep 30 flooding](https://www.weather.gov/oax/sep302026)
- [NWS Northern Indiana, mid-September flooding](https://www.weather.gov/iwx/20260916_Flooding)
- [Polo remnants in the Southwest, AJC](https://www.ajc.com/news/2026/09/hurricane-polos-remnants-bringing-more-rain-to-flood-struck-us-southwest/)
- [Bertha, Water ISAC](https://www.waterisac.org/?p=66496)
- [Hanna, KBTX](https://www.kbtx.com/2026/09/28/tropical-storm-hanna-has-formed-central-atlantic/)
- [Gonzalo, KBTX](https://www.kbtx.com/2026/09/25/tropical-storm-gonzalo-has-formed-off-coast-africa/)
- [Neuse River flood warning, Jul 24](https://defconlevel.com/alert/2026-07-25-nws-noaa-weather-flood-warning-issued-july-24-at-10-41pm-edt-until-july-25-at-8-00pm-edt-by-nws-raleigh-nc)
- [Arthur landfall on the Texas coast](https://www.mysuncoast.com/2026/06/17/tropical-storm-arthur-makes-landfall-texas-coast/)
- [Arthur, flooding from Texas to Alabama](https://www.wataugademocrat.com/news/state/arthur-hammers-louisiana-flood-threat-persists-along-gulf-coast/article_841cf9b0-d647-5a63-82ef-aba67c62faf9.html)
- [Isaias, first hurricane of the season](https://www.kuow.org/npr-news/2026-10-07/isaias-strengthens-into-the-first-hurricane-of-the-atlantic-season)
