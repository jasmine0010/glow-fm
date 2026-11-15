"""End-to-end extent evaluation for one site and one change pair, following the protocol:

1. build features and hydraulic truth on the analysis grid;
2. choose the ΔHH threshold on the calibration reach only (CSI-best) and write it to ``frozen_rule.json``;
3. only then score the test reach, with block-bootstrap intervals, and write ``metrics.json``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from hidden_floods.config import REPO_ROOT, Site
from hidden_floods.detect import ChangeRule, PairFeatures, pair_features
from hidden_floods.grid import Grid, grid_from_lonlat_bbox
from hidden_floods.io.dem import dem_on_grid
from hidden_floods.io.gauges import usgs_series, water_surface_navd88_m
from hidden_floods.io.nisar import identification, read_gcov
from hidden_floods.io.operational import gfm_mosaic
from hidden_floods.metrics import block_bootstrap, block_ids, score, sweep_threshold
from hidden_floods.truth import TruthLabels, ValleyLine, hydraulic_truth, refine_centerline


@dataclass
class ExtentInputs:
    grid: Grid
    features: PairFeatures
    truth: TruthLabels
    line: ValleyLine
    gauge_wse_m: dict[str, float]
    channel: np.ndarray


def analysis_grid(site: Site) -> Grid:
    return grid_from_lonlat_bbox(site.bbox, site.crs, site.resolution_m)


def gauge_water_surfaces(site: Site, when: str) -> dict[str, float]:
    return {g.name: water_surface_navd88_m(g, usgs_series(site.gauges_dir, g).at(when)) for g in site.gauges}


def build_inputs(site: Site, pair_name: str, channel_date: str = "20261022", connectivity: bool = True) -> ExtentInputs:
    grid = analysis_grid(site)
    pair = site.pairs[pair_name]
    feats = pair_features(read_gcov(site.gcov_path(pair.dry), grid), read_gcov(site.gcov_path(pair.wet), grid))
    dem = dem_on_grid(site.dem_path, grid)
    # Channel = GFM reference (permanent) water; used to re-centre the valley line and seed connectivity.
    channel = gfm_mosaic(site.operational_dir, channel_date, grid).reference_water
    coarse = ValleyLine.from_lonlat(grid, site.valley_line)
    dist, _ = coarse.project(*grid.meshgrid())
    line = refine_centerline(coarse, channel & (dist < site.corridor_m), grid)
    wse = gauge_water_surfaces(site, pair.wet_time)
    gauge_xy = [grid.to_xy(g.lon, g.lat) for g in site.gauges]
    seeds = channel if connectivity else None
    truth = hydraulic_truth(grid, dem, line, gauge_xy, [wse[g.name] for g in site.gauges], site.corridor_m,
                            site.margin_m, site.max_dry_height_m, channel_seeds=seeds)
    return ExtentInputs(grid, feats, truth, line, wse, channel)


def evaluate_extent(site: Site, pair_name: str, out_dir: Path | None = None, connectivity: bool = True,
                    n_boot: int = 2000) -> dict:
    out_dir = Path(out_dir or REPO_ROOT / "outputs" / site.name / pair_name)
    out_dir.mkdir(parents=True, exist_ok=True)
    inp = build_inputs(site, pair_name, connectivity=connectivity)
    t, f = inp.truth, inp.features
    cal = t.chainage_m < site.calibration_max_chainage_m
    test = ~cal
    eligible = ChangeRule(0.0, site.forest_hv_db).forest(f)

    # --- calibration (calibration reach only) ---
    rows, best = sweep_threshold(f.d_hh, eligible, t.wet, t.dry, cal, site.thresholds_db)
    rule = ChangeRule(best, site.forest_hv_db)
    frozen = {"site": site.name, "pair": pair_name, "rule": rule.to_dict(), "selected_on": "calibration reach",
              "calibration_max_chainage_m": site.calibration_max_chainage_m, "sweep": rows,
              "connectivity": connectivity}
    (out_dir / "frozen_rule.json").write_text(json.dumps(frozen, indent=2))

    # --- test (after the rule is written) ---
    pred = rule.apply(f)
    blocks = block_ids(t.chainage_m, site.bootstrap_block_m)
    area = inp.grid.pixel_area_ha
    result = {
        "site": site.name, "pair": pair_name, "rule": rule.to_dict(),
        "gauge_wse_navd88_m": inp.gauge_wse_m,
        "truth_ha": {"wet": float(t.wet.sum() * area), "dry": float(t.dry.sum() * area),
                     "wet_cal": float((t.wet & cal).sum() * area), "wet_test": float((t.wet & test).sum() * area)},
        "calibration": score(pred, t.wet, t.dry, cal).to_dict(area),
        "test": score(pred, t.wet, t.dry, test).to_dict(area),
        "test_ci95": block_bootstrap(pred, t.wet, t.dry, blocks, test, n_boot=n_boot),
        "flagged_ha_in_corridor": float((pred & t.corridor).sum() * area),
        "provenance": {"wet": identification(site.gcov_path(site.pairs[pair_name].wet)),
                       "dry": identification(site.gcov_path(site.pairs[pair_name].dry))},
        "connectivity": connectivity,
    }
    (out_dir / "metrics.json").write_text(json.dumps(result, indent=2, default=str))
    np.savez_compressed(out_dir / "layers.npz", pred=pred, wet=t.wet, dry=t.dry, chainage=t.chainage_m,
                        d_hh=f.d_hh.astype(np.float32), corridor=t.corridor)
    return result
