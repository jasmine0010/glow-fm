# Truth-based blind-spot audit of operational flood maps

**Question:** of the floodplain flooding confirmed by river gauges plus lidar at the flood map's own acquisition time, what share did Copernicus GFM and OPERA DSWx-S1 show?

This uses **no NISAR detector**, so the detector accuracy problems in `SECOND_EVENT_RESULTS.md` and `THIRD_EVENT_RESULTS.md` don't affect it.

- **Code:** `src/hidden_floods/audit.py` and `scripts/audit_blind_spot.py`.
- **Output:** `outputs/audit/blind_spot.json`.
- **Truth:** Module C at the Sentinel-1 scene time (15-min USGS stage), with connectivity to GFM reference water and the 10 km gauge-support rule.
- **Permanent water** (GFM reference water) is excluded, so only floodplain flooding is audited.
- **Intervals:** 2 km block bootstrap.

## Results (every auditable date)

| Flood | Scene (UTC) | Confirmed floodplain flooding | **GFM mapped** | Inside GFM exclusion mask | DSWx-S1 mapped (95% CI) |
|---|---|---|---|---|---|
| Isaias, Choctawhatchee FL | Oct 10 23:45 (rising) | 2,198 ha | **0 ha (0.0%)** | 97% | 3.0% (1.2–5.6) |
| Isaias, Choctawhatchee FL | Oct 22 23:45 (receding) | 1,506 ha | **0 ha (0.0%)** | 97% | 2.7% (1.3–4.5) |
| Arthur, Pearl LA/MS | Jun 28 00:02 (near crest) | 17,972 ha | **0 ha (0.0%)** | 99% | 0.8% (0.7–1.1) |
| Arthur, Pearl LA/MS | Jul 5 00:01 | 16,731 ha | **0 ha (0.0%)** | 99% | no tile |
| Isaias, Yellow River FL (added with the packaged auditor) | Oct 10 23:45 | 1,545 ha | **0 ha (0.0%)** | 99% | 0.2% (0.0–0.5) |
| Isaias, Yellow River FL | Oct 22 23:45 | 832 ha | **0 ha (0.0%)** | 99% | 1.2% (0.0–2.1) |

The Yellow River site was created from scratch with three commands (`hidden-floods create-site / fetch / audit`). Its gauges are Oak Grove 02367900, Milligan 02368000 and Milton 02369600, all NGVD29 datums converted by VDatum (−0.19 to −0.30 ft). That brings the audit to **three rivers in two states, across two storms**.

- **On every auditable date, GFM mapped none of the confirmed floodplain flooding.** Across the whole study boxes it mapped only 0–27 ha on these dates, because its exclusion mask covers 86–89% of each box.
- **OPERA DSWx-S1 caught 0.8–3%,** mostly at the edges of herbaceous wetland and open water.
- **Combined, the two products caught 0.8–3% of about 18,000 ha of confirmed flooding at Pearl and about 1,500–2,200 ha at Isaias.**
- **Exposure that GFM didn't map** (OSM drivable roads, bridges excluded):
  - Pearl: **about 21–23 km**, mostly residential and service roads.
  - Isaias: under 0.5 km.
  - No OSM buildings fell inside the supported flooded area. Check OSM building completeness against Microsoft or USA Structures footprints before quoting zero.

## Base-rate check: how much of this is just the mask's size?

From `scripts/audit_base_rate.py` and `research/audit_base_rate.json`. "Confirmed" in this file means the gauge-and-lidar estimate, which is a model and not a direct sighting of water.

