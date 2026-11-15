"""POST-HOC checks of the frozen v4 results (research/V4_RESULTS.md). Nothing here replaces them.

Was this a test of flood mapping at all? Asks where "confirmed flooding" sits, whether radar responds to the river
level, how far a no-radar map gets with a height limit picked using the truth, and how much of the land was flagged.
"""

import json

import numpy as np

from hidden_floods.config import REPO_ROOT
from hidden_floods.selfcal import smooth_nan


def csi(p, w, d):
    tp, fn, fp = (p & w).sum(), (~p & w).sum(), (p & d).sum()
    return float(tp / (tp + fn + fp)) if tp + fn + fp else float("nan")


def auc(x, w, d):
    a, b = x[w], x[d]
    a, b = a[np.isfinite(a)], b[np.isfinite(b)]
    r = np.concatenate([a, b]).argsort().argsort() + 1.0
    return float((r[: a.size].sum() - a.size * (a.size + 1) / 2) / (a.size * b.size))


out = {}
for river, pair in (("pee_dee", "098D_jul27"), ("neuse", "090A_jul26"), ("lower_sabine", "134A_jul17")):
    z = np.load(REPO_ROOT / "outputs" / river / pair / "frozen_v4_layers.npz")
    r = z["region"] & z["mapped"]
    w, dry, pred, v3, hand, depth = z["wet"] & r, z["dry"] & r, z["pred"], z["v3_pred"], z["hand"], z["depth"]
    hh, hv = smooth_nan(z["d_hh"], 3), smooth_nan(z["d_hv"], 3)
    tree = z["landcover"] == 1
    limits = {float(h): csi(hand < h, w, dry) for h in np.arange(0.5, 8.01, 0.25)}
    best = max(limits, key=limits.get)
    curve = []
    for lo, hi in ((-3, -1), (-1, -0.5), (0.5, 1), (1, 2), (2, 3)):
        m = tree & r & (depth >= lo) & (depth < hi)
        curve.append({"water_above_ground_m": [lo, hi], "ha": float(m.sum() * 0.25), "hh_db": float(np.nanmedian(hh[m])) if m.sum() >= 40 else None, "hv_db": float(np.nanmedian(hv[m])) if m.sum() >= 40 else None})
    out[river] = {
        "confirmed_ha": float(w.sum() * 0.25), "confirmed_median_depth_m": float(np.nanmedian(depth[w])), "confirmed_share_depth_over_1m": float((depth[w] > 1.0).mean()),
        "confirmed_median_hand_m": float(np.nanmedian(hand[w])), "dry_ha": float(dry.sum() * 0.25), "v4_mapped_on_confirmed_ha": float((pred & w).sum() * 0.25), "v4_mapped_on_dry_ha": float((pred & dry).sum() * 0.25),
        "v3_mapped_on_dry_ha": float((v3 & dry).sum() * 0.25), "auc_hh": auc(hh, w, dry), "auc_hh_minus_hv": auc(hh - hv, w, dry), "no_radar_best_height_m": best, "no_radar_best_csi": limits[best],
        "response": curve,
    }
print(json.dumps(out, indent=1))
