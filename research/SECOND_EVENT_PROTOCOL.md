# Second-event protocol (held-out test of the frozen method)

**Written** before any NISAR imagery, browse image, operational flood map or truth layer of a second event has been opened.
**Purpose:** the Choctawhatchee (Hurricane Isaias) lower reach was used during development, so it is no longer a clean test. This protocol fixes the method and the event-selection rule *before* the second event's data is examined. The run on the second event happens once, and its numbers are reported whatever they are.

A machine-readable receipt with SHA-256 hashes of the source code and settings is in `research/freeze_receipt.json`. It is generated right after this file and before any second-event data is downloaded.

## 1. Frozen method (no re-tuning on the second event)

**Detector (Module A):**
- same-track NISAR PROVISIONAL GCOV pair, wet scene minus dry reference, frequency A;
- HH and HV linear power averaged over 5×5 10 m pixels, giving a 50 m UTM grid; dB = 10·log10;
- **flooded forest = (dry-date HV > −16 dB) AND (ΔHH > 2.0 dB)**.
  - The 2.0 dB threshold was chosen independently on the calibration reach of both Isaias pairs (076A Oct 17, 127D Oct 21).
  - The absolute rule for already-wet swamp is *not* part of the frozen method; it is still untested.

**Truth (Module C):**
- Gauge stage at the wet acquisition time: 15-min USGS record, linear interpolation, at most 30 min gap.
- Converted to NAVD88 with gauge datum plus a NOAA VDatum offset (NGVD29→NAVD88, NAD27 input frame), or used directly if the gauge datum is already NAVD88.
- Valley line:
  - coarse polyline through the corridor gauges, upstream → downstream;
  - re-centred on GFM reference water (search 3 km, step 1 km, smoothing half-width 2 stations);
  - end points fixed at the first and last gauge.
- Water surface interpolated linearly along the valley between gauges. Labels only between the first and last gauge chainage, within **4 km** of the line.
- Ground = USGS 3DEP bare earth averaged to 50 m.
- **wet** = water − ground > +0.5 m AND connected (8-neighbour) to GFM reference-water pixels through ground below the water surface.
- **dry** = water − ground between −5 m and −0.5 m.
- Everything else unlabelled.

**Metrics:**
- **Primary: CSI over all labelled pixels in the corridor.** There is no calibration/test split, because nothing is calibrated on this event.
- Secondary: F1, recall, precision.
- 95% intervals from a spatial block bootstrap (2 km chainage blocks, 2,000 draws, seed 0).

**Reference values (development, not a target):** Isaias lower reach CSI 0.67 (0.61–0.73) on 076A Oct 17, and 0.61 (0.56–0.66) on 127D Oct 21.

## 2. Event-selection rule (fixed now)

Candidates are tried in this order. The **first one that meets every criterion is used**:
1. Tropical Storm Arthur (Jun 17–19, 2026): Pearl River corridor, LA/MS.
2. Tropical Storm Arthur: Tchefuncte / Tangipahoa / Bogue Chitto corridors, LA.
3. Any other 2026 flood found by the same screening.

**Criteria** (screened only with CMR metadata, gauge records, the 3DEP coverage index and general land-cover knowledge):
- **(a)** At least 2 USGS stage gauges on one main channel inside the corridor, each with a 15-min record covering both acquisition times, and a known datum.
- **(b)** Two PROVISIONAL GCOV acquisitions on the **same track and frame**, both covering those gauges:
  - **wet** = the acquisition with the highest mean gauge stage above its dry value;
  - **dry** = the acquisition on that track/frame with the lowest mean gauge stage within ±60 days of the event.
  - The wet acquisition must have at least one corridor gauge more than 1.0 m above its dry-acquisition stage.
  - BETA and PROVISIONAL are never mixed. The dry reference may come after the flood, since change detection is symmetric in time.
- **(c)** 3DEP lidar-derived bare-earth coverage of the corridor.
- **(d)** A forested floodplain (bottomland hardwood or swamp) along most of the corridor.
- **(e)** Optional, for the ledger only: GFM and DSWx-S1 scenes within ±3 days of the wet acquisition.

**Not allowed before the frozen run:**
- opening NISAR GCOV/GUNW data or browse images of the candidate area;
- opening GFM or DSWx flood layers of the area;
- computing any truth-vs-prediction comparison.

## 2a. Selection outcome (metadata and gauges only)

Recorded **before** any NISAR, GFM or DSWx layer of the area was opened.

**Candidate 1 (Pearl River, Tropical Storm Arthur) meets all criteria.**

