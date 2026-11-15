# Independent check 2 results: water through the canopy in NOAA aerial photos

**Rules:** `INDEPENDENT_AERIAL_PROTOCOL.md`, SHA-256 `aeb6445223f909d3db81a3c878cebcd355e90828f675ef361dd30201a2fe680f` at analysis, unchanged then; `58c3777954b0f669362adf37eedc830f6fa901441f3962d06c05b14b2e89c3ad` after dates were removed. It was not in a commit before the run. Data: `independent_aerial_results.json`, `independent_aerial_points.json`. Scripts: `scripts/independent_aerial_prepare.py`, `scripts/independent_aerial_analyze.py`. Saved sheets, the key and reviews: `outputs/independent_aerial/`.

**No frozen score changes.** Reviewers were two new AI vision agents, blind to river, stratum and hypothesis. They aren't trained photo-interpreters.

## Answer

**These photos didn't show that radar-flagged forest holds more water than other forest.** All fixed comparisons read **not supported by this check**. Forest at least 10 m above the river, chosen as a negative control, scored about the same as radar-flagged forest.

**This doesn't refute the radar.** The photos can't separate water from shadow under this canopy, and they were taken 4–5 days before the radar pass. The question is still open.

## Reviews

127 points, with class kappa 0.40 (57% agreement) and score kappa 0.47 (65% exact, 100% within one step). Agreement is weaker than in round 1, and the reviewers differ a lot on `FLOOD`: one used it 17 times, and the other once.

| Stratum | Points | Consensus FLOOD | PERMANENT | DRY | CANOPY | UNSURE | Water sign (95% interval) | Mean score |
|---|---|---|---|---|---|---|---|---|
| A flagged, estimate wet | 24 | 0 | 4 | 0 | 17 | 3 | 4 (17%, 7–36%) | 0.79 |
| E not flagged, estimate wet | 7 of 24 | 0 | 1 | 0 | 2 | 4 | 1 (14%, 3–51%) | 1.07 |
| F not flagged, estimate dry | 24 | 1 | 1 | 2 | 4 | 16 | 3 (13%, 4–31%) | 0.96 |
| D flagged, beyond corridor | 24 | 0 | 3 | 0 | 3 | 18 | 4 (17%, 7–36%) | 0.98 |
| G not flagged, beyond corridor | 24 | 0 | 0 | 3 | 6 | 15 | 0 (0%, 0–14%) | 0.79 |
| H high-ground control | 24 | 0 | 0 | 4 | 2 | 18 | 3 (13%, 4–31%) | 0.83 |

Stratum E fell short because only 360 pixels qualified, and spacing rules removed most of them. No stratum had 10 decidable points, so there is no claim from consensus classes.

## Fixed readings

| Reading | Result | Outcome |
|---|---|---|
| 1. Does the score mean anything? | H 3 of 24, 12.5%, under the 20% limit | Interpretable under the rule |
| 2. Flags beyond the corridor | D vs G: +0.17 (−0.00 to +0.36). D vs H: +0.04 (−0.17 to +0.25) | **Not supported by this check** |
| 3. Flags inside the corridor | A vs F: +0.04 (−0.17 to +0.25) | **Not supported by this check** |
| 4. Estimate alone | E vs F: +0.02 (−0.20 to +0.40) | **Not supported by this check** |
| 5. Radar beyond the estimate | A vs E: +0.02 (−0.36 to +0.25) | Descriptive, no difference |

## Post-hoc audit, not blind

This came after unblinding. It changes no reading.

- **What the water signs in flagged strata were.** All 4 in A and 3 of 4 in D were consensus `PERMANENT`, meaning channels or ponds in the box. Leaving out consensus `PERMANENT` gives A 0, E 0, F 2, D 1, G 0 and H 3. So flagged forest had no more non-channel water signs than high ground, and fewer in this small sample.
- **Why the control triggered.** The three H points lie 30–36 m above the river, where river flooding isn't plausible, and all came from mission `20261011b`. Viewed directly, they show pale crowns over a smooth blue floor, much like points that look flooded. So that appearance isn't reliable evidence of water in these photos. The cause may be shadow, haze or color balance. Which one wasn't tested.
- **Single-reviewer `FLOOD` calls don't track the strata.** They fell in G 5, F 5, H 4, A 1, D 1 and E 1. High ground got more than flagged forest.
- **Some flagged ground beyond the corridor sits on small channels.** 3 of 24 D points had water in the box in both panels, against 0 of 24 in G. This could mean some beyond-corridor flags track tributaries, or that they brighten at channel edges. It wasn't a fixed comparison, and the numbers are small.
- **One consensus `FLOOD` is on estimate-dry ground.** Point 266056 is usually a pale sandy clearing and appears dark and smooth in the event photo. It could be missed water or a cloud shadow. One point isn't evidence either way.

## Limits

- **Timing:** flights came 4–5 days before radar, when stage at Milton was about 0.5–0.6 m lower. Water could arrive after the flights.
- **One flood and river:** lower Yellow only, and not held out from development.
- **Reviewers:** AI agents, with modest agreement. An expert interpreter may see more.
- **Different photos:** missions differ in sun and color, which isn't balanced across strata.
- **Water score:** added for this round, and tested here for the first time.

## What can be claimed

**Supported:** "In NOAA's aerial photos of the lower Yellow River, reviewers couldn't separate water from shadow under forest canopy, and high-ground forest scored about the same as radar-flagged forest."

**Not supported:** that these photos confirm or refute NISAR's under-canopy mapping, or that flags beyond the corridor are right or wrong.
