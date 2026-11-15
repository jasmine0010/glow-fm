# Third-event protocol: held-out test of method v2

**Written** before any third-event data (NISAR imagery or browse images, GFM or DSWx flood layers, truth) was opened, and before candidate events were screened.
**Receipt:** `research/freeze_receipt_v2.json`, with SHA-256 hashes of all scientific modules, generated right after this file.

## 1. Why v2, and what is spent

The v1 fixed rule (ΔHH > 2.0 dB) did not transfer to Pearl River: CSI 0.23 (`SECOND_EVENT_RESULTS.md`). v2 was developed on **all four spent pairs** (Isaias 076A/127D, Pearl 105A/156D) using `scripts/dev_selfcal.py` and `scripts/dev_selfcal_grid2.py`. All v2 development scores are in-sample.

| Pair (development, gauge-supported region) | v1 fixed 2 dB | v2 frozen |
|---|---|---|
| Isaias 076A Oct 17 | 0.70 | 0.65 |
| Isaias 127D Oct 21 (falling limb) | 0.43 | 0.30 |
| Pearl 105A Jul 3 | 0.32 | 0.70 |
| Pearl 156D Jun 25 | 0.18 | 0.43 |
| **Mean** | 0.41 | **0.52** |

Development notes, recorded honestly:
- **The height-above-river gate can leak truth geometry.** Truth uses the same lidar DEM, and no truth-wet pixel sat more than 3 m above the river. Tight gates (2–3 m) scored higher partly for that reason. So the gate is **fixed at a generous 6 m**, chosen on physical grounds rather than by tuning. With that gate the scores are almost the same as with no gate at all.
- **The falling-limb pair (Isaias 127D Oct 21) scores worst, mostly on precision.** Water left ponded in backswamps while the river fell is labelled "dry" by gauge-based truth. That is a known limit of this kind of truth, not necessarily a detector error.

## 2. Frozen method v2

**Detector:**
- **forest** = dry-date HV > −16 dB, same 50 m GCOV multilook as v1;
- **change** = ΔHH (dB), smoothed with a NaN-aware 3×3 box mean (150 m);
- **height above river (HAND proxy)** = DEM minus the channel profile. The profile is the 10th percentile of DEM within 250 m of the valley line, in 1 km chainage bins, forced non-increasing downstream;
- **scene threshold** = 90th percentile of the change over the reference: forest with height above river > 12 m and within 15 km of the valley line. Floor 0.5 dB. If there are fewer than 500 reference pixels, the run stops;
- **flooded forest** = forest AND height above river < 6 m AND change > scene threshold.

**Truth:** v1 settings unchanged (±0.5 m margin, −5 m dry limit, 4 km corridor, connectivity to GFM reference water, valley line through the gauges refined on reference water), **plus the truth-confidence rule** adopted from the Pearl diagnosis: the **primary region** is pixels within **10 km of a gauge along the valley**.

**Metrics:**
- **Primary: v2 CSI in the gauge-supported region.**
- Secondary: v2 on the full corridor, and v1 (2 dB) in the supported region as the baseline.
- Block bootstrap: 2 km blocks, 2,000 draws, seed 0.

## 3. Third-event selection rule

Criteria (a)–(e) of `SECOND_EVENT_PROTOCOL.md` §2 apply unchanged, with two additions:
- **(f)** The corridor must not overlap a spent corridor (Choctawhatchee, or the West Pearl corridor including the lower Bogue Chitto confluence area).
- **(g)** At least **5,000 ha** of gauge-supported truth (wet plus dry) is expected. This is estimated from metadata only: corridor length near gauges, not truth itself. Otherwise the next candidate is tried.

Ordered candidates. The first that meets every criterion is used:
1. **Tangipahoa River** (LA/MS), Tropical Storm Arthur, Jun 2026.
2. **Tchefuncte River** (LA), Arthur.
3. **Yellow / Shoal River** (FL), Hurricane Isaias, Oct 2026.
4. **Escambia River** (FL/AL), Isaias.
5. Any other 2026 forested-floodplain flood found by the same metadata screening.

**Independence caveat, stated in advance:** candidates 1–4 share a storm (and so a season and sensor geometry period) with a development event. They are new rivers, forests and gauges, but they are not new storms.

**Not allowed before the run:** the same as the second-event protocol. No NISAR imagery or browse images of the candidate area, no GFM or DSWx flood layers, no truth-vs-prediction comparison. The static GFM reference-water layer may be downloaded.

## 3a. Selection outcome (metadata and gauges only)

**Candidate 1 (Tangipahoa River, Tropical Storm Arthur) meets every criterion.**

- **(a) Gauges.** Four mainstem USGS gauges with 15-min records covering both acquisition times:

| Gauge | ID | Datum |
|---|---|---|
| Kentwood | 07375300 | 179.47 NAVD88 |
| Amite | 07375430 | 80.0 NAVD88 |
| Robert | 07375500 | 6.6 NAVD88 |
| Ponchatoula | 07375650 | −2.75 NAVD88 |

  Tangipahoa (07375410) and Tickfaw (07375450) are excluded because their records stop before August.

- **(b) Same-track pairs.** Tracks 105A/017 and 156D/073 cover all four gauges. These are the same products used for Pearl, but only pixel windows over the Pearl box were ever read; the Tangipahoa corridor around −90.4° lies outside that box. Stage (ft) at each acquisition:

| Track | Acquisition | Kentwood | Amite | Robert | Ponchatoula |
|---|---|---|---|---|---|
| 105A | **Jun 21 11:19 (wet)** | 3.22 | 6.91 | 13.54 | 13.02 |
| 105A | **Aug 20 (dry)** | 1.40 | 5.19 | 6.83 | 5.04 |
| 156D | **Jun 25 00:45 (wet)** | 2.06 | 5.83 | 9.01 | 7.74 |
| 156D | **Aug 12 (dry)** | 1.51 | 5.21 | 6.78 | 5.22 |

  - Mean rise: 105A Jun 21 vs Aug 20 = 4.56 ft, which makes it **primary**. 156D Jun 25 vs Aug 12 = 1.48 ft is **secondary**.
  - Largest single-gauge rise: Ponchatoula 7.98 ft (2.4 m), so the "> 1 m" requirement holds.
  - Time between wet and dry: 60 and 48 days.
  - **Noted in advance:** the crest was Jun 17–19, so both wet scenes are on the **falling limb**. Upstream (Kentwood, Amite) the river had mostly receded by Jun 21. Development showed gauge-based truth is weakest on falling limbs.
- **(c) Lidar.** The 3DEP catalog lists `LA_2021FloridaParishes_C24` at 1 m over the corridor. The 3DEP index layer was returning errors; the ImageServer catalog query worked.
- **(d) Forest.** Bottomland hardwood floodplain, with swamp forest in the lower reach toward Ponchatoula and Manchac. Upstream there is a mix with farmland.
- **(e) Ledger data.** GFM scenes exist on Jun 21 (00:10 UTC).
- **(f) No overlap.** The corridor is around −90.4°, about 40 km west of the spent West Pearl corridor.
- **(g) Enough truth.** The corridor is about 65 km long with gauge spacing of 23, 28 and 8 km. Most of it lies within 10 km of a gauge, so supported truth is expected to exceed 5,000 ha.

## 4. After the run

Results go to `outputs/<site>/<pair>/frozen_v2_metrics.json`, unchanged. Every later analysis is labelled post-hoc. Bug-fix reruns are labelled as such.
