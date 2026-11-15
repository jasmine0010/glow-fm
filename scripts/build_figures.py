"""Data for the site's scientific figures (app/figures.js; the Results page and the story's headline figures).

    python scripts/build_figures.py

Writes app/data/figures/*.json. Most of it is gathered from results already on file (metrics.json, heldout.json,
manifest.json, research/*.json, the atlas). The pixel statistics (backscatter distributions by water depth,
wet-against-dry histograms, ROC curves, accuracy by depth, height and land cover) are DESCRIPTIVE: they are summarised
from the saved layers of each frozen one-time run (outputs/<river>/<pair>/frozen_v4_layers.npz) after the fact. Nothing
is re-scored or tuned, and every figure that uses them says so.

Each output is checked against the record before it's written: pooled confusion counts must equal each frozen run's
own, ROC areas must match research/rainfall_by_pass.json where it computed them from the same layers, curve medians must
match the stored response curves, and the latitude profile must sum to the atlas total.
"""

import json
import tomllib

import numpy as np

from hidden_floods.config import REPO_ROOT
from hidden_floods.drivers import BIN_EDGES_M, LC_TREE, MIN_BIN_PX
from hidden_floods.metrics import block_bootstrap, block_ids, score
from hidden_floods.selfcal import smooth_nan

APP = REPO_ROOT / "app" / "data"
OUT = APP / "figures"
RESEARCH = REPO_ROOT / "research"
PIXEL_HA = 0.25
BLOCK_M, N_BOOT, SEED = 2000.0, 2000, 0          # the frozen tests' interval method
HH_EDGES = np.round(np.arange(-4.0, 8.01, 0.25), 2)  # dB bins for the distributions
ROC_POINTS = 60


def jdump(name, obj):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(obj, separators=(",", ":"), allow_nan=False))


def r3(x):
    return None if x is None or not np.isfinite(x) else round(float(x), 4)


# ---------- the frozen v4 runs whose layers are saved ----------
def frozen_runs():
    runs = []
    for npz in sorted((REPO_ROOT / "outputs").glob("*/*/frozen_v4_layers.npz")):
        river, pair = npz.parent.parent.name, npz.parent.name
        rec = json.loads((npz.parent / "frozen_v4_metrics.json").read_text(encoding="utf8"))
        z = np.load(npz)
        scored = z["region"] & z["mapped"]
        runs.append({"river": river, "pair": pair, "z": z, "scored": scored, "rec": rec,
                     "wet": z["wet"] & scored, "dry": z["dry"] & scored})
    return runs


def check_counts(run):
    """The layers reproduce the frozen run's own confusion counts exactly."""
    s = score(run["z"]["pred"], run["wet"], run["dry"])
    want = run["rec"]["primary_v4"]["scores"]
    got = {"tp": s.tp, "fn": s.fn, "fp": s.fp, "tn": s.tn}
    assert all(got[k] == want[k] for k in got), (run["river"], run["pair"], got, want)
    return got


