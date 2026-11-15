# No-lidar test results

**Run once from freeze commit `84d06e3`, with one logged attempt.** The rules are in `NO_LIDAR_PROTOCOL.md`, and results are in `no_lidar_results.json`.

## Answer

- **Does NISAR beat a global height map without lidar? Partly supported, under the fixed rule.** NISAR averaged 0.25 against 0.22. It won clearly on 4 of 7 passes, and the height map won clearly on 2. "Supported" needed the height map to win on none.
- **The fairness check goes against radar.** If the height map could use its best limit on each pass, it would average 0.31, above NISAR's 0.25. That limit uses the answer, so no real user could choose it, but it means the margin is not robust. NISAR beat even that flattered height map on 2 of 7 passes.
- **How much does losing lidar cost? A moderate 0.13 in mean CSI,** by the fixed rule. Much of it falls on the Satilla, where the score drops from 0.73 to 0.42.
- **The likely cause is tree height in the global model,** according to a check made after the run (below). Simply removing the height limit isn't a fix.

## Results

CSI against the gauge-and-lidar estimate, on the pixels each frozen v4 run scored.

| Pass | NISAR without lidar | Global height map | Difference (95% interval) | Winner | Height map at its best limit | NISAR with lidar | Lidar height map |
|---|---|---|---|---|---|---|---|
| Satilla Oct 15 | **0.42** | 0.28 | +0.13 (+0.09 to +0.19) | NISAR | 0.54 at 10 m | 0.73 | 0.83 |
| Satilla Oct 19 | **0.42** | 0.25 | +0.17 (+0.11 to +0.20) | NISAR | 0.45 at 10 m | 0.72 | 0.69 |
| Ochlockonee Oct 14 | **0.32** | 0.23 | +0.09 (+0.03 to +0.15) | NISAR | 0.28 at 6 m | 0.43 | 0.39 |
| St Marys Oct 7 | **0.47** | 0.28 | +0.19 (+0.07 to +0.31) | NISAR | 0.31 at 6 m | 0.58 | 0.54 |
| Pee Dee Jul 27 | 0.04 | **0.29** | −0.26 (−0.36 to −0.18) | Height map | 0.29 at 2 m | 0.10 | 0.15 |
| Neuse Jul 26 | 0.07 | **0.16** | −0.10 (−0.17 to −0.03) | Height map | 0.18 at 1 m | 0.06 | 0.15 |
| Lower Sabine Jul 17 | 0.03 | 0.03 | −0.01 (−0.01 to 0.00) | Neither | 0.08 at 10 m | 0.05 | 0.08 |
| **Mean** | **0.25** | **0.22** | | | 0.31 | 0.38 | 0.41 |

**What this shows:**
- **NISAR wins where its signal exists.** All four wins are on the passes that scored 0.43 or higher with lidar. The three rivers where v4 had already failed show no win. This is a pattern in seven passes that aren't independent, and it wasn't a tested prediction.
- **When NISAR maps flooding on the Satilla, it's usually right, but it misses much of it.** Without lidar on Oct 15, precision stays at 0.95 and recall falls from 0.79 to 0.42.
- **A global height map can do better than lidar on the wrong river.** On the Pee Dee, it scored 0.29 against lidar's 0.15. Lidar's map flagged much of the low valley, where little flooding is estimated. This doesn't mean the global model is more accurate there.

## Post-hoc check: why did recall fall?

This came after the run, and it changes no result above (`scripts/posthoc_no_lidar_gate.py`, `no_lidar_posthoc.json`).

**Tree height is the likely cause.** Copernicus GLO-30 measures the top of the surface, including trees. On the Satilla, ground the estimate calls flooded sits at a median 0.4 m *below* the river by lidar, but 4.9 m *above* it by Copernicus. So v4's limit of 6 m above the river throws out much of the flooded forest.

**Removing the limit looks like a fix, and it isn't.** The same v4 rule, with the limit loosened on Copernicus heights:

| Height limit | Mean CSI | Satilla Oct 15 CSI | Satilla map size | Share of Satilla map the estimate can check |
|---|---|---|---|---|
| 6 m (frozen) | 0.25 | 0.42 | 5,222 ha | 31% |
| 10 m | 0.33 | 0.58 | 8,004 ha | 29% |
| None | 0.38 | 0.78 | 15,265 ha | 22% |

With no limit, the mean matches NISAR with lidar, but the score hides a problem:
- **The maps grow far beyond the estimated flood:** up to 30,930 ha on the Ochlockonee, 32,789 ha on the Pee Dee and 48,010 ha on the lower Sabine.
- **Most of each map can't be checked.** Only 4–22% of it has a label. The estimate only marks ground up to 5 m above the water as dry, and only inside its corridor, so errors further out don't count.
- **Some of it is very likely wrong.** Thousands of hectares sit on ground more than 5 m above the water: 4,707 ha on the Ochlockonee and 4,097 ha on the Neuse.

Some of that extra area could be real flooding on tributaries, which the estimate doesn't cover. This check can't separate the two. Either way, a no-limit score can't be used as evidence that the method doesn't need elevation data.

## What can be claimed

**Supported:** "On seven US passes, a method using no lidar in its map averaged 0.25 against 0.22 for a global height map, winning on four passes and losing on two."

**Must accompany it:** the height map would average 0.31 at the best limit for each pass, and the test removed lidar from the map but still used gauges for the valley line and the scoring.

**Not supported:** that radar is more accurate than global elevation data everywhere, that this holds in the tropics, or that the method needs no elevation data.

## What to test next

A global elevation model that removes trees, such as FABDEM, should address the likely cause. It needs a new frozen test. Its non-commercial license would also need checking against the project's open-source terms.

**Done:** see `BARE_EARTH_RESULTS.md`. With FABDEM in place of Copernicus, NISAR's mean rose from 0.25 to 0.35, within 0.03 of the lidar version ("partly supported" under that test's fixed rule).
