"""EXPLORATION ONLY, on spent rivers. Radar-only models trained on two storms and scored on the third, plus each feature's
best possible threshold chosen by looking at the truth (a ceiling, not a method). Plain numpy logistic regression.
"""

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from explore_model_ideas import CACHE, PASSES, build, csi, evaluate

SETS = {"dHH": ("dHH",), "dHH-dHV": ("dHH_minus_dHV",), "dHH+dHV": ("dHH", "dHV"), "change+levels": ("dHH", "dHV", "HH_wet", "HV_wet"),
        "levels only": ("HH_wet", "HV_wet"), "all": ("dHH", "dHV", "HH_wet", "HV_wet", "HV_dry")}


def fit(X, y, steps=400, lr=0.4):
    mu, sd = X.mean(0), X.std(0) + 1e-6
    Z = (X - mu) / sd
    w, b = np.zeros(Z.shape[1]), 0.0
    weights = np.where(y, 0.5 / y.mean(), 0.5 / (1 - y.mean()))     # balanced classes
    for _ in range(steps):
        p = 1 / (1 + np.exp(-(Z @ w + b)))
        g = weights * (p - y)
        w -= lr * (Z.T @ g / len(y) + 1e-3 * w)
        b -= lr * g.mean()
    return mu, sd, w, b


def oracle(x, eligible, w, d):
    v = x[eligible & np.isfinite(x)]
    return max(csi(eligible & (x > t), w, d) for t in np.percentile(v, np.arange(40, 99.5, 1.0)))


def main():
    rng = np.random.default_rng(0)
    data = {}
    for storm, name, pair in PASSES:
        row, f, eligible, w, d, mapped = evaluate(build(name, pair))
        data[(storm, name, pair)] = (row, f, eligible, w, d, mapped)
        if "--oracle" in sys.argv:
            print(f"{name} {pair}: wet {row['wet_ha']:.0f} | oracle CSI dHH {oracle(f['dHH'], eligible & mapped, w, d):.2f} dR {oracle(f['dHH_minus_dHV'], eligible & mapped, w, d):.2f} HHwet {oracle(f['HH_wet'], eligible & mapped, w, d):.2f}", flush=True)
    results = {}
    for label, names in SETS.items():
        for held in sorted({k[0] for k in data}):
            X, y = [], []
            for k, (_, f, eligible, w, d, _) in data.items():
                if k[0] == held:
                    continue
                m = eligible & (w | d) & np.all([np.isfinite(f[n]) for n in names], axis=0)
                idx = rng.choice(np.flatnonzero(m), min(int(m.sum()), 6000), replace=False)
                X.append(np.stack([f[n].ravel()[idx] for n in names], 1))
                y.append(w.ravel()[idx])
            X, y = np.concatenate(X), np.concatenate(y).astype(float)
            mu, sd, coef, b = fit(X, y)
            print(f"{label} held out {held}: weights per 1 sd {dict(zip(names, np.round(coef, 2).tolist(), strict=True))}", flush=True)
            for k, (row, f, eligible, w, d, mapped) in data.items():
                if k[0] != held:
                    continue
                good = eligible & mapped & np.all([np.isfinite(f[n]) for n in names], axis=0)
                A = (np.stack([f[n][good] for n in names], 1) - mu) / sd
                p = np.zeros(w.shape, bool)
                p[good] = A @ coef + b > 0
                results.setdefault(f"{k[1]} {k[2]}", {"wet_ha": row["wet_ha"], "otsu_dHH": row["dHH"]["csi"], "otsu_dR": row["dHH_minus_dHV"]["csi"]})[label] = csi(p, w, d)
    judged = {k: v for k, v in results.items() if v["wet_ha"] >= 500}
    print(json.dumps({k: {m: round(x, 2) for m, x in v.items()} for k, v in results.items()}), flush=True)
    print("mean over judgeable passes:", {m: round(float(np.mean([v[m] for v in judged.values()])), 3) for m in next(iter(judged.values())) if m != "wet_ha"}, flush=True)
    (CACHE / "logistic.json").write_text(json.dumps(results, indent=1))
    print("LOGISTIC DONE", flush=True)


if __name__ == "__main__":
    main()
