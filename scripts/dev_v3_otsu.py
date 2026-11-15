"""DEVELOPMENT ONLY — v3 with an Otsu threshold vs v3 with the upland-quantile threshold, leave-one-flood-out.

The Otsu rule has only two discrete choices (land-cover set, abstention set), so the leave-one-flood-out estimate
picks among four combinations. Also reports the effect of ponding-tolerant scoring (peak-envelope truth).
"""

import itertools
import json

import numpy as np
from dev_v3 import CACHE, MIN_COVERAGE, PAIRS, build, evaluate, grid_rules, rule_key

from hidden_floods.v3 import V3OtsuRule

data = {p: build(*p) for p in PAIRS}
rivers = sorted({p[0] for p in PAIRS})
judgeable = [p for p in PAIRS if data[p]["wet"][data[p]["region"]].sum() * 0.25 >= 500]  # skip near-empty floods
print("judgeable pairs:", judgeable)
for p, d in data.items():
    print(f"  {p[0][:5]} {p[1]}: ambiguous (dry now, flooded at crest) {(d['dry'] & d['wet_peak'] & d['region']).sum() * .25:,.0f} ha")


def loo(results):
    """results: key -> pair -> metrics. Returns per-river held-out metrics with the setting picked on the others."""
    def mean(k, rs, m):
        return float(np.nanmean([results[k][p][m] for p in judgeable if p[0] in rs]))
    out = {}
    for held in rivers:
        others = [r for r in rivers if r != held]
        ok = [k for k in results if mean(k, others, "coverage") >= MIN_COVERAGE]
        k = max(ok, key=lambda k: mean(k, others, "csi"))
        out[held] = {"setting": k, **{m: mean(k, [held], m) for m in ("csi", "recall", "precision", "coverage")}}
    best = max([k for k in results if mean(k, rivers, "coverage") >= MIN_COVERAGE], key=lambda k: mean(k, rivers, "csi"))
    return out, best


summary = {}
for ponding in (True, False):
    otsu = {}
    for lc, ab in itertools.product(((1, 2), (1, 2, 0)), ((), (4,))):
        r = V3OtsuRule(landcover=lc, abstain_timing=ab)
        otsu[f"otsu lc{''.join(map(str, lc))} ab{''.join(map(str, ab)) or '-'}"] = {p: evaluate(r, d, ponding) for p, d in data.items()}
    quant = {rule_key(r): {p: evaluate(r, d, ponding) for p, d in data.items()} for r in grid_rules()}
    for name, res in (("otsu", otsu), ("quantile grid", quant)):
        lo, best = loo(res)
        mean_loo = np.mean([v["csi"] for v in lo.values()])
        tag = "ponding-tolerant truth" if ponding else "instant truth"
        print(f"\n[{tag}] {name}: leave-one-flood-out mean CSI {mean_loo:.2f}")
        for held, v in lo.items():
            print(f"   {held:15s} {v['setting']:40s} CSI {v['csi']:.2f} recall {v['recall']:.2f} precision {v['precision']:.2f} coverage {v['coverage']:.2f}")
        print(f"   final choice on all three: {best}")
        summary[f"{name} | {tag}"] = {"loo": lo, "loo_mean_csi": mean_loo, "final": best,
                                      "final_per_pair": {f"{p[0]} {p[1]}": res[best][p] for p in PAIRS}}
(CACHE / "dev_v3_otsu.json").write_text(json.dumps(summary, indent=1, default=float))
