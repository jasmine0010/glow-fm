"""POST-HOC stress checks of the frozen Yellow River result (research/V3_YELLOW_RESULTS.md). Nothing here replaces it.

Truth comes from the same lidar DEM as the height gate, so a good score could partly be geometry. This asks how far a
map with no radar at all gets, with its height limit picked by looking at the truth (an unfairly generous benchmark),
and whether the score is carried by one reach.
"""

import itertools
import json
import sys
from pathlib import Path

import numpy as np

from hidden_floods.audit import truth_context
from hidden_floods.config import REPO_ROOT, load_site
from hidden_floods.detect import pair_features
from hidden_floods.io.nisar import read_gcov
from hidden_floods.pipeline import analysis_grid
from hidden_floods.v3 import V3OtsuRule


def csi(p, w, d):
    tp, fn, fp = (p & w).sum(), (~p & w).sum(), (p & d).sum()
    return float(tp / (tp + fn + fp)) if tp + fn + fp else float("nan")


def check(path: Path) -> dict:
    z = np.load(path)
    region = z["region"] & z["mapped"]
    w, d, pred, hand, chain = z["wet"] & region, z["dry"] & region, z["pred"], z["hand"], z["chainage"]
    rows = {f"{h:.1f}": csi(hand < h, w, d) for h in np.arange(0.5, 8.01, 0.25)}
    best = max(rows, key=rows.get)
    eligible = np.isin(z["landcover"], (0, 1, 2)) & (hand < 6.0)
    blocks = np.floor(chain / 2000.0).astype(int)
    labelled = w | d
    used = np.unique(blocks[labelled])
    edges = np.quantile(chain[labelled], [0, 0.25, 0.5, 0.75, 1])
    reaches = []
    for lo, hi in itertools.pairwise(edges):
        s = (chain >= lo) & (chain <= hi)
        reaches.append({"km": [round(lo / 1000, 1), round(hi / 1000, 1)], "wet_ha": float((w & s).sum() * 0.25),
                        "dry_ha": float((d & s).sum() * 0.25), "csi": csi(pred, w & s, d & s),
                        "no_radar_csi": csi(hand < float(best), w & s, d & s)})
    return {"csi": csi(pred, w, d), "no_radar_best_height_m": float(best), "no_radar_best_csi": rows[best],
            "gate_only_csi": csi(eligible, w, d), "blocks_with_labels": len(used),
            "wet_ha": float(w.sum() * 0.25), "dry_ha": float(d.sum() * 0.25), "reaches": reaches}


def without_height_gate(site_name: str, pair_name: str, layers: Path) -> dict:
    """Does the score depend on the lidar height gate? Same radar and land cover, with the gate removed."""
    z = np.load(layers)
    site = load_site(site_name)
    grid = analysis_grid(site)
    pair = site.pairs[pair_name]
    feats = pair_features(read_gcov(site.gcov_path(pair.dry), grid), read_gcov(site.gcov_path(pair.wet), grid))
    dist = truth_context(site, pair.wet_time, grid=grid).truth.distance_m
    open_rule = V3OtsuRule(hand_max_m=np.inf, landcover=(1, 2, 0))
    region = z["region"] & z["mapped"]
    w, d = z["wet"] & region, z["dry"] & region
    pred_open, _, thr = open_rule.apply(feats, z["landcover"], z["timing"], z["hand"], dist)
    return {"otsu_threshold_db_no_gate": thr, "csi_no_gate_otsu_recomputed": csi(pred_open, w, d)}


paths = [Path(p) for p in sys.argv[1:]] or [REPO_ROOT / "outputs/yellow/055D_oct16/frozen_v3_layers.npz"]
out = {str(p.parent.name): check(p) for p in paths}
out["055D_oct16"]["without_height_gate"] = without_height_gate("yellow", "055D_oct16", paths[0])
print(json.dumps(out, indent=1))
