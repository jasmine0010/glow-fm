"""Checks on the results page's figure data (scripts/build_figures.py writes app/data/figures/).

The build already asserts its own consistency checks before writing. These tests re-read what it wrote and hold it to the
records it came from, so a stale or hand-edited figure file fails here too. They skip if the app data hasn't been built.
"""

import importlib.util
import json
from itertools import pairwise
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
FIGS = ROOT / "app" / "data" / "figures"
APP = ROOT / "app" / "data"
RESEARCH = ROOT / "research"

needs_build = pytest.mark.skipif(not (FIGS / "signature.json").exists(), reason="app data not built (scripts/build_app.py)")


def load(name):
    return json.loads((FIGS / f"{name}.json").read_text(encoding="utf8"))


def build_figures():
    spec = importlib.util.spec_from_file_location("build_figures", ROOT / "scripts" / "build_figures.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_auc_is_the_rank_statistic():
    auc_from = build_figures().auc_from
    x = np.arange(200, dtype=float)
    wet, dry = x >= 100, x < 100
    assert auc_from(x, wet, dry) == pytest.approx(1.0)        # every flooded pixel brighter than every dry one
    assert auc_from(-x, wet, dry) == pytest.approx(0.0)
    rng = np.random.default_rng(0)
    y = rng.normal(size=4000)
    w = np.zeros(4000, bool)
    w[::2] = True
    assert auc_from(y, w, ~w) == pytest.approx(0.5, abs=0.03)  # no signal
    assert auc_from(x, wet & (x < 120), dry) is None           # too few pixels to say


@needs_build
def test_ridgeline_counts_and_medians():
    sig = load("signature")
    assert sig["check"]["max_median_diff_db"] < 0.02            # medians agree with the stored response curves
    edges = sig["hh_edges"]
    for b in sig["bins"]:
        assert len(b["counts"]) == len(edges) - 1
        assert sum(b["counts"]) == b["n"]                       # values outside the axis are clipped in, not dropped
        q = b["hh_q"]
        if b["n"] >= 40:
            assert q[0] <= q[1] <= q[2]
    sep = load("separability")
    assert sig["pooled_from"] == [f"{p['river']} {p['pair']}" for p in sep["passes"]]


@needs_build
def test_roc_areas_match_the_record():
    sep = load("separability")
    stored = {(p["river"], p["pair"]): p["auc_hh"] for p in json.loads((RESEARCH / "rainfall_by_pass.json").read_text(encoding="utf8"))["passes"]}
    checked = 0
    for p in sep["passes"]:
        roc = np.array(p["roc"])
        assert np.all(np.diff(roc[:, 0]) >= -1e-9) and np.all(np.diff(roc[:, 1]) >= -1e-9)
        assert roc[-1].tolist() == [1.0, 1.0]
        # the trapezoid area under the plotted curve is close to the exact rank AUC
        assert np.trapezoid(roc[:, 1], roc[:, 0]) == pytest.approx(p["auc"], abs=0.02)
        if p["river"] in ("pee_dee", "neuse", "lower_sabine"):
            assert p["auc"] == pytest.approx(stored[(p["river"], p["pair"])], abs=0.005)
            checked += 1
    assert checked == 3


@needs_build
def test_strata_against_the_frozen_scores():
    metrics = json.loads((APP / "metrics.json").read_text(encoding="utf8"))
    green, everything = load("strata")["groups"]
    assert set(green["passes"]) <= set(everything["passes"])
    for g in (green, everything):
        t = g["pooled"]
        for key in ("by_depth", "by_hand", "by_landcover"):
            for c in g[key]:
                if c["recall_ci"] and c["recall"] is not None:
                    assert c["recall_ci"][0] - 1e-3 <= c["recall"] <= c["recall_ci"][1] + 1e-3
        # land-cover strata partition the scored pixels (only tiny classes are left out)
        assert sum(c["n_wet"] for c in g["by_landcover"]) <= t["tp"] + t["fn"]
        assert sum(c["n_wet"] for c in g["by_landcover"]) >= 0.99 * (t["tp"] + t["fn"])
    # pooled over one pass, the counts give back that pass's frozen CSI
    for name in green["passes"]:
        river, pair = name.split()
        row = next(r for r in metrics["held_out"] if r["site"] == river and r["pair"] == pair and r["method"].startswith("v4, overbank"))
        sep = next(p for p in load("separability")["passes"] if p["river"] == river and p["pair"] == pair)
        assert sep["csi"] == pytest.approx(row["csi"], abs=1e-3)


@needs_build
def test_world_profile_and_towns():
    w = load("world")
    assert sum(w["tree_km2"]) == pytest.approx(w["totals"]["tree_km2"], rel=0.01)
    summary = json.loads((APP / "atlas" / "summary.json").read_text(encoding="utf8"))
    towns = sum(c["towns"] for c in w["countries"])
    assert 0.95 * summary["towns"]["high"] <= towns <= summary["towns"]["high"]
    assert w["check"]["excl_trees"] == summary["check"]["gfm_excludes_share_under_trees"]


@needs_build
def test_copied_records_are_unchanged():
    audit = json.loads((RESEARCH / "audit_base_rate.json").read_text(encoding="utf8"))
    rows = load("audit")["rows"]
    assert [(r["site"], r["date"], r["estimated_ha"], r["gfm_on_wet_ha"]) for r in rows] == [(a["site"], a["date"], a["estimated_ha"], a["gfm_on_wet_ha"]) for a in audit]
    ref = load("reference")
    errs = [abs(c["error_m"]) for c in ref["cases"]]
    assert ref["summary"]["cases"] == len(ref["cases"])
    assert float(np.median(errs)) == pytest.approx(ref["summary"]["median_abs_error_m"], abs=0.002)
    assert max(errs) == pytest.approx(ref["summary"]["worst_abs_error_m"], abs=0.002)


@needs_build
def test_time_series_is_in_metres_on_real_dates():
    t = load("time")
    frames = [np.datetime64(f["time"].replace("Z", "")) for f in t["frames"]]
    assert all(b > a for a, b in pairwise(frames))
    for g in t["gauges"]:
        v = np.array([x for x in g["stage_m"] if x is not None])
        assert 0 < v.max() - v.min() < 10                        # a river's rise in metres, not feet


@needs_build
def test_elevation_table_matches_the_frozen_run():
    path = RESEARCH / "bare_earth_results.json"
    if not path.exists():
        pytest.skip("bare-earth test not run")
    res = json.loads(path.read_text(encoding="utf8"))
    e = load("elevation")
    assert [(r["site"], r["pair"]) for r in e["rows"]] == [(p["site"], p["pair"]) for p in res["passes"]]
    for row, p in zip(e["rows"], res["passes"], strict=True):
        for m in ("nisar_with_lidar", "nisar_with_copernicus", "nisar_with_fabdem", "fabdem_height_map"):
            assert row[m] == pytest.approx(p["maps"][m]["csi"], abs=1e-4)
        assert row["fabdem_minus_copernicus_ci95"] == pytest.approx(p["q1_fabdem_minus_copernicus"]["ci95"], abs=1e-4)
    assert e["readings"]["q1"] == res["readings"]["q1"]["reading"]


@pytest.mark.skipif(not (APP / "story" / "thread.json").exists(), reason="thread not built (scripts/build_thread.py)")
def test_thread_particles_match_the_frozen_pass():
    t = json.loads((APP / "story" / "thread.json").read_text(encoding="utf8"))
    f = t["fields"]
    p = np.array(t["particles"], dtype=float)
    wet = p[:, f.index("wet")] == 1
    frozen = json.loads((RESEARCH / f"overbank_{t['site']}_{t['pass']}_frozen_metrics.json").read_text(encoding="utf8"))
    assert t["csi"] == pytest.approx(frozen["v4_csi"], abs=1e-4)
    assert wet.sum() * t["unit_ha"] == pytest.approx(t["wet_ha"], rel=0.01)                      # one particle per SAMPLE flooded pixels
    assert p[wet, f.index("nisar")].mean() == pytest.approx(t["recall"], abs=0.03)
    assert np.all(p[wet, f.index("water_m")] > 0) and np.all(p[~wet, f.index("water_m")] < 0)
    covered = p[wet, f.index("gfm_covered")] == 1
    assert p[wet, f.index("gfm_excluded")][covered].mean() == pytest.approx(t["mask_share_wet"], abs=0.03)


@pytest.mark.skipif(not (FIGS / "coverage.json").exists(), reason="coverage not built (scripts/build_coverage.py)")
def test_coverage_summary_matches_its_floods():
    c = load("coverage")
    s, rows = c["summary"], c["floods"]
    lat = np.array([x for r in rows for x in r["latency_days"]])
    assert s["floods"] == len(rows) and s["scenes"] == lat.size
    assert s["covered"] == sum(1 for r in rows if r["passes"]) and s["covered_by_method_kind"] == sum(1 for r in rows if r["method_passes"])
    assert s["ready_during_flood"] == sum(1 for r in rows if r["ready_during_flood"])
    assert s["latency_days"]["median"] == pytest.approx(float(np.median(lat)), abs=0.05)
    assert s["latency_days"]["share_over_7"] == pytest.approx(float((lat > 7).mean()), abs=1e-3)
    for r in rows:   # a scene can't be usable before it was recorded, nor recorded before the flood began
        if r["passes"]:
            assert 0 <= r["first_pass_days"] <= r["first_ready_days"]
