"""DEVELOPMENT ONLY — method v3 on the six spent NISAR pairs (Choctawhatchee, Pearl, Tangipahoa).

Settings are chosen by leave-one-flood-out: for each river, the best setting on the OTHER two rivers is scored on
it. That nested estimate is the honest guide to transfer; the final setting (best on all three) is what would be
frozen. Nothing here touches the Yellow River.

    python scripts/dev_v3.py            # build caches (first run, slow) and run the grid
"""

import itertools
import json

import numpy as np

from hidden_floods.audit import truth_context
from hidden_floods.config import REPO_ROOT, data_root, load_site
from hidden_floods.detect import PairFeatures, pair_features
from hidden_floods.io.dem import dem_on_grid
from hidden_floods.io.gauges import usgs_series
from hidden_floods.io.nisar import read_gcov
from hidden_floods.pipeline import analysis_grid
from hidden_floods.selfcal import height_above_river
from hidden_floods.trust import gcov_incidence_on_grid, timing_class, worldcover_class, worldcover_on_grid
from hidden_floods.v3 import V3Rule, peak_envelope_wet, peak_stage_wse, score_v3

PAIRS = [("choctawhatchee", "076A_oct17"), ("choctawhatchee", "127D_oct21"), ("pearl", "105A_jul03"),
         ("pearl", "156D_jun25"), ("tangipahoa", "105A_jun21"), ("tangipahoa", "156D_jun25")]
CACHE = REPO_ROOT / "outputs" / "dev_v3"
MIN_COVERAGE = 0.6   # a setting must keep at least 60% of confirmed flooding inside its mapped area (mean over pairs)


def build(site_name, pair_name):
    path = CACHE / f"{site_name}_{pair_name}.npz"
    if path.exists():
        return dict(np.load(path))
    site = load_site(site_name)
    grid = analysis_grid(site)
    pair = site.pairs[pair_name]
    dem = dem_on_grid(site.dem_path, grid)
    ctx = truth_context(site, pair.wet_time, dem=dem, grid=grid)
    f = pair_features(read_gcov(site.gcov_path(pair.dry), grid), read_gcov(site.gcov_path(pair.wet), grid))
    t = ctx.truth
    wet_peak = peak_envelope_wet(site, grid, dem, ctx.line, ctx.permanent_water,
                                 peak_stage_wse(site, pair.dry_time, pair.wet_time))
    g_chain = np.asarray(ctx.gauge_chainage_m)
    nearest = np.argmin(np.abs(t.chainage_m[..., None] - g_chain), axis=-1)
    classes = np.array([timing_class(usgs_series(site.gauges_dir, g), pair.wet_time) for g in site.gauges], np.uint8)
    d = {"hh_dry": f.hh_dry, "hv_dry": f.hv_dry, "hh_wet": f.hh_wet, "hv_wet": f.hv_wet,
         "hand": height_above_river(dem, t.distance_m, t.chainage_m), "dist": t.distance_m,
         "wet": t.wet, "dry": t.dry, "wet_peak": wet_peak, "region": ctx.supported & ~ctx.permanent_water,
         "landcover": worldcover_class(worldcover_on_grid(data_root() / "worldcover", grid)),
         "timing": classes[nearest], "incidence": gcov_incidence_on_grid(site.gcov_path(pair.wet), grid)}
    CACHE.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **d)
    return d


def evaluate(rule, d, ambiguous_out=True):
    f = PairFeatures(d["hh_dry"], d["hv_dry"], d["hh_wet"], d["hv_wet"])
    flooded, mapped, thr = rule.apply(f, d["landcover"], d["timing"], d["hand"], d["dist"])
    amb = d["dry"] & d["wet_peak"] if ambiguous_out else None
    s = score_v3(flooded, mapped, d["wet"], d["dry"], d["region"], amb)
    full = score_v3(flooded, np.ones_like(mapped), d["wet"], d["dry"], d["region"], amb)
    return {"csi": s.csi, "recall": s.recall, "precision": s.precision, "coverage": s.coverage,
            "csi_full": full.csi, "thr": thr, "wet_ha": s.wet_ha}


