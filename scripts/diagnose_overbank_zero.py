"""Post-hoc: why did the water estimate read 0 ha on the Alapaha and Withlacoochee? Writes research/overbank_zero_diagnosis.json.

Uses the layers saved by the one-time run, plus lidar and reference water. It reads no new radar and changes no frozen result. The second
estimate here starts connectivity from the gauges instead of from reference water, and its scores are post-hoc and never replace the first numbers.
"""

import json

import numpy as np

from hidden_floods.audit import truth_context
from hidden_floods.config import REPO_ROOT, load_site
from hidden_floods.frozen_v3 import RECEIPT_V3, settings_from
from hidden_floods.metrics import block_bootstrap, block_ids, score
from hidden_floods.truth import connected_to_channel

AREA = 0.25
SEED_RADIUS_M = 500.0
LIDAR_LIMIT_M, LIDAR_LANDCOVER = 2.0, (0, 1, 2)
PASSES = [("alapaha", "047A_oct15"), ("alapaha", "148A_oct22"), ("withlacoochee", "047A_oct15"), ("withlacoochee", "148A_oct10"), ("satilla", "047A_oct15"), ("st_marys", "098D_oct07"), ("ochlockonee", "026D_oct14")]
cfg = settings_from(json.loads(RECEIPT_V3.read_text()))


def scores(p, wet, dry, reg, chain):
    s = score(p, wet, dry, reg)
    ci = block_bootstrap(p, wet, dry, block_ids(chain, cfg.block_m), reg, n_boot=cfg.n_boot, seed=cfg.seed)["csi"] if s.tp + s.fn + s.fp > 0 else None
    return {"csi": round(s.to_dict(AREA)["csi"], 3), "ci95": ci}


out = {}
for river, pair in PASSES:
    site = load_site(river)
    ctx = truth_context(site, site.pairs[pair].wet_time)
    grid, t, perm = ctx.grid, ctx.truth, ctx.permanent_water
    z = np.load(REPO_ROOT / "outputs" / river / pair / "frozen_v4_layers.npz")
    depth, pred, mapped, lc, hand, chain = z["depth"], z["pred"], z["mapped"], z["landcover"], z["hand"], z["chainage"]
    below, above_margin = t.corridor & (depth > 0), t.corridor & (depth > site.margin_m)
    X, Y = grid.meshgrid()
    gauge_dist = {}
    near = np.zeros(depth.shape, bool)
    rows, cols = np.nonzero(perm)
    for g in site.gauges:
        gx, gy = grid.to_xy(g.lon, g.lat)
        near |= np.hypot(X - gx, Y - gy) <= SEED_RADIUS_M
        gauge_dist[g.name] = round(float(np.min(np.hypot(grid.xs[cols] - gx, grid.ys[rows] - gy))), 0) if rows.size else None
    gauge_seeded = connected_to_channel(below, near & below) & above_margin
    region = ctx.supported & ~perm
    scored = region & mapped

    lidar = np.isin(lc, LIDAR_LANDCOVER) & (hand < LIDAR_LIMIT_M)
    out.setdefault(river, {})[pair] = {
        "reference_water_seeds_below_water_px": int((perm & below).sum()),
        "nearest_reference_water_to_gauge_m": gauge_dist,
        "supported_ha_depth_over_margin_any_connection": float((above_margin & region).sum() * AREA),
        "frozen_estimate_ha": float((t.wet & region).sum() * AREA),
        "gauge_seeded_estimate_ha": float((gauge_seeded & region).sum() * AREA),
        "gauge_seeded_estimate_mapped_ha": float((gauge_seeded & scored).sum() * AREA),
        "gauge_seeded_coverage": float((gauge_seeded & scored).sum() / max((gauge_seeded & region).sum(), 1)),
        "gauge_seeded_wet_share": float((gauge_seeded & scored).sum() / max(((gauge_seeded | t.dry) & scored).sum(), 1)),
        "posthoc_v4": scores(pred, gauge_seeded, t.dry, scored, chain),
        "posthoc_lidar": scores(lidar, gauge_seeded, t.dry, scored, chain),
    }
    print(river, pair, json.dumps(out[river][pair], default=str), flush=True)
(REPO_ROOT / "research" / "overbank_zero_diagnosis.json").write_text(json.dumps(out, indent=1, default=str))
print("DIAGNOSIS DONE", flush=True)
