"""DEVELOPMENT ONLY: second settings grid for method v2 (adds ΔHH smoothing), on the four spent pairs."""
import itertools
import json

import numpy as np
from dev_selfcal import CACHE, PAIRS, build

from hidden_floods.detect import PairFeatures
from hidden_floods.metrics import score
from hidden_floods.selfcal import SelfCalRule, gauge_supported, height_above_river

data = {p: build(*p) for p in PAIRS}
feats = {p: PairFeatures(d["hh_dry"], d["hv_dry"], d["hh_wet"], d["hv_wet"]) for p, d in data.items()}
hands = {p: height_above_river(d["dem"], d["dist"], d["chain"]) for p, d in data.items()}
sup = {p: gauge_supported(d["chain"], d["g_chain"], 10000.0) for p, d in data.items()}
rows = []
for sm, q, hm in itertools.product((1, 3, 5), (80.0, 85.0, 90.0, 95.0), (3.0, 4.0, 6.0)):
    rule = SelfCalRule(q=q, hand_max_m=hm, smooth_px=sm)
    r = {"smooth_px": sm, "q": q, "hand_max_m": hm}
    cs = []
    for p, d in data.items():
        pred, thr = rule.apply(feats[p], hands[p], d["dist"])
        s = score(pred, d["wet"], d["dry"], sup[p])
        r[p[1]] = (round(thr, 2), round(s.csi, 3), round(s.recall, 3), round(s.precision, 3))
        cs.append(s.csi)
    r["mean"], r["min"] = round(float(np.mean(cs)), 3), round(float(np.min(cs)), 3)
    rows.append(r)
(CACHE / "dev_grid2.json").write_text(json.dumps(rows, indent=1))
print("smooth q hand | (thr, csi, rec, prec) per pair: 076A 127D 105A 156D | mean min")
for r in sorted(rows, key=lambda r: (-r["min"], -r["mean"]))[:10]:
    print(r["smooth_px"], r["q"], r["hand_max_m"], "|", r["076A_oct17"], r["127D_oct21"], r["105A_jul03"], r["156D_jun25"], "|", r["mean"], r["min"])
