# Third-event (held-out) results: method v2 on the Tangipahoa River (Tropical Storm Arthur)

Protocol: `THIRD_EVENT_PROTOCOL.md`. Receipt: `freeze_receipt_v2.json`. The integrity check at run time reported **no changes** to any hashed module. Raw outputs are in `outputs/tangipahoa/<pair>/frozen_v2_metrics.json`, written once.

## Frozen result (reported as is)

| Pair | Truth wet / dry, gauge-supported (ha) | v2 threshold | **v2 CSI (95% CI)** | v2 recall / precision | v1 (2 dB) CSI |
|---|---|---|---|---|---|
| **Primary: 105A Jun 21 vs Aug 20** | 2,425 / 16,688 | 1.61 dB | **0.29 (0.08–0.38)** | 0.48 / 0.43 | 0.21 (0.08–0.27) |
| Secondary: 156D Jun 25 vs Aug 12 | 85 / 15,220 | 1.30 dB | 0.006 (0.00–0.02) | 0.07 / 0.006 | 0.01 |

On the full corridor (secondary metric), v2 on the primary pair scores CSI 0.29, essentially the same as in the supported region.

## Reading it honestly

- **v2 is better than v1 on a river neither was tuned on:** CSI 0.29 against 0.21, and recall 0.48 against 0.36. The interval is wide (0.08–0.38) because there is little flooded truth.
- **Absolute accuracy is poor, and this time precision is the problem too (0.43).** At Pearl, v1 was precise but missed most of the flood. Here v2 also raises false alarms.
- **The secondary pair can't be judged.** By Jun 25 the river was almost back in its banks: only 85 ha of supported truth was still wet. So nearly every flagged pixel counts as a false alarm by definition. The protocol didn't require the wet scene to be near the crest, and this shows that it should.
- **Both wet scenes were on the falling limb**, as noted in advance. The crest was Jun 17–19, and NISAR PROVISIONAL data starts Jun 17, with the first usable pass on Jun 21.

## Post-hoc check (does not change the result)

Output: `outputs/tangipahoa/105A_jun21/posthoc_v2.json`.

- About 1,575 ha of false alarms against 1,163 ha of hits in the supported region.
- **Most false alarms (1,090 ha) sit 2–5 m above the river's Jun 21 water surface.** Only 112 ha sit 0.5–1 m above it. So they are mostly not truth errors near the water line. They are detector false alarms, or water that truth can't represent. Likely causes:
  - water ponded in the floodplain after the river fell (it crested 0.6–1.4 m higher three days earlier);
  - farmland and pasture changing between June and August (the upper Tangipahoa floodplain is partly farmed);
  - soil-moisture changes.
- **Activity is concentrated in the lower reach (Robert–Ponchatoula).** The upper reach had almost no flooded truth left by Jun 21.

## Overall picture after three events

| Event (role) | Best honest CSI | Notes |
|---|---|---|
| Isaias, Choctawhatchee FL (development) | 0.67 (0.61–0.73), lower reach | Near the crest, swamp forest, clean dry reference |
| Pearl, LA/MS (held out for v1) | 0.23 (0.17–0.30) with v1 | Weaker double-bounce change (+1.0 dB); 39 km truth gap |
| Tangipahoa, LA (held out for v2) | 0.29 (0.08–0.38) with v2 | Falling limb, mixed forest and farmland |

**Conclusion for the project:**
- NISAR's L-band change clearly sees flooded forest where operational maps are blind. At Isaias, 99% of NISAR's flooded forest lay inside GFM's exclusion mask.
- But simple change-detection accuracy is **strongly event-dependent**. It is good near the crest in swamp forest, and weak on falling limbs and in mixed land cover. Neither a fixed threshold (v1) nor a scene-calibrated one (v2) yet makes it reliable across events.
- Expert judges will value this finding when it comes with the three-event, pre-registered evaluation. It also sets the right claim: **a validated blind-spot detector for near-crest forest flooding, with honest, event-specific uncertainty**, not a general flood mapper.

## Next methodological options (would need pre-registration and a fourth event)

1. **Timing rule.** Require the wet scene to be within about 2 days of the crest at the nearest gauge, or to have a stage within about 20% of peak. This fixes the event-selection weakness exposed here.
2. **Peak-envelope truth.** Label "flooded at some point" from the crest water surface between the dry and wet dates. Score detections against both instantaneous and peak truth, which separates ponding after recession from false alarms.
3. **Land-cover forest mask** (for example WorldCover tree cover or the NLCD woody-wetland class) instead of the HV proxy. This should cut farmland false alarms.
4. **Multi-date reference.** Use the median of several dry dates instead of one, to reduce crop and phenology change.
