# Bare-earth protocol: does a global elevation model with the trees removed recover what losing lidar cost?

**Status: ready to freeze, not yet frozen.** Code, tiles, code check and receipt are done (§7). This becomes the rule only when it is committed together with its receipt. Until then, no FABDEM data over the test rivers may be opened. Changing this file after the receipt was written means deleting the receipt and writing it again before the commit.
**Receipt (at freeze):** `research/freeze_receipt_bare_earth.json`, with SHA-256 hashes of this file, the tile list, the run code and the v4, overbank and no-lidar receipts. Tile hashes go in `research/bare_earth_tiles.json`. The run refuses to start if any of them has changed. The freeze commit is the dated record.

**Why this test:** without lidar, NISAR's mean CSI fell from 0.38 to 0.25 on the seven judged passes, a moderate cost by the fixed rule (`NO_LIDAR_RESULTS.md`). A check after that run points at the cause: Copernicus GLO-30 measures the top of the forest. On the Satilla, ground the estimate calls flooded sits a median 0.4 m *below* the river by lidar but 4.9 m *above* it by Copernicus, so v4's height limit throws out much of the flooded forest. Loosening the limit raised the score, but only by mapping large areas the estimate can't check, so it was rejected as a fix. A bare-earth model attacks the cause instead of the limit. Lidar like the test rivers' covers only part of the world's forested floodplains, so this decides whether the method has a credible route to them.

**Question 1, the primary one:** with no lidar anywhere in the map, does NISAR score higher with a bare-earth global model than with Copernicus GLO-30?
**Question 2:** with bare-earth heights, does NISAR still beat a height map from the same model with no radar?
**Question 3:** how much of the gap to lidar remains?

## 1. What has and hasn't been seen

**Already seen:** the code check on Yellow River Oct 16, a used river that isn't in this test: NISAR with FABDEM 0.891, with Copernicus 0.774 and with lidar 0.891; flooded ground's median height above the river −0.06 m by FABDEM, +1.94 m by Copernicus and −0.77 m by lidar. It shows the code works, it is not evidence, and the readings in §5 were written before it ran. Also all NISAR maps and scores on these passes, the lidar and Copernicus maps and their scores (`no_lidar_results.json`), the post-hoc height check (`no_lidar_posthoc.json`) and the estimate. **Only the bare-earth elevation data is new.** The rivers and radar aren't fresh, and the test can only ask what changes when the elevation source changes.

**Not seen:** FABDEM over the test rivers. FABDEM is packaged as 10×10° zip archives of 1×1° tiles. `scripts/fetch_bare_earth_dem.py` reads only each archive's directory and the needed tiles, using byte ranges, so the multi-gigabyte archives aren't downloaded whole. Each tile is checked against the CRC-32 in its archive's directory, written, and hashed (SHA-256), but never decoded. The archive address and size, and each tile's hash, size and CRC-32, go in `bare_earth_tiles.json`. The code is checked only on Yellow River Oct 16, a used river outside this test, whose tile (N30W087) covers no test river. The fetch script refuses if they overlap.

## 2. Elevation model, fixed now

**FABDEM** (Hawker et al., 2022, *Environmental Research Letters*): Copernicus GLO-30 with buildings and forest removed by a trained correction, at the same 1 arc-second spacing. It starts from the same model as the earlier test, so the comparison isolates the tree and building removal.

- **Version:** V1-2 (January 2023, the current release), from the University of Bristol data repository, https://doi.org/10.5523/bris.s5hqmjcdj8yo2ibzi9b4ew3sn. The archive addresses and tile hashes go in `bare_earth_tiles.json` before the freeze.
- **Licence, confirmed:** CC BY-NC-SA 4.0, as stated in the dataset's `readme.txt` and `license.txt`. (The repository's catalogue field shows a different non-commercial licence; the dataset's own files are taken as authoritative.) Use here is non-commercial. The project's code is MIT, and ShareAlike applies to adapted material, so **no FABDEM tile or layer derived from it is committed, published on the site or bundled in `app/data`.** Tiles stay in the local data folder. Only scores and summary numbers are recorded, with the citation and the required Copernicus attribution:
  > FABDEM is produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved.
