"""Radar against a static lidar map with its height limit fixed first (research/STATIC_BASELINE.md).

Writes research/static_baseline.json. The truth uses the same lidar, so the static map starts with an advantage.
"""

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from dev_v4 import ALL, load_pass

from hidden_floods.config import REPO_ROOT
from hidden_floods.v4 import LOW_MAX_M, V4Rule

SCORED = [*ALL, ("isaias", "yellow", "127D_oct21")]
FROZEN_V4 = (("pee_dee", "098D_jul27"), ("neuse", "090A_jul26"), ("lower_sabine", "134A_jul17"))
LIMITS = (LOW_MAX_M, 1.0, 3.0)
FOREST_LC = (0, 1, 2)


def csi(p, w, d):
    tp, fn, fp = (p & w).sum(), (~p & w).sum(), (p & d).sum()
    return float(tp / (tp + fn + fp)) if tp + fn + fp else None


def row(pred, mapped, wet, dry, region, hand, lc, dist, storm, river, pair, role):
    r = region & mapped
    w, d = wet & r, dry & r
    corridor = region & (dist < 4000.0) if dist is not None else region
    static = {h: np.isin(lc, FOREST_LC) & (hand < h) for h in LIMITS}
    out = {"storm": storm, "river": river, "pair": pair, "role": role, "estimated_ha": float(w.sum() * 0.25), "dry_ha": float(d.sum() * 0.25),
           "radar_csi": csi(pred, w, d), "radar_ha": float((pred & corridor).sum() * 0.25), "radar_on_dry_ha": float((pred & d).sum() * 0.25),
           "static_ha": float((static[LOW_MAX_M] & corridor).sum() * 0.25), "static_on_dry_ha": float((static[LOW_MAX_M] & d).sum() * 0.25)}
    for h in LIMITS:
        out[f"static_csi_{h:g}m"] = csi(static[h], w, d)
    return out


def main():
    rule, rows = V4Rule(), []
    for storm, river, pair in SCORED:
        d, _ = load_pass(river, pair)
        r = rule.apply(d["hh_wet"] - d["hh_base"], d["hv_wet"] - d["hv_base"], d["landcover"], d["timing"], d["hand"], d["dist"])
        rows.append(row(r["pred"], r["mapped"], d["wet"], d["dry"], d["region"], d["hand"], d["landcover"], d["dist"], storm, river, pair, "development"))
        print(rows[-1], flush=True)
    for river, pair in FROZEN_V4:
        z = np.load(REPO_ROOT / "outputs" / river / pair / "frozen_v4_layers.npz")
        rows.append(row(z["pred"], z["mapped"], z["wet"], z["dry"], z["region"], z["hand"], z["landcover"], None, "fresh", river, pair, "frozen v4"))
        print(rows[-1], flush=True)
    judged = [r for r in rows if r["estimated_ha"] >= 500 and r["radar_csi"] is not None]
    key = f"static_csi_{LOW_MAX_M:g}m"
    summary = {"judgeable_passes": len(judged), "radar_mean": float(np.mean([r["radar_csi"] for r in judged])), "static_mean": float(np.mean([r[key] for r in judged])),
               "radar_wins": sum(r["radar_csi"] > r[key] for r in judged), "static_wins": sum(r["radar_csi"] < r[key] for r in judged)}
    print(summary, flush=True)
    (REPO_ROOT / "research" / "static_baseline.json").write_text(json.dumps({"rule_limit_m": LOW_MAX_M, "summary": summary, "passes": rows}, indent=1))
    print("STATIC DONE", flush=True)


if __name__ == "__main__":
    main()
