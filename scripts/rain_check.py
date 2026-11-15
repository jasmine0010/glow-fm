"""Rainfall before every pass, and whether it explains radar behaviour (research/RAINFALL.md). Exploratory, on spent rivers.

Writes research/rainfall_by_pass.json. Changes no method.
"""

import json
import sys
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from dev_v4 import load_pass
from explore_model_ideas import auc, get_site

from hidden_floods.config import REPO_ROOT, data_root
from hidden_floods.fetch import USGS_OGC, get_json
from hidden_floods.selfcal import smooth_nan
from hidden_floods.v4 import V4Rule

PASSES = (("choctawhatchee", "076A_oct17"), ("choctawhatchee", "127D_oct21"), ("pearl", "105A_jul03"), ("pearl", "156D_jun25"), ("tangipahoa", "105A_jun21"), ("tangipahoa", "156D_jun25"),
          ("yellow", "055D_oct04"), ("yellow", "076A_oct05"), ("yellow", "127D_oct09"), ("yellow", "055D_oct16"), ("yellow", "076A_oct17"), ("yellow", "127D_oct21"),
          ("village_creek", "134A_sep03"), ("village_creek", "012D_sep07"), ("pine_island", "012D_sep07"), ("pine_island", "134A_sep03"),
          ("pee_dee", "098D_jul27"), ("neuse", "090A_jul26"), ("lower_sabine", "134A_jul17"))
FROZEN_V4 = {"pee_dee", "neuse", "lower_sabine"}
POWER = "https://power.larc.nasa.gov/api/temporal/hourly/point"
RECENT_MM, ANTECEDENT_MM, BRIGHT_DB = 5.0, 25.0, 0.5
CACHE = data_root() / "rain"


def when(s):
    return datetime.fromisoformat(s.replace("Z", ""))


def power_series(river, lon, lat, start, end):
    """Hourly mm from NASA POWER, keyed by UTC hour. POWER reports local solar time, so shift by longitude."""
    path = CACHE / f"power_{river}.json"
    if path.exists():
        raw = json.loads(path.read_text())
    else:
        q = {"parameters": "PRECTOTCORR", "community": "RE", "longitude": round(lon, 3), "latitude": round(lat, 3), "start": start.strftime("%Y%m%d"), "end": end.strftime("%Y%m%d"), "format": "JSON"}
        raw = get_json(f"{POWER}?" + urllib.parse.urlencode(q), timeout=300)["properties"]["parameter"]["PRECTOTCORR"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(raw))
    shift = timedelta(hours=-lon / 15.0)
    return {datetime.strptime(k, "%Y%m%d%H") + shift: float(v) for k, v in raw.items() if float(v) > -900}


def total(series, end, hours):
    start = end - timedelta(hours=hours)
    vals = [v for t, v in series.items() if start <= t < end]
    return round(float(sum(vals)), 1) if len(vals) >= hours * 0.9 else None


def usgs_rain(site_id, start, end):
    """Rain gauge readings (parameter 00045). Returns (time, mm) pairs, or nothing where the gauge has no rain sensor."""
    path = CACHE / f"usgs_{site_id}_{start:%Y%m%d}_{end:%Y%m%d}.json"
    if path.exists():
        feats = json.loads(path.read_text())
    else:
        url, feats = f"{USGS_OGC}/continuous/items?" + urllib.parse.urlencode({"f": "json", "monitoring_location_id": site_id, "parameter_code": "00045", "time": f"{start:%Y-%m-%dT%H:%M:%SZ}/{end:%Y-%m-%dT%H:%M:%SZ}", "limit": 10000}), []
        while url:
            page = get_json(url, timeout=300)
            feats += [[f["properties"]["time"], f["properties"]["value"]] for f in page.get("features", [])]
            url = next((ln["href"] for ln in page.get("links", []) if ln.get("rel") == "next"), None)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(feats))
    return [(datetime.fromisoformat(t.replace("Z", "")[:19]), float(v) * 25.4) for t, v in feats if v not in (None, "")]


def signal(river, pair, rule):
    if river in FROZEN_V4:
        z = np.load(REPO_ROOT / "outputs" / river / pair / "frozen_v4_layers.npz")
        m = json.loads((REPO_ROOT / "research" / f"v4_{river}_{pair}_frozen_metrics.json").read_text())
        d_hh, d_hv, wet, dry, region, lc, hand, high, low_high = z["d_hh"], z["d_hv"], z["wet"], z["dry"], z["region"], z["landcover"], z["hand"], m["high_ground_db"], m["low_minus_high_db"]
    else:
        d, _ = load_pass(river, pair)
        d_hh, d_hv = d["hh_wet"] - d["hh_base"], d["hv_wet"] - d["hv_base"]
        wet, dry, region, lc, hand = d["wet"], d["dry"], d["region"], d["landcover"], d["hand"]
        r = rule.apply(d_hh, d_hv, lc, d["timing"], hand, d["dist"])
        high, low_high = r["high_db"], r["low_minus_high_db"]
    gate = np.isin(lc, (0, 1, 2)) & (hand < 6.0) & region
    w, n = wet & gate, dry & gate
    hh, ratio = smooth_nan(d_hh, 3), smooth_nan(d_hh - d_hv, 3)
    return {"high_ground_db": high, "low_minus_high_db": low_high, "auc_hh": auc(hh, w, n), "auc_hh_minus_hv": auc(ratio, w, n), "estimated_ha": float((wet & region).sum() * 0.25), "dry_ha": float((dry & region).sum() * 0.25)}