- **(a) Gauges.** Four USGS gauges on one main channel (the West Pearl branch), all with NAVD88 datums, so no VDatum offset is needed:

| Gauge | ID | Datum (ft) |
|---|---|---|
| Bogalusa | 02489500 | 54.64 |
| Pools Bluff | 02490193 | 0.32 |
| Pearl River, LA | 02492600 | −0.86 |
| I-10 near Slidell | 02492700 | 0.33 |

  The West Pearl was chosen over the East Pearl because it has more gauges with 2026 15-min records. The East Pearl has only Nicholson 02492511; Walkiah Bluff 02492110 and NSTL 02492620 have no 2026 data.

- **(b) Same-track pairs.** Two tracks cover all four gauges: 105A frame 017 and 156D frame 073. Frame 004A/017 covers none. Stage (ft) at each acquisition:

| Track | Acquisition (UTC) | Bogalusa | Pools Bluff | Pearl River LA | I-10 |
|---|---|---|---|---|---|
| 105A | Jun 21 11:19 | 18.53 | 62.08 | 17.08 | 7.09 |
| 105A | **Jul 3 11:19 (wet)** | 20.21 | 62.52 | 15.94 | 7.01 |
| 105A | Jul 15 | 9.16 | 57.11 | 9.07 | 5.13 |
| 105A | Jul 27 | 7.99 | 56.72 | 7.32 | 4.15 |
| 105A | **Aug 20 11:19 (dry)** | 6.80 | 56.36 | 5.64 | 2.98 |
| 156D | **Jun 25 00:45 (wet)** | 19.30 | 62.20 | 15.18 | 6.95 |
| 156D | Jul 7 | 12.79 | 59.15 | 13.62 | 6.79 |
| 156D | Jul 19 | 11.72 | 58.11 | 9.19 | 5.03 |
| 156D | Aug 12 | 7.18 | 56.45 | 6.16 | 3.51 |
| 156D | **Aug 24 00:45 (dry)** | 7.16 | 56.48 | 5.84 | 3.08 |

  - Mean rise of the wet over the dry acquisition: **105A Jul 3 vs Aug 20 = 8.47 ft**, which edges out 105A Jun 21 (8.25 ft). For 156D, Jun 25 vs Aug 24 = 7.77 ft.
  - Clarification of rule (b), added now and before any data was opened: when several tracks qualify, the **primary** pair is the one with the largest mean rise, **105A Jul 3 / Aug 20**. The best pair on the other track, **156D Jun 25 / Aug 24**, is run as a **secondary** frozen test with identical settings.
  - The largest single-gauge rise is 13.4 ft (4.1 m) at Bogalusa, which satisfies the "> 1.0 m" requirement.
  - Both dry references are within 60 days of their wet scene (48 and 60 days). Both are PROVISIONAL.
- **(c) Lidar.** 3DEP 1 m DEM projects LA_2021FloridaParishes and LA_UpperDeltaPlain_2015 cover the corridor box.
- **(d) Forest.** The corridor is dominated by bottomland hardwood and cypress–tupelo swamp: Pearl River WMA and Honey Island Swamp, from general knowledge.
- **(e) Ledger data.** GFM scenes exist on Jul 5 and Jul 6, within 3 days of Jul 3. No DSWx-S1 granules were found between Jun 30 and Jul 6.

## 2b. Pre-run log

These entries were made before the frozen run, and no imagery was read for them.

- **Entry point added.** `src/hidden_floods/frozen.py` and `scripts/run_frozen.py` were added after the receipt. They call only the hashed detector, truth, metric, grid and reader modules, and `check_receipt()` confirms those modules are unchanged.
- **Receipt check fixed.** The receipt's path keys use Windows backslashes, so the integrity check now normalises them. The receipt itself is unchanged.
- **Projection corrected in the site config.** The GCOV products for 105A/017 and 156D/073 are on **UTM 15N (EPSG:32615)**, not 16N. This was found from the HDF5 `projection` field only. The DEM was fetched on a 16N grid; it is resampled onto the 15N analysis grid by area averaging inside the frozen code path.
- **Reference water downloaded.** Only the static GFM reference-water layers (Jul 5–6 scenes) were downloaded for the valley-line refinement and connectivity seeds. GFM flood-extent layers were not downloaded or opened.

## 3. After the run

- Results go to `outputs/<site>/<pair>/frozen_metrics.json`, unchanged.
- Any later change (new rule, new truth settings, a bug fix) is reported as a **post-hoc** analysis next to the frozen result, never in place of it.
- If a bug is found that makes the frozen run invalid (for example a coordinate error), it is reported, fixed, and the rerun is labelled "rerun after bug fix: <description>".
