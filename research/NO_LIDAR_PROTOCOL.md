# No-lidar protocol: does NISAR add anything where there's no lidar?

**Written** before any Copernicus elevation data over the test rivers was opened.
**Receipt:** `research/freeze_receipt_no_lidar.json`, with SHA-256 hashes of this file, the elevation-tile list, the run code and the earlier receipts. Tile hashes are in `global_dem_tiles.json`. The run refuses to start if any of them has changed. The freeze commit is the dated record.

**Why this test:** on the latest frozen test, a lidar height map with no radar averaged 0.61, against NISAR's 0.62 (`OVERBANK_RESULTS.md`). That leaves a fair question: why use radar at all? But detailed lidar like this covers only part of the world's forested floodplains. Elsewhere, the alternative is a coarser global elevation model. So the comparison that matters globally is NISAR against a height map from that model.

**Question 1, the primary one:** with no lidar anywhere in the map, does NISAR score higher than a height map from a global elevation model?
**Question 2:** how much accuracy does NISAR lose when lidar is replaced?

## 1. What has and hasn't been seen

**Already seen:** all NISAR maps and scores on these passes, the lidar height map's scores, and the estimate. **Only the global elevation data is new.** The rivers aren't fresh, and the test can only ask what changes when the elevation source changes.

**Not seen:** Copernicus elevation data over the test rivers. Tiles were downloaded and hashed, not opened. The code was checked only on Yellow River Oct 16, a used river outside this test, using `scripts/check_no_lidar_code.py`.

## 2. Passes, fixed now

Every frozen v4 pass that was judged: at least 500 ha of estimated flooding and coverage of at least 0.60. That includes the three failures, so the test can't favour radar by leaving them out.

| Pass | Frozen v4 CSI | Lidar height map CSI |
|---|---|---|
| Satilla Oct 15 | 0.73 | 0.83 |
| Satilla Oct 19 | 0.72 | 0.69 |
| Ochlockonee Oct 14 | 0.43 | 0.39 |
| St Marys Oct 7 | 0.58 | 0.54 |
| Pee Dee Jul 27 | 0.10 | 0.15 |
| Neuse Jul 26 | 0.06 | 0.15 |
| Lower Sabine Jul 17 | 0.05 | 0.08 |

## 3. Frozen maps

**Global elevation:** Copernicus GLO-30, averaged onto the same 50 m grid. Height above the river uses the same `height_above_river` code as lidar, with the same valley line.

| Map | Radar | Elevation | Rule |
|---|---|---|---|
| **NISAR without lidar** | Yes | Copernicus | Hashed v4 rule, unchanged, with Copernicus height above the river |
| **Global height map** | No | Copernicus | Forest, wetland or other land cover under 2 m above the river. Same limit as the lidar map, not tuned |
| NISAR with lidar | Yes | Lidar | The recorded frozen map |
| Lidar height map | No | Lidar | The recorded comparison map |

**Scoring:** CSI against the unchanged gauge-and-lidar estimate, on the pixels each pass's frozen v4 run scored, with a 2 km block bootstrap (2,000 draws, seed 0). Paired intervals compare maps on the same draws.

**Fairness check:** the 2 m limit may not suit a coarser model, so the global height map is also scored at 1, 2, 3, 4, 5, 6, 8 and 10 m. The best limit per pass is reported. That choice uses the answer, so it flatters the height map, and it isn't the primary comparison.

## 4. Reading, fixed in advance

**Question 1: NISAR without lidar against the global height map.** A map beats the other on a pass only if the paired 95% interval is entirely on its side of zero.

| Result across the seven passes | Reading |
|---|---|
| NISAR's mean is higher, it wins on at least 3 passes, and the height map wins on none | **Supported:** radar adds value where there's no lidar |
| NISAR's mean is higher, and it wins on at least 1 pass | **Partly supported** |
| Anything else | **Not supported** |

The result is also compared with the fairness check, and the write-up says plainly if the reading would differ at the height map's best limit.

**Question 2: the cost of losing lidar.** Mean CSI of NISAR with lidar minus NISAR without lidar:

| Mean drop | Reading |
|---|---|
| 0.05 or less | Small |
| More than 0.05, up to 0.15 | Moderate |
| More than 0.15 | Large |

**What follows from the results:**
- **Supported or partly supported:** the project can say that, on these US rivers, radar beat a global height map. It still can't claim this holds in the tropics.
- **Not supported:** the project can't argue that radar beats a global height map on accuracy, and it must say so wherever global maps are shown. Radar's remaining argument is that it shows the date of a flood.
- **Either way:** any map outside the US stays labelled as unvalidated, and this result doesn't validate it.
- **No tuning.** v4 and the 2 m limit stay fixed. Any change is a new method that needs its own test.

## 5. Limits stated in advance

- **Copernicus GLO-30 is a surface model.** It includes tree height, so in forest it reads above the ground, which should hurt both Copernicus maps. A bare-earth global model might do better. That would be a separate test.
- **Gauges still play a part.** The valley line runs through gauges, and scored pixels leave out rivers in late recession, which gauges define. A real global map wouldn't have either, and would need a mapped river network instead. So this removes lidar and doesn't remove every local input.
- **The reference uses lidar.** The estimate is independent of Copernicus, but it remains a model and shares lidar with the "with lidar" maps.
- **Same places and forests.** All seven passes are in the southeastern US. Tropical forests are taller and denser, and floods there last longer.
- **Not independent.** Satilla's two passes share a flood, and passes share storms.
- **Not blind on radar.** The radar scores on these passes are already known, including the three failures.

## 6. After the run

Results go once to `research/no_lidar_results.json`. The attempt is logged before elevation data over the test rivers is read. A bug fix after scoring counts as post-hoc, is labelled that way, and doesn't replace the first number. The write-up goes in `NO_LIDAR_RESULTS.md` whichever way it comes out.