def rank_corr(a, b):
    a, b = np.array(a, float), np.array(b, float)
    ra, rb = a.argsort().argsort(), b.argsort().argsort()
    return float(np.corrcoef(ra, rb)[0, 1])


def summarize(rows):
    """The three questions in research/RAINFALL.md, for rows carrying rain totals and rainy/brightened flags."""
    both = [r for r in rows if r["auc_hh"] is not None and r["auc_hh_minus_hv"] is not None]
    judged = [r for r in rows if r["v4_csi"] is not None and r["estimated_ha"] >= 500]
    group = lambda rs, key: float(np.mean([r[key] for r in rs])) if rs else None
    wetpass, drypass = [r for r in both if r["rainy"]], [r for r in both if not r["rainy"]]
    bright = [r for r in rows if r["high_ground_db"] is not None]
    return {
        "passes": len(rows), "rainy": sum(r["rainy"] for r in rows), "brightened": sum(r["brightened"] for r in rows),
        "rainy_and_brightened": sum(r["rainy"] and r["brightened"] for r in rows), "dry_and_brightened": sum((not r["rainy"]) and r["brightened"] for r in rows),
        "rank_corr_rain72_high_ground": rank_corr([r["rain_72h_mm"] for r in bright], [r["high_ground_db"] for r in bright]),
        "rank_corr_rain24_high_ground": rank_corr([r["rain_24h_mm"] for r in bright], [r["high_ground_db"] for r in bright]),
        "ratio_beats_hh_on_rainy": sum(r["auc_hh_minus_hv"] > r["auc_hh"] for r in wetpass), "rainy_with_auc": len(wetpass),
        "ratio_beats_hh_on_dry": sum(r["auc_hh_minus_hv"] > r["auc_hh"] for r in drypass), "dry_with_auc": len(drypass),
        "mean_auc_gain_rainy": group(wetpass, "auc_hh_minus_hv") - group(wetpass, "auc_hh") if wetpass else None, "mean_auc_gain_dry": group(drypass, "auc_hh_minus_hv") - group(drypass, "auc_hh") if drypass else None,
        "mean_v4_csi_rainy": group([r for r in judged if r["rainy"]], "v4_csi"), "mean_v4_csi_not_rainy": group([r for r in judged if not r["rainy"]], "v4_csi"),
        "judged_rainy": sum(r["rainy"] for r in judged), "judged_not_rainy": sum(not r["rainy"] for r in judged),
    }


def main():
    rule, rows = V4Rule(), []
    static = {(r["river"], r["pair"]): r for r in json.loads((REPO_ROOT / "research" / "static_baseline.json").read_text())["passes"]}
    for river, pair_name in PASSES:
        site = get_site(river)
        pair = site.pairs[pair_name]
        t, t_dry = when(pair.wet_time), when(pair.dry_time)
        lon, lat = (site.bbox[0] + site.bbox[2]) / 2, (site.bbox[1] + site.bbox[3]) / 2
        series = power_series(river, lon, lat, datetime(2026, 5, 1), datetime(2026, 10, 31))
        row = {"river": river, "pair": pair_name, "time": pair.wet_time, "rain_6h_mm": total(series, t, 6), "rain_24h_mm": total(series, t, 24), "rain_72h_mm": total(series, t, 72), "rain_7d_mm": total(series, t, 168), "dry_pass_rain_72h_mm": total(series, t_dry, 72)}
        window = (t - timedelta(hours=72), t)
        gauges = []
        for g in site.gauges:
            obs = usgs_rain(g.id, window[0], window[1])
            if obs:
                gauges.append({"id": g.id, "name": g.name, "readings": len(obs), "rain_24h_mm": round(sum(v for when_, v in obs if when_ >= t - timedelta(hours=24)), 1), "rain_72h_mm": round(sum(v for _, v in obs), 1)})
        row["usgs_gauges"] = gauges
        row.update(signal(river, pair_name, rule))
        s = static.get((river, pair_name))
        row["v4_csi"] = s and s["radar_csi"]
        row["rainy"] = bool((row["rain_24h_mm"] or 0) >= RECENT_MM or (row["rain_72h_mm"] or 0) >= ANTECEDENT_MM)
        row["brightened"] = row["high_ground_db"] is not None and row["high_ground_db"] > BRIGHT_DB
        row["status"] = "Likely contributor" if row["rainy"] and row["brightened"] else "Possible" if row["rainy"] or row["brightened"] else "Little sign"
        rows.append(row)
        print(json.dumps({k: (round(v, 2) if isinstance(v, float) else v) for k, v in row.items()}), flush=True)
    summary = summarize(rows)
    print(json.dumps(summary, indent=1), flush=True)
    (REPO_ROOT / "research" / "rainfall_by_pass.json").write_text(json.dumps({"summary": summary, "passes": rows}, indent=1))
    print("RAIN DONE", flush=True)


if __name__ == "__main__":
    main()
