"""EXPLORATION ONLY, on rivers already spent. Nothing here is a method change or a validated result.

Ranks ideas for the next method by asking, pass by pass:
- How well does each radar feature separate confirmed flooding from confirmed dry ground (AUC, threshold-free)?
- What does the same Otsu rule score on each feature?
- Can a bimodality measure say "no flood here"?
- How much signal can a radar-only model find on a storm it never trained on?
- Does interferometric coherence carry a signal?
Features exclude height above the river because the truth is built from the same lidar.
"""

import json
import sys

import numpy as np

from hidden_floods.audit import truth_context
from hidden_floods.config import REPO_ROOT, data_root, load_site
from hidden_floods.detect import pair_features
from hidden_floods.grid import Grid
from hidden_floods.io.dem import dem_on_grid
from hidden_floods.io.gauges import usgs_series
from hidden_floods.io.nisar import read_gcov, read_gunw_box
from hidden_floods.pipeline import analysis_grid
from hidden_floods.selfcal import height_above_river, smooth_nan
from hidden_floods.series import yellow_series_site
from hidden_floods.trust import timing_class, worldcover_class, worldcover_on_grid
from hidden_floods.v3 import otsu_threshold

CACHE = REPO_ROOT / "outputs" / "explore"
PASSES = [("isaias", "choctawhatchee", "076A_oct17"), ("isaias", "choctawhatchee", "127D_oct21"),
          ("isaias", "yellow", "076A_oct05"), ("isaias", "yellow", "127D_oct09"), ("isaias", "yellow", "055D_oct16"), ("isaias", "yellow", "076A_oct17"),
          ("arthur", "pearl", "105A_jul03"), ("arthur", "pearl", "156D_jun25"), ("arthur", "tangipahoa", "105A_jun21"),
          ("edouard", "village_creek", "134A_sep03"), ("edouard", "village_creek", "012D_sep07"),
          ("edouard", "pine_island", "012D_sep07"), ("edouard", "pine_island", "134A_sep03")]


def get_site(name):
    return yellow_series_site() if name == "yellow" else load_site(name)


def build(name, pair_name):
    path = CACHE / f"{name}_{pair_name}.npz"
    if path.exists():
        return dict(np.load(path))
    site = get_site(name)
    grid = analysis_grid(site)
    pair = site.pairs[pair_name]
    dem = dem_on_grid(site.dem_path, grid)
    ctx = truth_context(site, pair.wet_time, dem=dem, grid=grid)
    t = ctx.truth
    f = pair_features(read_gcov(site.gcov_path(pair.dry), grid), read_gcov(site.gcov_path(pair.wet), grid))
    classes = np.array([timing_class(usgs_series(site.gauges_dir, g), pair.wet_time) for g in site.gauges], np.uint8)
    timing = classes[np.argmin(np.abs(t.chainage_m[..., None] - np.asarray(ctx.gauge_chainage_m)), axis=-1)]
    out = {"hh_dry": f.hh_dry, "hv_dry": f.hv_dry, "hh_wet": f.hh_wet, "hv_wet": f.hv_wet, "wet": t.wet, "dry": t.dry,
           "hand": height_above_river(dem, t.distance_m, t.chainage_m), "dist": t.distance_m, "timing": timing,
           "landcover": worldcover_class(worldcover_on_grid(data_root() / "worldcover", grid)),
           "region": ctx.supported & ~ctx.permanent_water}
    CACHE.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **{k: (v.astype(np.float32) if v.dtype.kind == "f" else v) for k, v in out.items()})
    return out


def auc(x, wet, dry):
    a, b = x[wet], x[dry]
    a, b = a[np.isfinite(a)], b[np.isfinite(b)]
    if a.size < 40 or b.size < 40:
        return None
    ranks = np.concatenate([a, b]).argsort().argsort() + 1.0
    return float((ranks[: a.size].sum() - a.size * (a.size + 1) / 2) / (a.size * b.size))


def csi(p, w, d):
    tp, fn, fp = (p & w).sum(), (~p & w).sum(), (p & d).sum()
    return float(tp / (tp + fn + fp)) if tp + fn + fp else float("nan")


def bimodality(x):
    x = x[np.isfinite(x)]
    t = otsu_threshold(x)
    lo, hi = x[x <= t], x[x > t]
    if lo.size < 50 or hi.size < 50:
        return t, 0.0, 0.0
    ashman = float(np.sqrt(2) * abs(hi.mean() - lo.mean()) / np.sqrt(hi.var() + lo.var()))
    w0, w1 = lo.size / x.size, hi.size / x.size
    between = float(w0 * w1 * (hi.mean() - lo.mean()) ** 2 / x.var())
    return t, ashman, between


