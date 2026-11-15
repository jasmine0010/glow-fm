# What today's flood maps showed on the Satilla

**Run after the one-time overbank test, and separate from it** (`scripts/audit_satilla.py`, `satilla_audit.json`). It uses the settings in `BLIND_SPOT_AUDIT.md`. Flood layers are kept in their own folder, so the reference water behind the frozen result doesn't change.

## Answer

**GFM lists no scene covering this stretch between Sep 30 and Oct 24, so it has no map of the Oct 15 NISAR pass or the days around it. On Oct 24, the first scene that covers it, gauges and lidar estimate 1,149 ha of flooding, and GFM mapped 0 ha of it.**

| GFM day | Corridor covered | Estimated flooding | GFM mapped | OPERA DSWx-S1 mapped |
|---|---|---|---|---|
| Sep 25 | 0% | | | |
| Sep 30 (before the flood) | 89% | 0 ha | 0 ha | |
| Oct 5 | 0% | | | |
| Oct 17 | 0% | | | |
| **Oct 24** | **89%** | **1,149 ha** | **0 ha** | **15 ha (1.3%)** |
| Oct 29 | 0% | | | |
| Oct 31 | 0% | | | |

**On Oct 24:**
- 94% of the estimated flooding is under tree cover.
- 97% of it lies inside GFM's exclusion mask, against 88% of estimated dry ground in the same corridor. So the mask's size explains much of this.
- 34 ha of the flooding lies outside the mask, and GFM mapped none of that.
- Missed flooding covers 8.2 km of mapped road, 6.8 km of it tracks, and no mapped buildings. These counts rely on OpenStreetMap and use a single date.

## Limits

- **Oct 24 is nine days after the NISAR pass.** By then the upstream gauges had fallen, so this is the same flood at a later stage. The two dates can't be scored against each other.
- **Oct 24 narrowly misses the 90% coverage rule written into the script (89%), so no date qualifies as primary.** It is reported because it is the only date that covers the flood. Only covered ground is counted.
- **"No scene covering" refers to GFM's catalog.** This check didn't establish why. Other Sentinel-1 data may exist.
- **The estimate can miss flooding on narrow rivers** (`OVERBANK_RESULTS.md`), and it is an estimate and not an observation.
- **One river and one date.** This adds to the audit in `BLIND_SPOT_AUDIT.md` and doesn't change it.