# ---------- Fig. 2: the physical signature ----------
def signature(runs, heldout):
    stored = {(r["id"], p["id"]): p["drivers"]["curve"] for r in heldout["rivers"] for p in r["pairs"]}
    judged = [r for r in runs if r["wet"].sum() > 0]
    nb = len(BIN_EDGES_M) - 1
    pooled = np.zeros((nb, len(HH_EDGES) - 1), dtype=np.int64)
    pooled_hh = [[] for _ in range(nb)]
    pooled_hv = [[] for _ in range(nb)]
    hero = None
    max_diff = 0.0
    for run in judged:
        z = run["z"]
        d_hh, d_hv, depth = z["d_hh"], z["d_hv"], z["depth"]
        in_curve = (z["landcover"] == LC_TREE) & z["region"] & np.isfinite(depth) & np.isfinite(d_hh) & np.isfinite(d_hv)
        per = []
        for k in range(nb):
            lo, hi = BIN_EDGES_M[k], BIN_EDGES_M[k + 1]
            m = in_curve & (depth >= lo) & (depth < hi)
            vals = d_hh[m]
            pooled[k] += np.histogram(np.clip(vals, HH_EDGES[0], HH_EDGES[-1] - 1e-6), HH_EDGES)[0]
            pooled_hh[k].append(vals)
            pooled_hv[k].append(d_hv[m])
            per.append({"bin": k, "n": int(m.sum()), "hh": r3(np.median(vals)) if m.sum() >= MIN_BIN_PX else None})
        # the stored response curve uses the same pixels: its medians must agree
        key = (run["river"], run["pair"])
        if key in stored:
            for row in stored[key]:
                k = int(np.searchsorted(BIN_EDGES_M, row["water_above_ground_m"]) - 1)
                if per[k]["hh"] is not None:
                    max_diff = max(max_diff, abs(per[k]["hh"] - row["hh_db"]))
        if run["river"] == "satilla" and run["pair"] == "047A_oct15":
            hero = per
    assert max_diff < 0.02, f"ridgeline medians differ from the stored curves by {max_diff:.3f} dB"
    bins = []
    for k in range(nb):
        hh, hv = np.concatenate(pooled_hh[k]), np.concatenate(pooled_hv[k])
        n = int(hh.size)
        q = (lambda a, p, n=n: r3(np.percentile(a, p)) if n >= MIN_BIN_PX else None)
        bins.append({"lo": BIN_EDGES_M[k], "hi": BIN_EDGES_M[k + 1], "n": n, "ha": n * PIXEL_HA, "counts": pooled[k].tolist(),
                     "hh_q": [q(hh, 25), q(hh, 50), q(hh, 75)], "hv_q": [q(hv, 25), q(hv, 50), q(hv, 75)]})
    return {"hh_edges": HH_EDGES.tolist(), "bins": bins, "pooled_from": [f"{r['river']} {r['pair']}" for r in judged], "hero": hero,
            "check": {"max_median_diff_db": round(max_diff, 4)}}


def curves(heldout, manifest):
    """Every stored response curve: 7 held-out and 12 development passes."""
    out = []
    for r in heldout["rivers"]:
        for p in r["pairs"]:
            out.append({"river": r["id"], "pair": p["id"], "role": "held-out", "curve": p["drivers"]["curve"]})
    for s in manifest["sites"]:
        for p in s["pairs"]:
            if p.get("drivers") and p["drivers"].get("curve"):
                out.append({"river": s["id"], "pair": p["id"], "role": "development", "curve": p["drivers"]["curve"]})
    c = json.loads((RESEARCH / "c_band_results.json").read_text(encoding="utf8"))
    return {"passes": out, "pearl": {"c_band": c["c_band"]["curve"], "l_band": c["l_band"]["curve"], "c_dates": c["c_band"]["dates"], "l_pair": c["l_band"]["pair"]}}


# ---------- Fig. 3: separability ----------
def auc_from(x, w, d):
    a, b = x[w], x[d]
    a, b = a[np.isfinite(a)], b[np.isfinite(b)]
    if a.size < 40 or b.size < 40:
        return None
    r = np.concatenate([a, b]).argsort().argsort() + 1.0
    return float((r[: a.size].sum() - a.size * (a.size + 1) / 2) / (a.size * b.size))