def features(d):
    hh, hv = d["hh_wet"] - d["hh_dry"], d["hv_wet"] - d["hv_dry"]
    s = lambda a: smooth_nan(a, 3)
    return {"dHH": s(hh), "dHV": s(hv), "dHH_minus_dHV": s(hh - hv), "HH_wet": s(d["hh_wet"]), "HHHV_ratio_wet": s(d["hh_wet"] - d["hv_wet"]),
            "HV_dry": s(d["hv_dry"]), "HV_wet": s(d["hv_wet"])}


def evaluate(d):
    f = features(d)
    valid = np.isfinite(f["dHH"]) & np.isfinite(f["dHV"])
    mapped = d["timing"] != 4
    eligible = valid & np.isin(d["landcover"], (0, 1, 2)) & (d["hand"] < 6.0)
    floor = eligible & (d["dist"] < 4000.0)
    r = d["region"] & mapped & eligible
    # scored the way v3 is scored: labelled pixels the gate removes still count as misses or correct rejections
    w_all, dry_all = d["wet"] & d["region"] & mapped, d["dry"] & d["region"] & mapped
    w, dr = d["wet"] & r, d["dry"] & r
    upland = valid & (d["landcover"] == 1) & (d["hand"] > 12.0) & (d["dist"] < 15000.0)
    row = {"wet_ha": float(w_all.sum() * 0.25), "dry_ha": float(dry_all.sum() * 0.25),
           "upland_dHH": float(np.median(f["dHH"][upland])) if upland.sum() >= 500 else None,
           "upland_dHV": float(np.median(f["dHV"][upland])) if upland.sum() >= 500 else None,
           "auc": {k: auc(v, w, dr) for k, v in f.items()}}
    for name in ("dHH", "dHH_minus_dHV"):
        t, ashman, between = bimodality(f[name][floor])
        thr = max(t, 0.5)
        row[name] = {"threshold": thr, "csi": csi(eligible & (f[name] > thr) & mapped, w_all, dry_all), "ashman_d": ashman, "between_share": between}
    row["both"] = {"csi": csi(eligible & (f["dHH"] > row["dHH"]["threshold"]) & (f["dHH_minus_dHV"] > row["dHH_minus_dHV"]["threshold"]) & mapped, w_all, dry_all)}
    # Is there flooding at all? Radar change on the lowest valley ground minus higher valley ground. Uses no gauge or truth.
    low, high = valid & (d["landcover"] == 1) & (d["hand"] < 2.0) & (d["dist"] < 4000.0), valid & (d["landcover"] == 1) & (d["hand"] > 4.0) & (d["hand"] < 8.0) & (d["dist"] < 4000.0)
    row["low_minus_high"] = {n: float(np.median(f[n][low]) - np.median(f[n][high])) if low.sum() >= 200 and high.sum() >= 200 else None for n in ("dHH", "dHH_minus_dHV")}
    return row, f, eligible, w_all, dry_all, mapped


def leave_one_storm_out(data):
    try:
        from sklearn.ensemble import HistGradientBoostingClassifier
        from sklearn.linear_model import LogisticRegression
    except ImportError as e:
        print(f"scikit-learn unavailable ({e!r}): skipping the model comparison", flush=True)
        return {}
    names = ("dHH", "dHV", "dHH_minus_dHV", "HH_wet", "HHHV_ratio_wet", "HV_dry", "HV_wet")
    rng = np.random.default_rng(0)
    pixels = {}
    for key, (_, f, eligible, w, dr, _) in data.items():
        m = eligible & (w | dr) & np.all([np.isfinite(f[n]) for n in names], axis=0)
        idx = np.flatnonzero(m)
        idx = rng.choice(idx, min(idx.size, 30000), replace=False)
        pixels[key] = (np.stack([f[n].ravel()[idx] for n in names], 1), w.ravel()[idx])
    out = {}
    for held in sorted({k[0] for k in data}):
        X = np.concatenate([pixels[k][0] for k in pixels if k[0] != held])
        y = np.concatenate([pixels[k][1] for k in pixels if k[0] != held])
        models = {"logistic": LogisticRegression(max_iter=500, class_weight="balanced").fit(X, y),
                  "boosted_trees": HistGradientBoostingClassifier(max_iter=120, learning_rate=0.08, max_leaf_nodes=15, class_weight="balanced", random_state=0).fit(X, y)}
        scale = X.std(axis=0)
        print(f"held out {held}: logistic weight per 1 sd", {n: round(float(c * s), 2) for n, c, s in zip(names, models["logistic"].coef_[0], scale, strict=True)}, flush=True)
        for key, (_, f, eligible, w, dr, mapped) in data.items():
            if key[0] != held:
                continue
            good = eligible & np.all([np.isfinite(f[n]) for n in names], axis=0) & mapped
            A = np.stack([f[n][good] for n in names], 1)
            for label, model in models.items():
                p = np.zeros(w.shape, bool)
                p[good] = model.predict(A).astype(bool)
                out.setdefault(f"{key[1]} {key[2]}", {})[label] = csi(p, w, dr)
    return out