- **Citation:** Hawker, L., Uhe, P., Paulo, L., Sosa, J., Savage, J., Sampson, C. & Neal, J. (2022). A 30 m global map of elevation with forests and buildings removed. *Environmental Research Letters* 17, 024016.
- **No other model is tried in this test.** Choosing between bare-earth models after seeing scores would be tuning.

## 3. Passes, fixed now

The same seven passes as the no-lidar test: every frozen v4 pass that was judged (at least 500 ha of estimated flooding and coverage of at least 0.60). The three failures stay in.

| Pass | NISAR with lidar | NISAR with Copernicus | Copernicus height map | Lidar height map |
|---|---|---|---|---|
| Satilla Oct 15 | 0.73 | 0.42 | 0.28 | 0.83 |
| Satilla Oct 19 | 0.72 | 0.42 | 0.25 | 0.69 |
| Ochlockonee Oct 14 | 0.43 | 0.32 | 0.23 | 0.39 |
| St Marys Oct 7 | 0.58 | 0.47 | 0.28 | 0.54 |
| Pee Dee Jul 27 | 0.10 | 0.04 | 0.29 | 0.15 |
| Neuse Jul 26 | 0.06 | 0.07 | 0.16 | 0.15 |
| Lower Sabine Jul 17 | 0.05 | 0.03 | 0.03 | 0.08 |
| **Mean** | **0.38** | **0.25** | **0.22** | **0.41** |

These are the recorded values. The run recomputes the Copernicus and lidar maps from their hashed inputs and refuses if any differs from the record by more than 0.001.

## 4. Frozen maps

FABDEM heights are averaged onto the same 50 m grid as Copernicus was. Height above the river uses the same `height_above_river` code, with the same valley line.

| Map | Radar | Elevation | Rule |
|---|---|---|---|
| **NISAR with FABDEM** | Yes | FABDEM | Hashed v4 rule, unchanged, including its 6 m height limit |
| **FABDEM height map** | No | FABDEM | Forest, wetland or other land cover under 2 m above the river. Same limit as the other height maps, not tuned |
| NISAR with Copernicus | Yes | Copernicus | Recorded no-lidar map |
| Copernicus height map | No | Copernicus | Recorded |
| NISAR with lidar | Yes | Lidar | Recorded frozen map |
| Lidar height map | No | Lidar | Recorded |

**Scoring:** CSI against the unchanged gauge-and-lidar estimate, on the pixels each pass's frozen v4 run scored, with a 2 km block bootstrap (2,000 draws, seed 0). Paired intervals compare maps on the same draws.

