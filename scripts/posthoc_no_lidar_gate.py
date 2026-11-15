"""Post-hoc: did tree height in the global elevation model cost NISAR its recall? Writes research/no_lidar_posthoc.json.

This came after the one-time no-lidar run and changes none of its results. It repeats the unchanged v4 rule with the height limit loosened or removed,
on the same pixels. Any choice made from these numbers would be a new method that needs its own frozen test.
"""

import json
from dataclasses import replace

import numpy as np

from hidden_floods.audit import truth_context
from hidden_floods.config import REPO_ROOT, load_site
from hidden_floods.frozen_no_lidar import LAND, LIMIT_M, PASSES, global_dem
from hidden_floods.frozen_v3 import RECEIPT_V3, paired_csi_difference, settings_from
from hidden_floods.frozen_v4 import RECEIPT as RECEIPT_V4
from hidden_floods.frozen_v4 import rule_from
from hidden_floods.metrics import block_ids, score
from hidden_floods.selfcal import height_above_river

LIMITS_M = (6.0, 10.0, 15.0, 20.0, 1e9)
cfg = settings_from(json.loads(RECEIPT_V3.read_text()))
rule = rule_from(json.loads(RECEIPT_V4.read_text()))
rows = []
for river, pair in PASSES:
    site = load_site(river)
    z = np.load(REPO_ROOT / "outputs" / river / pair / "frozen_v4_layers.npz")
    ctx = truth_context(site, site.pairs[pair].wet_time)
    t = ctx.truth
    wet, dry, lc, scored = z["wet"], z["dry"], z["landcover"], z["region"] & z["mapped"]
    hand = height_above_river(global_dem(river, ctx.grid), t.distance_m, t.chainage_m)
    blocks = block_ids(t.chainage_m, cfg.block_m)
    height_map = np.isin(lc, LAND) & (hand < LIMIT_M)
    row = {"site": river, "pair": pair, "by_height_limit": {}}
    # How high does the global model put ground the lidar estimate calls flooded?
    row["wet_ground_global_hand_m"] = {f"p{q}": round(float(np.nanpercentile(hand[wet & scored], q)), 1) for q in (10, 50, 90)}
    row["wet_ground_lidar_hand_m"] = {f"p{q}": round(float(np.nanpercentile(z["hand"][wet & scored], q)), 1) for q in (10, 50, 90)}
    for m in LIMITS_M:
        pred = replace(rule, hand_max_m=m).apply(z["d_hh"], z["d_hv"], lc, z["timing"], hand, t.distance_m)["pred"]
        s = score(pred, wet, dry, scored)
        key = "none" if m > 1e6 else str(m)
        # The estimate only labels ground up to 5 m above the water as dry, so errors on higher ground go unscored.
        mapped_px, labelled_px = int((pred & scored).sum()), int((pred & scored & (wet | dry)).sum())
        high = pred & scored & (z["depth"] <= -site.max_dry_height_m)
        row["by_height_limit"][key] = {"csi": float(s.csi), "recall": float(s.recall), "precision": float(s.precision), "minus_global_map": paired_csi_difference(pred, height_map, wet, dry, blocks, scored, cfg.n_boot, cfg.seed),
                                       "mapped_ha": mapped_px * 0.25, "labelled_share_of_map": labelled_px / max(mapped_px, 1), "ha_more_than_5m_above_water": float(high.sum() * 0.25)}
    rows.append(row)
    print(river, pair, {k: (round(v["csi"], 3), round(v["recall"], 2), round(v["precision"], 2), round(v["mapped_ha"]), round(v["labelled_share_of_map"], 2), round(v["ha_more_than_5m_above_water"]), [round(x, 2) for x in v["minus_global_map"]["ci95"]]) for k, v in row["by_height_limit"].items() if k in ("6.0", "10.0", "none")}, flush=True)
(REPO_ROOT / "research" / "no_lidar_posthoc.json").write_text(json.dumps({"note": "Post-hoc. Doesn't replace the one-time results.", "passes": rows}, indent=1, default=float))
print("MEANS", {("none" if m > 1e6 else str(m)): round(float(np.mean([r["by_height_limit"]["none" if m > 1e6 else str(m)]["csi"] for r in rows])), 3) for m in LIMITS_M}, flush=True)
print("POSTHOC DONE", flush=True)