| Pass | Estimated flooding | Under tree cover | Valley corridor in mask | Estimated flooding in mask | Estimated dry ground in mask | GFM mapped on estimated flooding | Estimated flooding outside mask, GFM mapped |
|---|---|---|---|---|---|---|---|
| Choctawhatchee Oct 10 | 2,198 ha | 88% | 90% | 97.4% | 90.8% | 0 ha | 0 of 56 ha |
| Choctawhatchee Oct 22 | 1,506 ha | 89% | 90% | 97.4% | 93.3% | 0 ha | 0 of 40 ha |
| Pearl Jun 28 | 17,972 ha | 98% | 94% | 99.2% | 83.5% | 0.25 ha | 0.25 of 136 ha |
| Pearl Jul 5 | 16,731 ha | 98% | 94% | 99.2% | 86.2% | 0.75 ha | 0.75 of 129 ha |
| Yellow Oct 10 | 1,545 ha | 98% | 91% | 98.7% | 92.0% | 0 ha | 0 of 20 ha |
| Yellow Oct 22 | 832 ha | 99% | 91% | 98.9% | 93.6% | 0 ha | 0 of 9 ha |

- **The mask covers these valleys whether or not they flood.** Estimated dry ground is 84–94% inside it, so flooding is only 4–16 percentage points more likely to be inside than dry ground. Those differences have 95% intervals above zero, but they are small. The explanation for GFM's silence is "the valley is excluded", not "flooding happens to fall in the mask".
- **Outside the mask, GFM mapped 0–0.6% of estimated flooding.** This is the only part that tests detection, not coverage. The areas are small (9–136 ha), 43–69% of that ground is still tree cover, and it may sit at mask edges, so it's suggestive only.
- **"None" was rounded.** GFM mapped 0.25 and 0.75 ha on the Pearl, so say "at most 0.75 ha".
- **"Forest" can now be said for these areas,** since 88–99% of estimated flooding is WorldCover tree cover.
- **Gauge support:** the Pearl's estimate covers ground within 10 km of a gauge, including both ends of the 39 km reach between Pools Bluff and Pearl River, LA, which has no usable gauge between them.

## What could not be audited (stated openly)

- **Sentinel-1 missed the corridors on several near-crest dates.** Pearl Jun 17, 22 and 24, and Tangipahoa Jun 21, had 0% coverage of the corridor even though the scenes intersect the search box. Isaias Oct 17 also missed the river.
- **The Tangipahoa has no auditable date.** By the first covering pass (Jun 28) only 6 ha was still flooded.
- **Isaias truth is limited to within 10 km of a gauge.** The Caryville–Bruce midsection is excluded, which is why its confirmed area is smaller than the NISAR-mapped area.

## Caveats

- The truth assumes floodplain water stands at the river level interpolated between gauges, with ±0.5 m uncertainty excluded. It is weakest on falling limbs (ponding) and across long gauge gaps.
- The audit measures **recall** of the operational products, meaning what they missed. It isn't a full accuracy assessment: GFM flagged almost nothing in the corridors, so its precision can't be evaluated here.
- Two independent floods (two storms, two states) and four dates. That's strong evidence for these forested floodplains, not a global statistic. The global scale of the exclusion mask comes from Wagner et al. 2026 (32% of land; 51.7% in South America).

## Pitch line this supports

> "On six passes over three Gulf Coast rivers in two 2026 storms, gauges and lidar estimate 832–17,972 ha of floodplain flooding, 88–99% of it under tree cover. GFM mapped at most 0.75 ha of it. GFM's exclusion mask covers 90–94% of these valleys whether they flood or not, so this is a declared coverage gap. OPERA's Sentinel-1 product mapped 0.2–3%."

Wording rules for this claim:
- It is **floodplain** flooding, 88–99% under tree cover by WorldCover. Call it an **estimate**.
- It is a **coverage gap**: GFM declares it does not map inside its exclusion mask, so this is not a detection failure in observed areas.
- Say **GFM**, not "global flood maps" in general; OPERA's product is not at 0%.
- Never sum areas across dates. The largest single pass is 17,972 ha (Pearl, Jun 28).
- The six passes are not six independent samples: the Choctawhatchee and Yellow share a storm and scene times.
