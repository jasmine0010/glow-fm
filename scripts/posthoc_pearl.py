"""POST-HOC diagnostics of the frozen Pearl River run (does not change the frozen result).

Questions: is the miss concentrated where the swamp was already wet on the dry reference date (change detection
cannot see that)? Where along the river? What do ΔHH values of missed truth pixels look like?
"""

import itertools
import json
import sys

import numpy as np

from hidden_floods.config import REPO_ROOT, load_site
from hidden_floods.io.dem import dem_on_grid
from hidden_floods.pipeline import analysis_grid, gauge_water_surfaces
from hidden_floods.truth import ValleyLine, interpolate_wse

site = load_site("pearl")
pair_name = sys.argv[1] if len(sys.argv) > 1 else "105A_jul03"
pair = site.pairs[pair_name]
out = REPO_ROOT / "outputs" / site.name / pair_name
L = np.load(out / "frozen_layers.npz")
pred, wet, dry, chain, d_hh, corridor = (L[k] for k in ("pred", "wet", "dry", "chainage", "d_hh", "corridor"))
grid = analysis_grid(site)
dem = dem_on_grid(site.dem_path, grid)
line = ValleyLine(L["line_x"], L["line_y"])
_, g_chain = line.project(*map(np.array, zip(*[grid.to_xy(g.lon, g.lat) for g in site.gauges])))
wse_dry = gauge_water_surfaces(site, pair.dry_time)
depth_dry = interpolate_wse(chain, g_chain, [wse_dry[g.name] for g in site.gauges]) - dem

m = site.margin_m
already = wet & (depth_dry > -m)
new = wet & (depth_dry < -m)
area = grid.pixel_area_ha
res = {"note": "POST-HOC; frozen result unchanged", "pair": pair_name,
       "dry_wse_navd88_m": wse_dry,
       "truth_wet_ha": float(wet.sum() * area),
       "already_wet_on_dry_date_ha": float(already.sum() * area),
       "recall_already_wet": float((pred & already).sum() / max(already.sum(), 1)),
       "newly_flooded_ha": float(new.sum() * area),
       "recall_newly_flooded": float((pred & new).sum() / max(new.sum(), 1)),
       "median_dHH_newly_flooded_db": float(np.nanmedian(d_hh[new])) if new.any() else None,
       "median_dHH_already_wet_db": float(np.nanmedian(d_hh[already])) if already.any() else None,
       "by_reach": []}
for name, s0 in zip([g.name for g in site.gauges], g_chain):
    pass
edges = np.sort(g_chain)
for a, b in itertools.pairwise(edges):
    sel = (chain >= a) & (chain < b)
    w, n = wet & sel, new & sel
    res["by_reach"].append({"chainage_km": [round(a / 1000, 1), round(b / 1000, 1)],
                            "truth_wet_ha": float(w.sum() * area), "recall": float((pred & w).sum() / max(w.sum(), 1)),
                            "newly_flooded_ha": float(n.sum() * area),
                            "recall_newly_flooded": float((pred & n).sum() / max(n.sum(), 1))})
for t in (1.0, 1.5, 2.0):
    p2 = (pred | True) & np.isfinite(d_hh) & (d_hh > t)
    res[f"posthoc_recall_newly_flooded_if_dHH>{t}"] = float((p2 & new).sum() / max(new.sum(), 1))
(out / "posthoc_diagnostics.json").write_text(json.dumps(res, indent=2))
print(json.dumps(res, indent=2))
