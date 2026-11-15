# Method v3: development record (not a validation)

**Code:** `src/hidden_floods/v3.py`; development scripts `scripts/dev_v3.py` and `scripts/dev_v3_otsu.py`. Caches and results are in `outputs/dev_v3/`.
**Data used:** the six spent NISAR pairs only (Choctawhatchee 076A/127D, Pearl 105A/156D, Tangipahoa 105A/156D). The Tangipahoa Jun 25 pair is excluded from averages: only 81 ha was still flooded.
**Not touched:** the Yellow River. Its corridor lies in the same 076A/127D scenes as the Choctawhatchee, but outside every pixel window ever read. It is also covered by track 055D.

## What v3 changes (each targets a measured failure)

| Change | Failure it targets | Kept? |
|---|---|---|
| Land-cover gate (ESA WorldCover: tree, herbaceous wetland, other; never crop/grass/shrub) | Farmland precision 0.03 | Yes. Every fold picked tree + wetland + other |
| Abstain where the nearest gauge is in late recession (more than 6 days after the crest) | Late recession CSI 0.21 | Yes, picked in every fold. Coverage is always reported |
| **Otsu threshold** on the smoothed valley-floor HH change, instead of an upland percentile | Signal strength varies by flood (+3.0 dB Isaias, +1.0 dB Pearl) | **Yes: the main gain** |
| Absolute flood-date rule (strong HH + high HH/HV) for already-wet swamp | Recall 0.26 on already-wet swamp | Not kept. It helped only one fold, and flooded vs dry forest separation varies (median HH −0.3 vs −4.0 dB at Isaias, −3.1 vs −4.2 at Tangipahoa) |
| Ponding-tolerant scoring (dry now but flooded at crest = left out) | Falling-limb ponding counted as false alarms | A scoring change, not a detector change. It mattered at Choctawhatchee Oct 21 (3,446 ha) |

A bug was found and fixed during development. The crest window was wrong whenever the dry reference came *after* the flood, which was the case at Pearl and Tangipahoa. It is now the 10 days before the wet pass, cut short only by a dry reference taken *before* the flood. There is a unit test for it.

## Leave-one-flood-out results

For each river, the setting is picked on the other two rivers, then scored on the held-out river.

| Held-out river | v3 Otsu (picked setting) | v3 quantile grid (192 settings) | For reference: earlier frozen held-out result |
|---|---|---|---|
| Choctawhatchee | **0.87** (recall 0.91, precision 0.94, coverage 0.97) | 0.52 | development river |
| Pearl | **0.61** (0.64 / 0.91, coverage 0.82) | 0.52 | 0.23 (v1, frozen) |
| Tangipahoa | **0.30** (0.74 / 0.33, coverage 1.00) | 0.31 | 0.29 (v2, frozen) |
| Mean | **0.59** | 0.45 | |

- **Otsu has no tuned number,** only two discrete choices, and every fold picked the same one. The quantile grid's choice swung between the 80th and 95th percentiles across folds, a sign of overfitting.
- **Instant and ponding-tolerant truth give the same leave-one-flood-out numbers to within 0.01.** Abstaining on late recession already removes most ponding pixels.
- **The Tangipahoa is still poor.** Precision is 0.33 on the falling limb in mixed land. Remaining false alarms sit 2–5 m above the river, beyond what a crest-envelope allowance explains.

**Candidate to freeze:** `V3OtsuRule(smooth_px=3, hand_max_m=6, valley_m=4000, min_threshold_db=0.5, landcover=(tree, wetland, other), abstain_timing=(late recession,))`.

## Honest status

**Update:** the one frozen test has now been run: CSI 0.88 (0.80–0.92) on the Yellow River, 055D Oct 16. See `V3_YELLOW_RESULTS.md` for what it does and does not support. The numbers below remain development numbers.

- These are **development** numbers. Otsu and the other v3 ideas came from studying these three floods, so even leave-one-flood-out estimates are optimistic.
- The planned test was one frozen run on the Yellow River.
  - **Independence caveat:** it shares the storm with the Choctawhatchee. The scenes used turned out to be new (track 055D).
  - A second fresh river (Escambia, also Isaias) would add confidence.
- **Not tried yet:**
  - a multi-date dry reference (needs 6 GB per extra scene);
  - interferometric coherence as a feature;
  - combining ascending and descending passes.