def separability(runs, overbank):
    stored = {(p["river"], p["pair"]): p for p in json.loads((RESEARCH / "rainfall_by_pass.json").read_text(encoding="utf8"))["passes"]}
    light = {(o["site"], o["pair"]): o for o in overbank}
    out, pooled_w, pooled_d, worst = [], np.zeros(len(HH_EDGES) - 1, int), np.zeros(len(HH_EDGES) - 1, int), 0.0
    for run in runs:
        if run["wet"].sum() == 0:
            continue
        z, rec = run["z"], run["rec"]
        # the same pixels and smoothing as the stored ROC areas (scripts/rain_check.py signal())
        gate = np.isin(z["landcover"], (0, 1, 2)) & (z["hand"] < 6.0) & z["region"]
        w, d = z["wet"] & gate, z["dry"] & gate
        hh = smooth_nan(z["d_hh"], 3)
        auc = auc_from(hh, w, d)
        s = stored.get((run["river"], run["pair"]))
        diff = None if not s or s["auc_hh"] is None or auc is None else abs(auc - s["auc_hh"])
        if diff is not None and run["river"] in ("pee_dee", "neuse", "lower_sabine"):   # these were computed from these very layers
            worst = max(worst, diff)
        a, b = hh[w], hh[d]
        a, b = a[np.isfinite(a)], b[np.isfinite(b)]
        cuts = np.quantile(np.concatenate([a, b]), np.linspace(1, 0, ROC_POINTS))
        roc = [[r3((b >= c).mean()), r3((a >= c).mean())] for c in cuts]
        # the method's own signal and its frozen cut-off, on the scored pixels
        sig = smooth_nan(z["d_hh"] - z["d_hv"] if rec["used_hh_minus_hv"] else z["d_hh"], 3)
        hw = np.histogram(np.clip(sig[run["wet"]], HH_EDGES[0], HH_EDGES[-1] - 1e-6), HH_EDGES)[0]
        hd = np.histogram(np.clip(sig[run["dry"]], HH_EDGES[0], HH_EDGES[-1] - 1e-6), HH_EDGES)[0]
        if not rec["used_hh_minus_hv"]:
            pooled_w += hw; pooled_d += hd
        o = light.get((run["river"], run["pair"]), {})
        out.append({"river": run["river"], "pair": run["pair"], "auc": r3(auc), "auc_stored": r3(s["auc_hh"]) if s else None,
                    "signal": "HH minus HV" if rec["used_hh_minus_hv"] else "HH", "cutoff_db": r3(rec["v4_threshold_db"]),
                    "wet_hist": hw.tolist(), "dry_hist": hd.tolist(), "n_wet": int(run["wet"].sum()), "n_dry": int(run["dry"].sum()),
                    "roc": roc, "csi": r3(rec["primary_v4"]["scores"]["csi"]), "trust": o.get("signal") or ("green" if rec.get("confident") else "red")})
    assert worst < 0.005, f"ROC areas differ from research/rainfall_by_pass.json by {worst:.4f}"
    return {"hh_edges": HH_EDGES.tolist(), "passes": out, "pooled_wet": pooled_w.tolist(), "pooled_dry": pooled_d.tolist(), "check": {"max_auc_diff": round(worst, 5)}}


# ---------- Fig. 5: where it works ----------
def strata(runs, trust):
    """Recall by water depth (every labelled pixel deeper than 0.5 m is wet, so precision there is always 1), and recall and
    precision by height above the river and by land cover. Computed for the green-light passes and for all judged passes,
    because the red-light failures dominate the false alarms when everything is pooled."""
    return {"groups": [strata_group([r for r in runs if r["wet"].sum() > 0 and trust[(r["river"], r["pair"])] == "green"], "green"),
                       strata_group([r for r in runs if r["wet"].sum() > 0], "all")]}


