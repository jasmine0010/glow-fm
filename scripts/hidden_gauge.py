"""Hide each interior gauge and predict it from the others (research/HIDDEN_GAUGE.md). Writes research/hidden_gauge.json.

Uses gauges and lidar only. Changes no method.
"""

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from explore_model_ideas import get_site

from hidden_floods.audit import truth_context
from hidden_floods.config import REPO_ROOT
from hidden_floods.io.dem import dem_on_grid
from hidden_floods.pipeline import analysis_grid
from hidden_floods.truth import hydraulic_truth

PASSES = (("choctawhatchee", "076A_oct17"), ("choctawhatchee", "127D_oct21"), ("pearl", "105A_jul03"), ("pearl", "156D_jun25"), ("tangipahoa", "105A_jun21"), ("tangipahoa", "156D_jun25"),
          ("yellow", "055D_oct04"), ("yellow", "076A_oct05"), ("yellow", "127D_oct09"), ("yellow", "055D_oct16"), ("yellow", "076A_oct17"), ("yellow", "127D_oct21"),
          ("pee_dee", "098D_jul27"), ("neuse", "090A_jul26"), ("lower_sabine", "134A_jul17"))
MARGIN_M, FAIR_GAP_M, NEAR_M, MIN_WET_HA = 0.5, 40000.0, 10000.0, 50.0


def main():
    rows = []
    for river, pair_name in PASSES:
        site = get_site(river)
        pair = site.pairs[pair_name]
        grid = analysis_grid(site)
        dem = dem_on_grid(site.dem_path, grid)
        ctx = truth_context(site, pair.wet_time, dem=dem, grid=grid)
        names = [g.name for g in site.gauges]
        chain = np.array(ctx.gauge_chainage_m)
        wse = np.array([ctx.gauge_wse_m[n] for n in names])
        order = np.argsort(chain)
        gxy = [grid.to_xy(g.lon, g.lat) for g in site.gauges]
        full = ctx.truth
        for k in order[1:-1]:
            keep = order[order != k]
            pred = float(np.interp(chain[k], chain[keep], wse[keep]))
            left, right = chain[keep][chain[keep] < chain[k]].max(), chain[keep][chain[keep] > chain[k]].min()
            changed = wse.copy()
            changed[k] = pred
            alt = hydraulic_truth(grid, dem, ctx.line, gxy, changed.tolist(), site.corridor_m, site.margin_m, site.max_dry_height_m, channel_seeds=ctx.permanent_water)
            near = (np.abs(full.chainage_m - chain[k]) <= NEAR_M) & ~ctx.permanent_water
            a, b = full.wet & near, alt.wet & near
            area = grid.pixel_area_ha
            union = float((a | b).sum() * area)
            rows.append({"river": river, "pair": pair_name, "gauge": names[k], "neighbour_gap_km": round(float(right - left) / 1000, 1), "predicted_m": round(pred, 3), "measured_m": round(float(wse[k]), 3),
                         "error_m": round(pred - float(wse[k]), 3), "full_wet_ha": round(float(a.sum() * area), 1), "held_out_wet_ha": round(float(b.sum() * area), 1),
                         "agreement": round(float((a & b).sum() * area) / union, 3) if max(a.sum(), b.sum()) * area >= MIN_WET_HA else None})
            r = rows[-1]
            print(f"{river} {pair_name} {r['gauge'][:32]} gap {r['neighbour_gap_km']} km error {r['error_m']:+.2f} m wet {r['full_wet_ha']:.0f}/{r['held_out_wet_ha']:.0f} ha agreement {r['agreement']}", flush=True)

    def summary(rs):
        e = np.array([r["error_m"] for r in rs])
        ag = [r["agreement"] for r in rs if r["agreement"] is not None]
        return {"cases": len(rs), "median_abs_error_m": round(float(np.median(np.abs(e))), 3), "share_within_margin": round(float((np.abs(e) <= MARGIN_M).mean()), 3), "mean_signed_error_m": round(float(e.mean()), 3),
                "worst_abs_error_m": round(float(np.abs(e).max()), 3), "median_agreement": round(float(np.median(ag)), 3) if ag else None, "agreement_cases": len(ag)}

    fair = [r for r in rows if r["neighbour_gap_km"] * 1000 <= FAIR_GAP_M]
    rivers = sorted({r["river"] for r in rows})
    out = {"all": summary(rows), "gap_at_most_40_km": summary(fair) if fair else None, "by_river": {x: summary([r for r in rows if r["river"] == x]) for x in rivers}, "cases": rows}
    (REPO_ROOT / "research" / "hidden_gauge.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: out[k] for k in ("all", "gap_at_most_40_km", "by_river")}, indent=1), flush=True)
    print("HIDDEN GAUGE DONE", flush=True)


if __name__ == "__main__":
    main()
