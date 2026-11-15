# Independent check 2: can water be seen through the canopy in NOAA aerial photos?

**Written** before any chip for this round was made or opened. The first round (`INDEPENDENT_CHECK_RESULTS.md`) has been seen, and its review notes prompted this design. Reviewers in this round are new and haven't seen those results.

**Weaker record:** this file's hash is recorded in the results, but it was not in a commit before the run.

**Question:** in forest on the lower Yellow River, do NOAA's Hurricane Isaias photos show water more often where radar flagged, including beyond the estimate's corridor?

## Why this round is different

- **Native resolution:** NOAA zoom 19 tiles, about 26 cm per pixel, with an enlarged view of the box. Round 1 used about 0.6 m.
- **Forest only:** every point has WorldCover tree cover, because under-canopy water is the question.
- **A negative control:** forest high above the river should almost never show river flooding.
- **A water score:** round 1 lost most points to `CANOPY`. Reviewers now also score signs of water at every point, and the control tests whether that score means anything.

## Case

Frozen v3 map, Yellow River, Oct 16 00:36 UTC, CSI 0.88. Photos are the same NOAA missions as round 1, Oct 11–12, preferring the latest mission with data at a point. **Timing limit:** the flights came 4–5 days before radar, and stage at Milton was about 0.5–0.6 m lower at the flights. So water seen is likely still present at radar, while no visible water doesn't refute a flag. This river isn't held out from the project's development.

## Points

Scored ground (`region & mapped`), inside flown bounds, WorldCover tree, 24 points per stratum, seed 20261107, at least 300 m apart within a stratum, at least 300 m from round 1 points, flown tile has data.

| Stratum | Definition |
|---|---|
| A flagged, estimate wet | flagged and labelled flooded |
| E not flagged, estimate wet | not flagged and labelled flooded |
| F not flagged, estimate dry | not flagged and labelled dry |
| D flagged, beyond corridor | flagged, outside the corridor |
| G not flagged, beyond corridor | not flagged, outside the corridor, under 6 m above the river |
| H high-ground control | not flagged, outside the corridor, at least 10 m above the river |

If a stratum has too few points, all are used and the shortfall is reported.

## Blind review

Points are shuffled with random IDs. Reviewers see no river, date, stratum, radar, estimate or hypothesis. Two new independent AI vision agents review each point. They aren't trained photo-interpreters.

**Class:** `FLOOD` water on the ground in the box, not shown as water in the usual panel. `PERMANENT` water in both. `DRY` ground visible without water. `CANOPY` crowns or shadow hide the ground. `UNSURE` anything else.

**Water score:** 0 no sign of water, 1 weak or ambiguous sign, 2 likely water, 3 clear water.

**Water sign** means both reviewers scored 2 or more. Agreement is reported with Cohen's kappa and, for the score, the share of points within one step.

## Fixed readings

Intervals are Wilson 95% for shares and Newcombe 95% for differences. All are descriptive.

**1. Does the score mean anything?** If stratum H's water-sign share is 20% or more, reviewers can't separate water from shadow in these photos. Every comparison below then reads **not interpretable**.

**2. Main question, flags beyond the corridor.** **Supported** only if water-sign share in D is above both G and H, with both intervals entirely above zero. Otherwise **not supported by this check**.

**3. Flags inside the corridor.** A against F, same rule. Radar and the estimate agree in A, so this tests them together.

**4. Estimate alone.** E against F.

**5. Radar beyond the estimate.** A against E. Descriptive.

**Also reported:** consensus `FLOOD` of decidable points per stratum, with no claim under 10 decidable points.

No frozen score changes, whatever this finds. Failing to find water doesn't refute radar. Water can be shallow, hidden or gone by the flight date, or not yet arrived.
