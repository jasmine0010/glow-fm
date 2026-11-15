"""DEVELOPMENT ONLY: choose v4 settings by leave-one-storm-out on the 14 spent passes.

For each storm, settings are picked on the other two, then scored on it. Passes under 500 ha of confirmed flooding count
only as false-alarm tests. Selection maximises mean CSI, breaking ties by fewer false-alarm hectares on no-flood passes.
"""

import itertools
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from explore_model_ideas import CACHE, PASSES, build, get_site
from fetch_stacks import scenes_for

from hidden_floods.pipeline import analysis_grid
from hidden_floods.stack import cache_path
from hidden_floods.v4 import V4Rule, median_baseline

ALL = [*PASSES, ("isaias", "yellow", "055D_oct04")]
GRID = list(itertools.product(("single", "median"), ("hh", "hh_minus_hv", "adaptive"), (None, 0.25, 0.5, 0.75)))
JUDGE_HA = 500.0


def csi(p, w, d):
    tp, fn, fp = (p & w).sum(), (~p & w).sum(), (p & d).sum()
    return float(tp / (tp + fn + fp)) if tp + fn + fp else float("nan")


def load_pass(name, pair_name):
    d = build(name, pair_name)
    site = get_site(name)
    pair = site.pairs[pair_name]
    grid = analysis_grid(site)
    assert grid.shape == d["hh_wet"].shape
    hh, hv, used = [], [], []
    for s in scenes_for(site, pair):
        if s.time == pair.wet_time or s.time[:10] == pair.wet_time[:10]:
            continue
        path = cache_path(site, s.name)
        if path.exists():
            z = np.load(path)
            hh.append(z["hh"])
            hv.append(z["hv"])
            used.append(s.time[:10])
    d = dict(d)
    d["hh_base"] = median_baseline(np.stack(hh))
    d["hv_base"] = median_baseline(np.stack(hv))
    return d, used


def run_rule(rule, d):
    if rule.baseline == "single":
        d_hh, d_hv = d["hh_wet"] - d["hh_dry"], d["hv_wet"] - d["hv_dry"]
    else:
        d_hh, d_hv = d["hh_wet"] - d["hh_base"], d["hv_wet"] - d["hv_base"]
    r = rule.apply(d_hh, d_hv, d["landcover"], d["timing"], d["hand"], d["dist"])
    scored = d["region"] & r["mapped"]
    w, dr = d["wet"] & scored, d["dry"] & scored
    return {"csi": csi(r["pred"], w, dr), "wet_ha": float((d["wet"] & d["region"]).sum() * 0.25), "false_ha": float((r["pred"] & dr).sum() * 0.25),
            "mapped_ha": float((r["pred"] & d["region"] & (d["dist"] < 4000)).sum() * 0.25), "flood_found": r["flood_found"], "ratio": r["used_hh_minus_hv"],
            "thr": r["threshold_db"], "low_minus_high": r["low_minus_high_db"], "high": r["high_db"]}


def key(s):
    return f"{s[0]} / {s[1]} / check {s[2]}"


def main():
    data = {}
    for storm, name, pair_name in ALL:
        d, used = load_pass(name, pair_name)
        data[(storm, name, pair_name)] = d
        print(f"{name} {pair_name}: baseline dates {used}", flush=True)
    res = {}
    for s in GRID:
        rule = V4Rule(baseline=s[0], signal=s[1], flood_check_db=s[2])
        res[s] = {k: run_rule(rule, d) for k, d in data.items()}

    def judged(s, storms):
        return [r for k, r in res[s].items() if k[0] in storms and r["wet_ha"] >= JUDGE_HA]

    def false_tests(s, storms):
        return sum(r["false_ha"] for k, r in res[s].items() if k[0] in storms and r["wet_ha"] < JUDGE_HA)

    def pick(storms):
        return max(GRID, key=lambda s: (round(float(np.mean([r["csi"] for r in judged(s, storms)])), 3), -false_tests(s, storms)))

    print("\nAll settings, mean CSI on judgeable passes | false-alarm ha on small and no-flood passes:", flush=True)
    for s in sorted(GRID, key=lambda s: -np.mean([r["csi"] for r in judged(s, {"isaias", "arthur", "edouard"})])):
        all_storms = {"isaias", "arthur", "edouard"}
        print(f"  {key(s):38s} {np.mean([r['csi'] for r in judged(s, all_storms)]):.3f} | {false_tests(s, all_storms):7,.0f}", flush=True)

    storms = sorted({k[0] for k in data})
    loso = {}
    for held in storms:
        s = pick(set(storms) - {held})
        rows = {f"{k[1]} {k[2]}": r for k, r in res[s].items() if k[0] == held}
        loso[held] = {"setting": key(s), "passes": rows}
        print(f"\nHeld out {held}: picked {key(s)}", flush=True)
        for n, r in rows.items():
            base = res[("single", "hh", None)][next(k for k in data if f"{k[1]} {k[2]}" == n)]
            print(f"  {n:32s} confirmed {r['wet_ha']:7,.0f} | v4 CSI {r['csi']:.2f} false {r['false_ha']:7,.0f} mapped {r['mapped_ha']:7,.0f} flood_found {r['flood_found']} ratio {r['ratio']} lowhigh {r['low_minus_high']} | v3 CSI {base['csi']:.2f} false {base['false_ha']:7,.0f}", flush=True)
    flat = [r for v in loso.values() for r in v["passes"].values() if r["wet_ha"] >= JUDGE_HA]
    v3 = [r for k, r in res[("single", "hh", None)].items() if r["wet_ha"] >= JUDGE_HA]
    print(f"\nLeave-one-storm-out mean CSI on judgeable passes: v4 {np.mean([r['csi'] for r in flat]):.3f}, v3 {np.mean([r['csi'] for r in v3]):.3f}", flush=True)
    final = pick(set(storms))
    print(f"Final setting on all storms: {key(final)}", flush=True)
    (CACHE / "dev_v4.json").write_text(json.dumps({"grid": {key(s): {f"{k[1]} {k[2]}": r for k, r in v.items()} for s, v in res.items()}, "loso": loso, "final": key(final)}, indent=1, default=float))
    print("DEV V4 DONE", flush=True)


if __name__ == "__main__":
    main()