def strata_group(judged, name):
    # pool the passes, keeping each pass's 2 km blocks distinct
    cat = lambda key: np.concatenate([r["z"][key][r["scored"]] for r in judged])
    pred, wet, dry, depth, hand, lc = cat("pred"), cat("wet"), cat("dry"), cat("depth"), cat("hand"), cat("landcover")
    blocks, offset = [], 0
    for r in judged:
        b = block_ids(r["z"]["chainage"][r["scored"]], BLOCK_M)
        blocks.append(b + offset)
        offset += int(b.max()) + 1
    blocks = np.concatenate(blocks)

    def cell(mask, label):
        s = score(pred, wet, dry, mask)
        n_wet, n_dry = s.tp + s.fn, s.fp + s.tn
        if n_wet + n_dry < MIN_BIN_PX:
            return None
        ci = block_bootstrap(pred, wet, dry, blocks, mask, n_boot=N_BOOT, seed=SEED, metrics=("recall", "precision"))
        rec = s.tp / n_wet if n_wet else None
        prec = s.tp / (s.tp + s.fp) if s.tp + s.fp else None
        return {"label": label, "n_wet": n_wet, "n_dry": n_dry, "recall": r3(rec), "precision": r3(prec),
                "recall_ci": [r3(x) for x in ci["recall"]] if rec is not None else None, "precision_ci": [r3(x) for x in ci["precision"]] if prec is not None else None}

    by_depth = [cell(np.isfinite(depth) & (depth >= lo) & (depth < hi), f"{lo:+.1f} to {hi:+.1f} m") for lo, hi in ((0.0, 0.5), (0.5, 1.0), (1.0, 1.5), (1.5, 2.0), (2.0, 3.0))]
    by_hand = [cell((hand >= lo) & (hand < hi), f"{lo:g}–{hi:g} m") for lo, hi in ((-5, 0), (0, 1), (1, 2), (2, 3), (3, 4), (4, 6))]
    lc_names = {0: "other", 1: "tree cover", 2: "herbaceous wetland", 3: "crop, grass, shrub"}
    by_lc = [cell(lc == k, name) for k, name in lc_names.items()]
    total = score(pred, wet, dry)
    want = {k: sum(check_counts(r)[k] for r in judged) for k in ("tp", "fn", "fp", "tn")}
    assert {"tp": total.tp, "fn": total.fn, "fp": total.fp, "tn": total.tn} == want
    return {"group": name, "passes": [f"{r['river']} {r['pair']}" for r in judged], "pooled": want,
            "by_depth": [c for c in by_depth if c], "by_hand": [c for c in by_hand if c], "by_landcover": [c for c in by_lc if c]}


