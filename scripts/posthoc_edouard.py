"""POST-HOC checks of the frozen Edouard results (research/EDOUARD_RESULTS.md). Nothing here replaces them.

Asks how far a no-radar map gets with its height limit picked by looking at the truth, how much false alarm each pass
has, and whether removing the scene-wide upland shift, an idea born from the warning, would have helped. That last one
is exploration on spent data: it is not a method change and is not validated.
"""

import json

import numpy as np

from hidden_floods.config import REPO_ROOT
from hidden_floods.selfcal import smooth_nan
from hidden_floods.v3 import otsu_threshold


def csi(p, w, d):
    tp, fn, fp = (p & w).sum(), (~p & w).sum(), (p & d).sum()
    return float(tp / (tp + fn + fp)) if tp + fn + fp else float("nan")


out = {}
for river, pair in (("village_creek", "134A_sep03"), ("pine_island", "012D_sep07"), ("village_creek", "012D_sep07"), ("pine_island", "134A_sep03")):
    d = REPO_ROOT / "outputs" / river / pair
    z = np.load(d / "frozen_edouard_layers.npz")
    meta = json.loads((d / "frozen_edouard_metrics.json").read_text())
    r = z["region"] & z["mapped"]
    w, dry, pred, hand, lc, dhh = z["wet"] & r, z["dry"] & r, z["pred"], z["hand"], z["landcover"], z["d_hh"]
    limits = {h: csi(hand < h, w, dry) for h in np.arange(0.5, 8.01, 0.25)}
    best = max(limits, key=limits.get)
    eligible = np.isin(lc, (0, 1, 2)) & (hand < 6.0)
    row = {"csi": csi(pred, w, dry), "no_radar_best_height_m": float(best), "no_radar_best_csi": limits[best], "gate_only_csi": csi(eligible, w, dry),
           "flagged_on_wet_ha": float((pred & w).sum() * 0.25), "flagged_on_dry_ha": float((pred & dry).sum() * 0.25),
           "wet_ha": float(w.sum() * 0.25), "dry_ha": float(dry.sum() * 0.25),
           "median_change_wet_db": float(np.nanmedian(dhh[w])), "median_change_dry_db": float(np.nanmedian(dhh[dry])),
           "threshold_db": meta["v3_threshold_db"], "upland_hh_db": meta["upland_warning"]["upland_hh_db"]}
    if row["upland_hh_db"] is not None:      # exploration only: same Otsu rule on the change minus the upland shift
        change = smooth_nan(dhh - row["upland_hh_db"], 3)
        floor = eligible & np.isfinite(change)
        thr = max(otsu_threshold(change[floor]), 0.5)
        row["exploratory_upland_corrected"] = {"threshold_db": thr, "csi": csi(eligible & (change > thr) & z["mapped"], w, dry)}
    out[f"{river} {pair}"] = row
print(json.dumps(out, indent=1))
