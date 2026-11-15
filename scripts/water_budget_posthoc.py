"""Post-hoc, after the one-time run: was the flow record quiet enough to judge the estimate? Reads the saved results only and changes no reading."""
import json
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
j = json.loads((ROOT / "research/water_budget_results.json").read_text())
rows, quiet = [], []
for r in j["reaches"]:
    if not r.get("estimated_mm3_daily") or not r.get("flow_mm3_daily"):
        continue
    n = min(len(r["estimated_mm3_daily"]), len(r["flow_mm3_daily"]))
    e = np.array([np.nan if v is None else v for v in r["estimated_mm3_daily"][:n]], float)
    f = np.array(r["flow_mm3_daily"][:n], float)
    peak_i = int(np.nanargmax(e))
    start_candidates = np.nonzero(e[:peak_i + 1] <= 0.05 * np.nanmax(e))[0]
    start = int(start_candidates[-1]) if len(start_candidates) else 0
    rise_est, rise_flow = float(e[peak_i] - e[start]), float(f[peak_i] - f[start])
    # Days with almost no estimated water show how far flow storage wanders with nothing to store.
    calm = e <= 0.05 * np.nanmax(e)
    wander = None
    if calm.sum() >= 5:
        idx = np.nonzero(calm)[0]
        wander = float(np.max(f[idx]) - np.min(f[idx]))
    daily_flow = np.diff(f)
    daily_est = np.diff(e)
    ok = np.isfinite(daily_est)
    change_rho = float(spearmanr(daily_flow[ok], daily_est[ok]).statistic) if ok.sum() >= 10 else None
    row = {"river": r["river"], "reach": r["reach"], "judged": r["judged"], "peak_est": round(float(np.nanmax(e)), 1), "peak_flow": r["peak_flow_mm3"], "end_of_window_flow": round(float(f[-1]), 1), "flow_at_est_peak": round(float(f[peak_i]), 1),
           "rise_days": peak_i - start, "rise_est": round(rise_est, 1), "rise_flow": round(rise_flow, 1), "rise_ratio": None if rise_est <= 0 else round(rise_flow / rise_est, 2), "calm_days": int(calm.sum()), "calm_wander": None if wander is None else round(wander, 1), "daily_change_spearman": None if change_rho is None else round(change_rho, 2)}
    rows.append(row)
    print(row)
judged = [r for r in rows if r["judged"]]
out = {"note": "Post-hoc, after the one-time run. Changes no reading.", "reaches": rows,
       "judged_rise_ratios": [r["rise_ratio"] for r in judged], "judged_within_third_to_three": sum(r["rise_ratio"] is not None and 1 / 3 <= r["rise_ratio"] <= 3 for r in judged), "judged_n": len(judged),
       "median_abs_end_over_peak_est": round(float(np.median([abs(r["end_of_window_flow"]) / r["peak_est"] for r in judged])), 2),
       "median_calm_wander_mm3": round(float(np.median([r["calm_wander"] for r in judged if r["calm_wander"] is not None])), 1), "median_peak_est_mm3": round(float(np.median([r["peak_est"] for r in judged])), 1)}
print({k: v for k, v in out.items() if k != "reaches"})
(ROOT / "research/water_budget_posthoc.json").write_text(json.dumps(out, indent=1))