# ---------- Fig. 1: study design ----------
def study(metrics, manifest, heldout):
    roles = {}
    for r in metrics["held_out"]:
        roles.setdefault(r["site"], "held-out")
    for s in manifest["sites"]:
        roles.setdefault(s["id"], "development")
    rivers = []
    for name, role in roles.items():
        cfg = tomllib.loads((REPO_ROOT / "sites" / f"{name}.toml").read_text(encoding="utf8"))
        w, s, e, n = cfg["bbox"]
        passes = [{"pair": k, "time": v["wet_time"]} for k, v in cfg.get("pairs", {}).items()]
        tested = {r["pair"] for r in metrics["held_out"] if r["site"] == name}
        for p in passes:
            p["tested"] = p["pair"] in tested
        hydro = None
        for path in (APP / "dashboard" / f"{name}_gauges.json", APP / name / "gauges.json"):
            if path.exists():
                g = json.loads(path.read_text(encoding="utf8"))
                times = g[0]["times"][::6]
                # the river's rise and fall, relative to its own range, averaged over its gauges (a sketch, not a level)
                rows = [np.array([np.nan if v is None else v for v in x["stage_ft"][::6]], float) for x in g]
                rows = [(x - np.nanmin(x)) / max(1e-6, np.nanmax(x) - np.nanmin(x)) for x in rows if np.isfinite(x).sum() > 2]
                if rows:
                    m = np.nanmean(np.vstack([x[: len(times)] for x in rows]), axis=0)
                    hydro = {"times": times, "rel": [r3(v) for v in m]}
                break
        rivers.append({"id": name, "role": role, "center": [round((w + e) / 2, 3), round((s + n) / 2, 3)], "bbox": cfg["bbox"], "passes": passes, "hydro": hydro,
                       "labelled_ha": sum((r.get("confirmed_ha") or r.get("estimated_ha") or 0) for r in metrics["held_out"] if r["site"] == name)})
    gfm = [{"river": a["site"], "date": a["date"]} for a in metrics["audit"]]
    # a coastline for the region, from the same Natural Earth file the atlas uses
    geo = json.loads((REPO_ROOT / "outputs" / "atlas" / "ne_countries.geojson").read_text(encoding="utf8"))
    box = (-100.0, 24.0, -74.0, 38.0)
    rings = []
    for f in geo["features"]:
        if f["properties"].get("ADMIN", f["properties"].get("NAME")) not in ("United States of America", "Mexico", "Cuba", "The Bahamas", "Bahamas"):
            continue
        g = f["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        for poly in polys:
            ring = [p for p in poly[0] if box[0] - 3 <= p[0] <= box[2] + 3 and box[1] - 3 <= p[1] <= box[3] + 3]
            if len(ring) > 8:
                rings.append([[round(x, 2), round(y, 2)] for x, y in ring[::2]])
    return {"rivers": rivers, "gfm": gfm, "box": box, "coast": rings}


# ---------- Fig. 6: a flood through time ----------
def through_time(manifest):
    site = next(s for s in manifest["sites"] if s.get("timeline"))
    g = json.loads((APP / site["gauges"]).read_text(encoding="utf8"))
    gauges = [{"name": x["name"], "times": x["times"][::3], "stage_m": [None if v is None else round(v * 0.3048, 3) for v in x["stage_ft"][::3]]} for x in g]
    frames = [{k: f.get(k) for k in ("pair", "time", "flagged_ha", "confirmed_ha", "static_ha", "csi", "csi_ci95", "frozen", "confident")} for f in site["timeline"]]
    return {"river": site["id"], "gauges": gauges, "frames": frames, "unusable": site.get("unusable", [])}


# ---------- Fig. 8: worldwide ----------
def world():
    s = json.loads((APP / "atlas" / "summary.json").read_text(encoding="utf8"))
    lat_flood, lat_tree = np.zeros(180), np.zeros(180)
    for name in s["cell_files"]:
        lat0, _lon0 = (int(x) for x in name.split("_"))
        a = np.frombuffer((APP / "atlas" / "cells" / f"{name}.bin").read_bytes(), "<u2").reshape(2, 100, 100) / 100.0
        for row in range(100):                     # row 0 is the northern edge
            lat = lat0 + 10 - (row + 0.5) * 0.1
            k = int(np.floor(lat)) + 90
            lat_flood[k] += a[0, row].sum()
            lat_tree[k] += a[1, row].sum()
    assert abs(lat_tree.sum() - s["tree_km2"]) / s["tree_km2"] < 0.01, (lat_tree.sum(), s["tree_km2"])
    towns = json.loads((APP / "atlas" / "towns.json").read_text(encoding="utf8"))
    per_country = {}
    alias = {"United States": "United States of America", "French Guiana": "France"}   # GeoNames names against Natural Earth's
    for t in towns:
        k = alias.get(t[1], t[1])
        per_country[k] = per_country.get(k, 0) + 1
    assert set(per_country) <= {c["name"] for c in s["countries"]}, set(per_country) - {c["name"] for c in s["countries"]}
    countries = [{"name": c["name"], "floodplain_km2": c["floodplain_km2"], "tree_km2": c["tree_km2"], "share": c["share"], "towns": per_country.get(c["name"], 0)}
                 for c in s["countries"] if c["floodplain_km2"] >= 1000]
    return {"lat": list(range(-90, 90)), "floodplain_km2": [round(x) for x in lat_flood], "tree_km2": [round(x) for x in lat_tree],
            "totals": {"floodplain_km2": s["floodplain_km2"], "tree_km2": s["tree_km2"]}, "countries": countries, "check_areas": s["check"]["areas"],
            "check": {"excl_trees": s["check"]["gfm_excludes_share_under_trees"], "excl_else": s["check"]["gfm_excludes_share_elsewhere"]}}


# ---------- the bare-earth test: scores only (FABDEM is CC BY-NC-SA, so no layer derived from it goes in the app) ----------
ELEV_MAPS = ("nisar_with_lidar", "nisar_with_copernicus", "nisar_with_fabdem", "fabdem_height_map", "lidar_height_map", "copernicus_height_map")


def elevation():
    res = json.loads((RESEARCH / "bare_earth_results.json").read_text(encoding="utf8"))
    rows = [{"site": p["site"], "pair": p["pair"], **{m: r3(p["maps"][m]["csi"]) for m in ELEV_MAPS},
             "fabdem_minus_copernicus": r3(p["q1_fabdem_minus_copernicus"]["difference"]),
             "fabdem_minus_copernicus_ci95": [r3(x) for x in p["q1_fabdem_minus_copernicus"]["ci95"]],
             "best_limit_csi": r3(p["best_limit_csi"]), "best_limit_m": p["best_limit_m"]} for p in res["passes"]]
    means = {m: r3(np.mean([p["maps"][m]["csi"] for p in res["passes"]])) for m in ELEV_MAPS}
    means["best_limit_csi"] = r3(np.mean([p["best_limit_csi"] for p in res["passes"]]))
    # the means must give back the run's own readings
    assert abs(means["nisar_with_fabdem"] - means["nisar_with_copernicus"] - res["readings"]["q1"]["mean_gain"]) < 1e-3
    assert abs(means["nisar_with_lidar"] - means["nisar_with_fabdem"] - res["readings"]["q3"]["mean_gap"]) < 1e-3
    r = res["readings"]
    return {"rows": rows, "means": means,
            "readings": {"q1": r["q1"]["reading"], "q1_won": r["q1"]["passes_won"], "q1_lost": r["q1"]["passes_lost"],
                         "area_ratio_vs_lidar": r3(r["q1"]["area_ratio_vs_lidar"]), "q2": r["q2"]["reading"], "q3": r["q3"]["reading"], "p1_median_m": r3(r["mechanism"]["p1_hero_median_m"])},
            "attribution": "FABDEM V1-2 (Hawker et al. 2022, CC BY-NC-SA 4.0). FABDEM is produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved."}


def main():
    metrics = json.loads((APP / "metrics.json").read_text(encoding="utf8"))
    manifest = json.loads((APP / "manifest.json").read_text(encoding="utf8"))
    heldout = json.loads((APP / "dashboard" / "heldout.json").read_text(encoding="utf8"))
    runs = frozen_runs()
    for r in runs:
        check_counts(r)
    sig = signature(runs, heldout)
    jdump("signature.json", {**sig, **curves(heldout, manifest)})
    sep = separability(runs, metrics["overbank"])
    jdump("separability.json", sep)
    jdump("strata.json", strata(runs, {(x["river"], x["pair"]): x["trust"] for x in sep["passes"]}))
    jdump("study.json", study(metrics, manifest, heldout))
    jdump("time.json", through_time(manifest))
    jdump("world.json", world())
    hidden = json.loads((RESEARCH / "hidden_gauge.json").read_text(encoding="utf8"))
    jdump("reference.json", {"cases": hidden["cases"], "summary": hidden["all"]})
    audit = json.loads((RESEARCH / "audit_base_rate.json").read_text(encoding="utf8"))
    jdump("audit.json", {"rows": [{k: a.get(k) for k in ("site", "date", "estimated_ha", "gfm_on_wet_ha", "wet_share_in_mask", "dry_share_in_mask", "difference_ci95")} for a in audit]})
    if (RESEARCH / "bare_earth_results.json").exists():
        jdump("elevation.json", elevation())
    print(f"figures: {len(runs)} frozen runs, ridgeline medians within {sig['check']['max_median_diff_db']} dB, ROC areas within {sep['check']['max_auc_diff']}")


if __name__ == "__main__":
    main()