def grid_rules():
    for sm, q, lc, ab, absr in itertools.product((1, 3), (80.0, 85.0, 90.0, 95.0), ((1, 2), (1, 2, 0)),
                                                 ((), (4,), (3, 4)), (None, (-6.0, 6.0), (-4.0, 8.0), (-2.0, 10.0))):
        yield V3Rule(q=q, smooth_px=sm, landcover=lc, abstain_timing=ab,
                     abs_hh_db=None if absr is None else absr[0], abs_ratio_db=None if absr is None else absr[1])


def rule_key(r):
    return f"sm{r.smooth_px} q{r.q:.0f} lc{''.join(map(str, r.landcover))} ab{''.join(map(str, r.abstain_timing)) or '-'} " \
           f"abs{'-' if r.abs_hh_db is None else f'{r.abs_hh_db:+.0f}/{r.abs_ratio_db:.0f}'}"


def main():
    data = {p: build(*p) for p in PAIRS}
    # What does the absolute rule have to separate? Flood-date HH and HH/HV of already-wet truth vs dry truth.
    for p, d in data.items():
        f = PairFeatures(d["hh_dry"], d["hv_dry"], d["hh_wet"], d["hv_wet"])
        w, dr = d["wet"] & d["region"] & (d["landcover"] == 1), d["dry"] & d["region"] & (d["landcover"] == 1)
        print(f"{p[0][:5]} {p[1]}: flooded-forest HH p50 {np.nanmedian(f.hh_wet[w]):.1f} dB, HH/HV p50 "
              f"{np.nanmedian(f.ratio_wet[w]):.1f} | dry-forest HH p50 {np.nanmedian(f.hh_wet[dr]):.1f}, "
              f"HH/HV p50 {np.nanmedian(f.ratio_wet[dr]):.1f} | ambiguous {(d['dry'] & d['wet_peak'] & d['region']).sum() * .25:,.0f} ha")
    rules = list(grid_rules())
    res = {rule_key(r): {p: evaluate(r, d) for p, d in data.items()} for r in rules}
    rivers = sorted({p[0] for p in PAIRS})

    def mean_over(key, river_set, m):
        vals = [res[key][p][m] for p in PAIRS if p[0] in river_set]
        return float(np.nanmean(vals))

    def best_on(river_set):
        ok = [k for k in res if mean_over(k, river_set, "coverage") >= MIN_COVERAGE]
        return max(ok, key=lambda k: mean_over(k, river_set, "csi"))

    print("\nLeave-one-flood-out (setting picked on the other two rivers, scored on the held-out one):")
    loo = {}
    for held in rivers:
        k = best_on([r for r in rivers if r != held])
        loo[held] = {"setting": k, **{m: mean_over(k, [held], m) for m in ("csi", "recall", "precision", "coverage", "csi_full")}}
        print(f"  {held:15s} {k:42s} CSI {loo[held]['csi']:.2f} (all pixels {loo[held]['csi_full']:.2f}) "
              f"recall {loo[held]['recall']:.2f} precision {loo[held]['precision']:.2f} coverage {loo[held]['coverage']:.2f}")
    v2like = rule_key(V3Rule(q=90.0, smooth_px=3, landcover=(1, 2, 0), abstain_timing=()))
    print(f"\nreference ~v2 settings with the v3 land-cover gate ({v2like}):")
    for held in rivers:
        print(f"  {held:15s} CSI {mean_over(v2like, [held], 'csi'):.2f} coverage {mean_over(v2like, [held], 'coverage'):.2f}")
    final = best_on(rivers)
    print(f"\nfinal (best on all three, coverage >= {MIN_COVERAGE}): {final}")
    for p in PAIRS:
        r = res[final][p]
        print(f"  {p[0]:15s} {p[1]}: CSI {r['csi']:.2f} recall {r['recall']:.2f} precision {r['precision']:.2f} "
              f"coverage {r['coverage']:.2f} thr {r['thr']:.2f} dB (wet {r['wet_ha']:,.0f} ha)")
    (CACHE / "dev_v3_results.json").write_text(json.dumps({"loo": loo, "final": final, "grid": {k: {f"{p[0]} {p[1]}": v for p, v in r.items()} for k, r in res.items()}}, indent=1, default=float))


if __name__ == "__main__":
    main()
