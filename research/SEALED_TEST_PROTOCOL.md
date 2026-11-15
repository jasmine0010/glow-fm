# Sealed test: the trust light on NISAR passes that haven't happened yet

**Written** before any of the passes it names was recorded, so nothing about them can have shaped it.
**Receipt:** `research/freeze_receipt_sealed.json` holds SHA-256 hashes of:
- this file;
- the sealed list (`research/sealed/sealed_<date>.json`);
- the sealing script and the scorer;
- the frozen live and v4 receipts they rest on.

The scorer refuses to run if any of them has changed. **The commit that adds them is the dated record.** Only a commit pushed before the first predicted pass is an independent timestamp.

## 1. The question
The trust signal was fixed in advance in `OVERBANK_PROTOCOL.md` §4: green predicts a match score (CSI) of 0.60 or higher, red predicts below 0.60. Its first fair test was right on 3 of 4 judgeable passes, which is "too few" under its own rule (at least 5 needed).

This test adds passes that **do not exist yet**, named before NISAR flies over them. So the method can't be tuned to them, and none can be dropped afterwards.

## 2. Which passes are sealed
The sealing script (`scripts/seal_next_passes.py`) runs once, at the sealing time written in the list.

**Gauges:** every NOAA river gauge at minor, moderate or major flood stage at that moment (`hidden_floods.live.us_candidates`, the frozen live code, unchanged). A gauge is used if:
- NOAA links it to a USGS gauge; and
- NOAA's record shows when the current flood began (`us_flood_window`).

**Stacks:** for each gauge, NISAR scenes over its point of the kind the method reads (40 MHz, HH and HV; `scenes_over`), grouped by stack. A stack is a track, direction, frame and mode, so its scenes can be compared pixel for pixel. A stack is used if it has **at least 3 passes in the 60 days before the flood began**: the live protocol's baseline rule.

**Predicted passes:** NISAR repeats each track every 12 days. Each used stack's predicted passes are its latest pass + 12 days × k, for every k landing between the sealing time and 24 days after it (one or two passes).

**Left out, with the reason recorded:** every gauge or stack left out, and why.

Nothing about a gauge's radar, estimate or score is read when sealing. Only catalog dates and NOAA's stage record are.

## 3. How a sealed pass is run and scored
The scorer is `scripts/score_sealed.py`. It is run whenever new passes may have reached NASA's catalog; NISAR's scenes take a median of about 2 days.

**Matching:** a sealed pass is **found** when a scene of the same stack, over the same point, begins within ±1 hour of the predicted time. If none has appeared 30 days after the predicted time, it is **missing**.

**Run:** a found pass is run once, with the frozen live code, exactly as `scripts/live_cases.py` runs a US case:
- the found scene is the flood pass;
- the baseline is the stack's passes in the 60 days before the flood began (the latest 6, at least 3);
- `live.prepare(..., score_it=True)`, then `live.run_rule` with the frozen v4 rule (`research/freeze_receipt_v4.json`);
- `live.score_case` with the frozen v3 settings (2 km blocks, 2,000 draws, seed 0).

**Trust light**, as in `OVERBANK_PROTOCOL.md` §4:
- **Green** if the v4 confidence label is High **and** the pass isn't rainy. **Red** otherwise.
- **Rainy** means at least 5 mm in the 24 hours or at least 25 mm in the 72 hours before the pass. Rain is the IMERG V07 Late Run mean over the case's box, read by the same IMERG reader as `RAINFALL.md` (`scripts/rain_imerg.py`).
- If IMERG can't be read, the pass is tried again at the next check. If it is still unreadable 30 days after the pass, the pass is recorded as **not judged: rain unknown**. Rain is never guessed.

**Judgeable**, as in `OVERBANK_PROTOCOL.md` §6:
- at least 500 ha of estimated flooding on scored ground; and
- coverage of at least 0.60: the share of estimated flooding, inside the gauge-supported region, that the radar mapped.

**Hit:** a judgeable pass is a hit when the light and the score agree: green and CSI ≥ 0.60, or red and CSI < 0.60.

**Nothing is dropped.** Every sealed pass stays in the results as one of:
- waiting;
- missing;
- not run (with the error);
- not judgeable (with the numbers);
- judged.

## 4. The reading, fixed now
The bars are `OVERBANK_PROTOCOL.md` §6's, unchanged. Hits are counted over judgeable passes, and compared with the two trivial rules (always green, always red) on the same passes.
- **Held up:** at least 5 judgeable passes, at least 80% hits, and more hits than either trivial rule.
- **Mixed:** at least 5 judgeable passes and at least 60% hits, without meeting the bar above.
- **Did not hold up:** at least 5 judgeable passes and under 60% hits.
- **Too few:** fewer than 5 judgeable passes.

**Primary reading:** the overbank test's judgeable passes, read from its frozen per-pass files, plus the judgeable sealed passes.
**Also reported:** the sealed passes alone.

## 5. What this can and can't say
- **It can say** whether the trust light, fixed before any of these passes existed, tells a user when to believe a NISAR flood map on US rivers.
- **It can't say** anything outside the US: there are no gauges or lidar there to judge against.
- **It may end as "too few".** Floods recede, passes are missed, and many US floods are under 500 ha. That outcome is reported as it is.
- **A single sealed pass** is one fresh test on one river.
- **Neighbouring gauges share ground.** One NISAR scene can cover several gauges on the same river. Each gauge's pass is run and counted on its own, as the live runs count cases, but those passes are not independent, and the results say so.
- **A temporary failure** (catalog, download or rainfall not yet readable) records nothing; the pass is tried again at the next check. Only a finished run is kept, and it is never run again. Rainfall still unreadable 30 days after the pass leaves it **not judged**.
