"""DEVELOPMENT ONLY: explore method v2 settings on the four spent pairs (Isaias 076A/127D, Pearl 105A/156D).

Builds features, distance/chainage, height above river and truth once per pair, caches them, then scores a grid of
v2 settings. Scores here are in-sample development numbers, not validation.
"""

import itertools
import json

import numpy as np

from hidden_floods.config import REPO_ROOT, load_site
from hidden_floods.detect import ChangeRule, pair_features
from hidden_floods.frozen import reference_water
from hidden_floods.io.dem import dem_on_grid
from hidden_floods.io.nisar import read_gcov
from hidden_floods.metrics import score
from hidden_floods.pipeline import analysis_grid, gauge_water_surfaces
from hidden_floods.selfcal import SelfCalRule, gauge_supported, height_above_river
from hidden_floods.truth import ValleyLine, hydraulic_truth, refine_centerline

PAIRS = [("choctawhatchee", "076A_oct17"), ("choctawhatchee", "127D_oct21"), ("pearl", "105A_jul03"), ("pearl", "156D_jun25")]
CACHE = REPO_ROOT / "outputs" / "dev_selfcal"
CACHE.mkdir(parents=True, exist_ok=True)


def build(site_name, pair_name):
    path = CACHE / f"{site_name}_{pair_name}.npz"
    if path.exists():
        return dict(np.load(path))
    site = load_site(site_name)
    grid = analysis_grid(site)
    pair = site.pairs[pair_name]
    f = pair_features(read_gcov(site.gcov_path(pair.dry), grid), read_gcov(site.gcov_path(pair.wet), grid))
    dem = dem_on_grid(site.dem_path, grid)
    channel = reference_water(site.operational_dir, grid)
    coarse = ValleyLine.from_lonlat(grid, site.valley_line)
    dist0, _ = coarse.project(*grid.meshgrid())
    line = refine_centerline(coarse, channel & (dist0 < site.corridor_m), grid)
    dist, chain = line.project(*grid.meshgrid())
    wse = gauge_water_surfaces(site, pair.wet_time)
    gxy = [grid.to_xy(g.lon, g.lat) for g in site.gauges]
    _, g_chain = line.project(*map(np.array, zip(*gxy)))
    t = hydraulic_truth(grid, dem, line, gxy, [wse[g.name] for g in site.gauges], site.corridor_m, site.margin_m,
                        site.max_dry_height_m, channel_seeds=channel)
    d = {"hh_dry": f.hh_dry, "hv_dry": f.hv_dry, "hh_wet": f.hh_wet, "hv_wet": f.hv_wet, "dem": dem, "dist": dist,
         "chain": chain, "wet": t.wet, "dry": t.dry, "g_chain": g_chain}
    np.savez_compressed(path, **d)
    return d


def main():
    data = {p: build(*p) for p in PAIRS}
    from hidden_floods.detect import PairFeatures
    rows = []
    hands = {p: height_above_river(d["dem"], d["dist"], d["chain"]) for p, d in data.items()}
    feats = {p: PairFeatures(d["hh_dry"], d["hv_dry"], d["hh_wet"], d["hv_wet"]) for p, d in data.items()}
    for support_km in (None, 10.0):
        for q, hand_max in itertools.product((90.0, 95.0, 97.5, 99.0), (4.0, 6.0, 8.0, 12.0)):
            rule = SelfCalRule(q=q, hand_max_m=hand_max)
            r = {"support_km": support_km, "q": q, "hand_max_m": hand_max}
            csis = []
            for p, d in data.items():
                pred, thr = rule.apply(feats[p], hands[p], d["dist"])
                region = gauge_supported(d["chain"], d["g_chain"], support_km * 1000) if support_km else None
                s = score(pred, d["wet"], d["dry"], region)
                r[f"{p[0][:5]}_{p[1]}"] = {"thr": round(thr, 2), "csi": round(s.csi, 3), "rec": round(s.recall, 3),
                                         "prec": round(s.precision, 3)}
                csis.append(s.csi)
            r["mean_csi"], r["min_csi"] = float(np.mean(csis)), float(np.min(csis))
            rows.append(r)
        # baseline: fixed 2 dB rule under the same truth region
        base = {"support_km": support_km, "baseline": "fixed 2 dB"}
        for p, d in data.items():
            region = gauge_supported(d["chain"], d["g_chain"], support_km * 1000) if support_km else None
            s = score(ChangeRule(2.0).apply(feats[p]), d["wet"], d["dry"], region)
            base[f"{p[0][:5]}_{p[1]}"] = {"csi": round(s.csi, 3), "rec": round(s.recall, 3), "prec": round(s.precision, 3)}
        rows.append(base)
    (CACHE / "dev_grid.json").write_text(json.dumps(rows, indent=1))
    for r in sorted([r for r in rows if "q" in r], key=lambda r: -r["min_csi"])[:8]:
        print(json.dumps(r))
    for r in rows:
        if "baseline" in r:
            print("BASELINE", json.dumps(r))


if __name__ == "__main__":
    main()