**Also recorded for every map**, so a gain can't hide in unchecked ground (the problem the no-lidar check found). All three are counted within the pass's scored pixels, as in `no_lidar_posthoc.json`:
- mapped area (ha) and the share of it the estimate labels as flooded or dry;
- area mapped on ground more than 5 m above the water by lidar (the site's dry-height limit), which is very likely wrong.

**Fairness check:** the FABDEM height map is also scored at 1, 2, 3, 4, 5, 6, 8 and 10 m, and the best limit per pass is reported. That choice uses the answer, so it flatters the height map. It isn't the primary comparison.

## 5. Reading, fixed in advance

A map beats another on a pass only if the paired 95% interval is entirely on its side of zero.

**Question 1: NISAR with FABDEM against NISAR with Copernicus.**

| Result across the seven passes | Reading |
|---|---|
| Mean higher by at least 0.05, FABDEM wins on at least 3 passes, and loses on none | **Supported:** removing trees recovers part of the cost |
| Mean higher, and FABDEM wins on at least 1 pass | **Partly supported** |
| Anything else | **Not supported** |

**Guard on Question 1.** The reading drops one level (Supported to Partly, Partly to Not) if either holds:
- NISAR with FABDEM's mapped area, summed over the seven passes, is more than 1.5 times NISAR with lidar's;
- its labelled share, averaged over the passes, is under half of NISAR with lidar's.

**Question 2: NISAR with FABDEM against the FABDEM height map.** The same table as the no-lidar test's Question 1:

| Result | Reading |
|---|---|
| NISAR's mean is higher, it wins on at least 3 passes, and the height map wins on none | **Supported:** radar adds value over a bare-earth height map |
| NISAR's mean is higher, and it wins on at least 1 pass | **Partly supported** |
| Anything else | **Not supported** |

The write-up says plainly if the reading would differ at the height map's best limit.

**Question 3: the remaining gap to lidar.** Mean CSI of NISAR with lidar minus NISAR with FABDEM:

| Mean gap | Reading |
|---|---|
| 0.05 or less | Small |
| More than 0.05, up to 0.15 | Moderate |
| More than 0.15 | Large |

**The mechanism, predicted now.** If tree height is the cause, FABDEM should place flooded forest near the river:
- **P1:** On Satilla Oct 15, ground the estimate calls flooded (its flooded pixels within the scored pixels) sits a median of under 2.0 m above the river by FABDEM (lidar: −0.4 m; Copernicus: +4.9 m).
- **P2:** On at least 5 of the 7 passes, the median of (model height minus lidar height) on that ground is closer to zero for FABDEM than for Copernicus.

If Question 1 is supported but P1 and P2 fail, the gain isn't explained by tree removal, and the write-up says so.

**What follows from the results:**
- **Q1 supported or partly supported:** the site can say that, on these US rivers, a bare-earth global model recovered part of the accuracy lost without lidar. It still can't claim this holds in the tropics, where forests are taller and the correction is less certain.
- **Q1 not supported:** the site keeps saying the method needs lidar-quality ground height to do well, and global maps stay framed as where to look, not as validated flood maps.
- **Either way:** any map outside the US stays labelled unvalidated.
- **No tuning.** v4, its 6 m limit and the 2 m height-map limit stay fixed. Any change is a new method that needs its own test.

## 6. Limits stated in advance

- **FABDEM is a model.** Its forest correction was trained on reference data, and its error under dense canopy is larger than in open land. It may also contain lidar from regions like these in its training, which would flatter it here more than in the tropics.
- **Gauges still play a part.** The valley line runs through gauges, and scored pixels leave out rivers in late recession, which gauges define. A real global map wouldn't have either.
- **The reference uses lidar.** The estimate is independent of FABDEM, but it remains a model, and it shares lidar with the "with lidar" maps.
- **Same places, already seen.** All seven passes are in the southeastern US, and their radar scores, including the three failures, are known.
- **Not independent.** Satilla's two passes share a flood, and passes share storms.
- **Small n.** Seven passes can show a direction, not a precise size.

## 7. Before the freeze (to do, in order)

1. ~~**Licence and source.**~~ Done: CC BY-NC-SA 4.0, V1-2, address above (§2).
2. **Code**, reusing the no-lidar test's code with only the elevation source changed (written; `tests/test_frozen_bare_earth.py` covers the reading rules on synthetic numbers):
   - `scripts/fetch_bare_earth_dem.py`: fetch and hash tiles for the seven test rivers and Yellow, without decoding them. It refuses if a Yellow tile covers a test river.
   - `src/hidden_floods/frozen_bare_earth.py`: the maps, scores, area checks, P1/P2 heights and the readings in §5, computed by code. It refuses to write results if the recorded Copernicus or lidar values don't reproduce (§3).
   - `scripts/run_frozen_bare_earth.py`: runs once. It refuses if `research/bare_earth_results.json` exists or any hashed file has changed, and logs the attempt before any test-river elevation is read.
   - `scripts/check_bare_earth_code.py`: dry run on Yellow Oct 16. NISAR with lidar must reproduce 0.890845, and the replay must agree on more than 99.9% of scored pixels.
   - `scripts/make_freeze_receipt_bare_earth.py`: writes the receipt.
3. ~~**Fetch the tiles**, then run the code check.~~ Done: 15 tiles from three archives, all matching their recorded hashes; the code check passed (NISAR with lidar reproduced 0.890845).
4. **Freeze:** commit this file, the tile list, the code and the receipt together. That commit is the dated record. FABDEM tiles themselves are not committed.
5. **Run once.**

## 8. After the run

Results go once to `research/bare_earth_results.json`. A bug fix after scoring counts as post-hoc, is labelled that way, and doesn't replace the first number. The write-up goes in `BARE_EARTH_RESULTS.md` whichever way it comes out, and `NO_LIDAR_RESULTS.md` links to it.
