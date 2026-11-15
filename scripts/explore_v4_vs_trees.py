"""EXPLORATION ONLY: boosted trees and random forests, trained on two storms and scored on the third, against v4 rules.

Radar features only. Height above the river is not a feature, since the truth uses the same lidar. Both single-date and
median-baseline change features are offered, so the trees get every advantage the rule gets. Trees are also given
per-scene standardized features, which is their best chance of transferring between storms.
"""

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from dev_v4 import ALL, JUDGE_HA, csi, load_pass
from explore_model_ideas import CACHE

from hidden_floods.selfcal import smooth_nan


def features(d):
    s = lambda a: smooth_nan(a, 3)
    hh1, hv1, hhm, hvm = d["hh_wet"] - d["hh_dry"], d["hv_wet"] - d["hv_dry"], d["hh_wet"] - d["hh_base"], d["hv_wet"] - d["hv_base"]
    return {"dHH": s(hh1), "dHV": s(hv1), "dHHm": s(hhm), "dHVm": s(hvm), "dRm": s(hhm - hvm), "HH_wet": s(d["hh_wet"]), "HV_wet": s(d["hv_wet"]), "HV_base": s(d["hv_base"])}


def standardize(f, floor):
    """Subtract the scene's valley-floor median and divide by its spread: self-calibration for the trees."""
    out = {}
    for n, v in f.items():
        x = v[floor & np.isfinite(v)]
        out[n] = (v - np.median(x)) / (1.4826 * np.median(np.abs(x - np.median(x))) + 1e-6)
    return out


def main():
    import sklearn
    from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier

    print("sklearn", sklearn.__version__, "imports OK", flush=True)
    rng = np.random.default_rng(0)
    data = {}
    for storm, name, pair in ALL:
        d, _ = load_pass(name, pair)
        f = features(d)
        names = tuple(f)
        good = np.all([np.isfinite(f[n]) for n in names], axis=0) & np.isin(d["landcover"], (0, 1, 2)) & (d["hand"] < 6.0)
        floor = good & (d["dist"] < 4000.0)
        mapped = d["timing"] != 4
        w, dr = d["wet"] & d["region"] & mapped, d["dry"] & d["region"] & mapped
        data[(storm, name, pair)] = {"raw": f, "scene": standardize(f, floor), "good": good, "w": w, "dr": dr, "mapped": mapped}
    results = {}
    for kind in ("raw", "scene"):
        for held in sorted({k[0] for k in data}):
            Xs, ys = [], []
            for k, v in data.items():
                if k[0] == held:
                    continue
                m = v["good"] & (v["w"] | v["dr"])
                idx = rng.choice(np.flatnonzero(m), min(int(m.sum()), 15000), replace=False)
                Xs.append(np.stack([v[kind][n].ravel()[idx] for n in names], 1))
                ys.append(v["w"].ravel()[idx])
            X, y = np.concatenate(Xs), np.concatenate(ys)
            models = {"boosted": HistGradientBoostingClassifier(max_iter=150, learning_rate=0.08, max_leaf_nodes=15, class_weight="balanced", random_state=0).fit(X, y),
                      "forest": RandomForestClassifier(n_estimators=150, min_samples_leaf=20, class_weight="balanced", n_jobs=-1, random_state=0).fit(X, y)}
            for k, v in data.items():
                if k[0] != held:
                    continue
                good = v["good"] & v["mapped"]
                A = np.stack([v[kind][n][good] for n in names], 1)
                for label, model in models.items():
                    p = np.zeros(v["w"].shape, bool)
                    p[good] = model.predict(A).astype(bool)
                    results.setdefault(f"{k[1]} {k[2]}", {"wet_ha": float(v["w"].sum() * 0.25)})[f"{label}_{kind}"] = csi(p, v["w"], v["dr"])
            print(f"finished {kind} held out {held}", flush=True)
    grid = json.loads((CACHE / "dev_v4.json").read_text())["grid"]
    for k, r in results.items():
        r["v3"] = grid["single / hh / check None"][k]["csi"]
        r["v4"] = grid["median / adaptive / check None"][k]["csi"]
    judged = [r for r in results.values() if r["wet_ha"] >= JUDGE_HA]
    print(json.dumps({k: {m: round(x, 2) for m, x in r.items()} for k, r in results.items()}), flush=True)
    print("mean over judgeable passes:", {m: round(float(np.mean([r[m] for r in judged])), 3) for m in judged[0] if m != "wet_ha"}, "n", len(judged), flush=True)
    (CACHE / "trees.json").write_text(json.dumps(results, indent=1))
    print("TREES DONE", flush=True)


if __name__ == "__main__":
    main()
