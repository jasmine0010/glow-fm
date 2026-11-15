# Independent check results

**Rules:** `INDEPENDENT_CHECK_PROTOCOL.md`, SHA-256 `df33ed1546568ea8559fcd1b68be75c1ecc84557d17f118f6afdc9a7eb14758c` at analysis, unchanged then; `8ea6f964ef15a85ef55e1cee92b0fca33b62a0892b4c4cd4f9b9f238e12ae808` after dates were removed. It was not in a commit before the run. Data: `independent_check_results.json`, `independent_check_points.json`. Scripts: `scripts/independent_check_prepare.py`, `scripts/independent_check_analyze.py`. Saved sheets, the key and reviews: `outputs/independent_check/`.

**No frozen score changes.** Reviewers were two AI vision agents, blind to river, stratum and hypothesis. They aren't trained photo-interpreters.

## Answer

- **The estimate has independent support on the Satilla, for ground imagery can see.** Reviewers found flooding at 9 of 14 decidable estimate-wet points and 0 of 11 estimate-dry points, a difference of +0.64 (95% interval 0.28 to 0.84). Under the fixed rule this reads **supported**.
- **Whether radar flags beyond the corridor are real is still unknown.** Too few of those points could be judged on any river. The fixed reading is **imagery can't decide**.
- **Mapping under closed canopy remains unvalidated.** Only 11–21% of points were decidable, as the protocol warned.
- **The automatic water index didn't confirm the visual result.** It found new water at 0 of 350 points. An audit, below, suggests the rule was too strict for water at the edge of a box, but that explanation is post-hoc.

## Reviews

| Case | Points | Kappa | Agreement | FLOOD | PERMANENT | DRY | CANOPY | CLOUD | UNSURE | Decidable |
|---|---|---|---|---|---|---|---|---|---|---|
| Satilla, Sentinel-2 | 175 | 0.75 | 86% | 11 | 5 | 20 | 106 | 0 | 33 | 21% |
| Lower Sabine, Sentinel-2 | 175 | 0.80 | 87% | 0 | 0 | 19 | 68 | 65 | 23 | 11% |
| Lower Yellow, NOAA aerial | 137 | 0.62 | 83% | 1 | 11 | 3 | 90 | 0 | 32 | 11% |

## Flood share by stratum (FLOOD of decidable points)

| Stratum | Satilla | Lower Sabine | Lower Yellow |
|---|---|---|---|
| A flagged, estimate wet | 0 of 2 | 0 of 1 | 0 of 0 |
| B flagged, estimate dry | 0 of 4 | 0 of 4 | 0 of 1 |
| C flagged, near water line | 2 of 4 | 0 of 0 | 0 of 0 |
| D flagged, beyond corridor | 0 of 1 | 0 of 4 | 0 of 3 |
| E not flagged, estimate wet | 9 of 12 | 0 of 2 | 1 of 7 |
| F not flagged, estimate dry | 0 of 7 | 0 of 4 | 0 of 3 |
| G not flagged, beyond corridor | 0 of 6 | 0 of 4 | 0 of 1 |

## Fixed readings

| Reading | Satilla | Lower Sabine | Lower Yellow |
|---|---|---|---|
| 1. Estimate wet against dry | **Supported**: 9/14 vs 0/11, +0.64 (0.28 to 0.84) | Imagery can't decide: 0/3 vs 0/8 | Imagery can't decide: 1/7 vs 0/4 |
| 2. Flags beyond corridor against control | Imagery can't decide: 0/1 vs 0/6 | Imagery can't decide: 0/4 vs 0/4 | Imagery can't decide: 0/3 vs 0/1 |
| 3. Estimate wet, flagged against not | Too few: 0/2 vs 9/12 | Too few: 0/1 vs 0/2 | Too few: 0/0 vs 1/7 |

**Strong against failed:** the expected pattern, reading 2 supported on the Satilla and not on the Lower Sabine, could not be tested. All 19 decidable Lower Sabine points were dry, but 37% of its points were cloud or haze.

**Automatic measure:** new water at 0 of 350 points, so it gave no difference in any comparison.

## Post-hoc audit, not blind

This came after unblinding. It changes no reading.

- **Why the two measures differ.** Viewing the 16 water-consensus Satilla rows, the flooding is visible, as new dark areas in several fields and clearings. It often only reaches part of the box. The most any FLOOD point scored on the water index was 40% of box pixels, under the 50% rule.
- **Why reading 1 rests on unflagged points.** Imagery sees openings. Radar's flags are almost all forest, where 20 of 25 stratum A points were hidden by canopy, against 6 of 25 in stratum E. So all nine visible estimate-wet floods fall in E. This tests the estimate, not radar.
- **Where radar flagged ground that could be seen, it was usually dry.** Pooling flagged strata, the Satilla has 2 FLOOD, 2 PERMANENT and 7 DRY, and the Lower Sabine has 9 DRY of 9. Double bounce needs trunks, so this may not transfer to forest. It does suggest brightening on open ground isn't reliable flood evidence, including in the land cover the method calls tree. Pooling wasn't in the protocol, and the numbers are small.
- **Some visible floods were dark to radar.** Four of the nine stratum E FLOOD points had HH change at or below +0.3 dB, and three were negative. Others brightened by up to 4.6 dB in raw HH without being flagged after smoothing. This is the open-water behaviour the method doesn't look for.
- **The aerial photos may hold more than these chips showed.** Both reviewers said forest panels show pale crowns over a flat, dark floor that they couldn't separate from shadow or water at this chip size. The chips were about 0.6 m per pixel, while NOAA's source is 15–30 cm.

## Limits

- **Reviewers:** AI agents, not expert interpreters. "FLOOD" often means water reaching a box, not filling it.
- **Selection:** decidable points are openings inside mostly forested valleys, so reading 1 doesn't describe water under trees.
- **One river:** the supported reading comes from one flood, and nine visible points.
- **Timing and scenes:** Satilla imagery came 18.5 hours before radar. Lower Sabine scenes came about 18 or 30 hours from radar, with a May 2 before scene. Yellow flights came 4–5 days before radar, with stage about 0.5–0.6 m lower at Milton.
- **Land cover:** WorldCover called most visible openings tree, so it can't be used to predict which points imagery can judge.

## What can be claimed

**Supported:** "On the Satilla, blind review of Sentinel-2 imagery a day before the radar pass found flooding where the gauge-and-lidar estimate says wet, and none where it says dry, on open ground that imagery can see."

**Not supported:** that imagery validates NISAR's flood map, that flags beyond the corridor are right or wrong, or that the estimate is right under closed canopy.