def coherence_check():
    """Does interferometric coherence separate flooded from dry forest? Choctawhatchee only, where GUNW is on disk."""
    site = load_site("choctawhatchee")
    grid = analysis_grid(site)
    cases = (("076A Oct 5 to 17 (flood)", "076A_20261005_20261017", "076A_oct17"), ("127D Oct 9 to 21 (flood)", "127D_20261009_20261021", "127D_oct21"),
             ("127D Sep 15 to 27 (before the flood, control)", "127D_20260915_20260927", "127D_oct21"))
    box = (grid.x0, grid.y0 - grid.height * grid.res, grid.x0 + grid.width * grid.res, grid.y0)
    out = {}
    for label, key, truth_pair in cases:
        d = dict(np.load(CACHE / f"choctawhatchee_{truth_pair}.npz"))
        gl = read_gunw_box(site.gunw_path(key), box, which="wrapped")
        coh = gl.layers["coherenceMagnitude"].astype(float)
        xs, ys = np.asarray(gl.xs), np.asarray(gl.ys)
        src = Grid("EPSG:32616", float(xs[0] - 10), float(ys[0] + 10), 20.0, len(xs), len(ys))
        ci = np.clip(np.searchsorted(xs, grid.xs), 0, len(xs) - 1)
        ri = np.clip(np.searchsorted(-ys, -grid.ys), 0, len(ys) - 1)
        c = smooth_nan(np.where(coh[np.ix_(ri, ci)] > 0, coh[np.ix_(ri, ci)], np.nan), 3)
        forest = (d["landcover"] == 1) & (d["hand"] < 6.0) & d["region"] & (d["timing"] != 4)
        w, dr = d["wet"] & forest, d["dry"] & forest
        out[label] = {"auc": auc(c, w, dr), "median_wet": float(np.nanmedian(c[w])), "median_dry": float(np.nanmedian(c[dr]))}
        del src
    return out


def main():
    data, table = {}, {}
    for storm, name, pair in PASSES:
        row, f, eligible, w, dr, mapped = evaluate(build(name, pair))
        data[(storm, name, pair)] = (row, f, eligible, w, dr, mapped)
        table[f"{name} {pair}"] = {"storm": storm, **row}
        print(f"{name:15s} {pair} wet {row['wet_ha']:7,.0f} up dHH {row['upland_dHH'] if row['upland_dHH'] is None else round(row['upland_dHH'], 2)} "
              f"up dHV {row['upland_dHV'] if row['upland_dHV'] is None else round(row['upland_dHV'], 2)} | CSI dHH {row['dHH']['csi']:.2f} dR {row['dHH_minus_dHV']['csi']:.2f} both {row['both']['csi']:.2f} "
              f"| AUC dHH {row['auc']['dHH']} dHV {row['auc']['dHV']} dR {row['auc']['dHH_minus_dHV']} HHwet {row['auc']['HH_wet']} ratio {row['auc']['HHHV_ratio_wet']} "
              f"| Ashman dHH {row['dHH']['ashman_d']:.2f} dR {row['dHH_minus_dHV']['ashman_d']:.2f}", flush=True)
    d = build("yellow", "055D_oct04")
    row, *_ = evaluate(d)
    table["yellow 055D_oct04 (no flood)"] = row
    print("low minus high valley ground:", json.dumps({k: {n: (None if v is None else round(v, 2)) for n, v in r["low_minus_high"].items()} | {"wet_ha": round(r["wet_ha"])} for k, r in table.items()}), flush=True)
    print(f"no-flood control Oct 4: CSI dHH {row['dHH']['csi']:.2f} dR {row['dHH_minus_dHV']['csi']:.2f}, Ashman dHH {row['dHH']['ashman_d']:.2f} dR {row['dHH_minus_dHV']['ashman_d']:.2f}, between-share dHH {row['dHH']['between_share']:.2f} dR {row['dHH_minus_dHV']['between_share']:.2f}", flush=True)
    models = leave_one_storm_out(data)
    print("leave-one-storm-out:", json.dumps({k: {m: round(v, 2) for m, v in r.items()} for k, r in models.items()}), flush=True)
    try:
        coh = coherence_check()
        print("coherence:", json.dumps(coh), flush=True)
    except (OSError, KeyError, ValueError) as e:
        coh = {"error": repr(e)}
        print("coherence failed:", repr(e), flush=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    (CACHE / "summary.json").write_text(json.dumps({"passes": table, "leave_one_storm_out": models, "coherence": coh}, indent=1, default=float))
    print("EXPLORE DONE", flush=True)
    sys.stdout.flush()


if __name__ == "__main__":
    main()
