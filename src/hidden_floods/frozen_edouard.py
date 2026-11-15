"""Frozen evaluation of method v3 on Tropical Storm Edouard — research/EDOUARD_PROTOCOL.md.

The v3 rule comes from ``research/freeze_receipt_v3.json``, unchanged. The Edouard receipt adds the two rivers, the
pair choices and the upland warning. The run refuses to start if any hashed file has changed, logs each attempt before
reading imagery, writes each result once and refuses to overwrite it.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from hidden_floods.audit import truth_context
from hidden_floods.config import REPO_ROOT, Site, data_root
from hidden_floods.detect import pair_features
from hidden_floods.frozen_v3 import HASHED_V3, RECEIPT_V3, paired_csi_difference, settings_from
from hidden_floods.io.dem import dem_on_grid
from hidden_floods.io.gauges import usgs_series
from hidden_floods.io.nisar import identification, read_gcov
from hidden_floods.metrics import block_bootstrap, block_ids, score
from hidden_floods.pipeline import analysis_grid
from hidden_floods.selfcal import height_above_river
from hidden_floods.trust import timing_class, worldcover_class, worldcover_on_grid
from hidden_floods.v3 import LC_TREE, peak_envelope_wet, peak_stage_wse

RECEIPT = REPO_ROOT / "research" / "freeze_receipt_edouard.json"
HASHED = (*HASHED_V3, "research/EDOUARD_PROTOCOL.md", "research/freeze_receipt_v3.json", "sites/village_creek.toml",
          "sites/pine_island.toml", "scripts/run_frozen_edouard.py", "src/hidden_floods/frozen_edouard.py")
PASSES = {"village_creek": ("134A_sep03", "012D_sep07"), "pine_island": ("012D_sep07", "134A_sep03")}
WARNING_DB = 0.5
MIN_UPLAND_PX = 500


def digest(rel: str) -> str:
    return hashlib.sha256((REPO_ROOT / rel).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def check_receipt(path: Path = RECEIPT) -> list[str]:
    rec = json.loads(Path(path).read_text())
    return [r for r in HASHED if rec["sha256"].get(r) != digest(r)]


def upland_warning(d_hh, valid, landcover, hand, dist, hand_min_m=12.0, max_dist_m=15000.0, min_px=MIN_UPLAND_PX) -> dict:
    """Median HH change over upland forest, and whether the scene-wide warning fires. Needs no truth."""
    m = valid & (landcover == LC_TREE) & (hand > hand_min_m) & (dist < max_dist_m)
    if m.sum() < min_px:
        return {"upland_hh_db": None, "upland_px": int(m.sum()), "warned": None}
    u = float(np.median(d_hh[m]))
    return {"upland_hh_db": u, "upland_px": int(m.sum()), "warned": abs(u) > WARNING_DB}


def _git_head() -> str:
    run = subprocess.run(["git", "rev-parse", "HEAD"], check=False, cwd=REPO_ROOT, capture_output=True, text=True)
    return run.stdout.strip() if run.returncode == 0 else "no commit"


def evaluate_edouard(site: Site, pair_name: str, out_dir: Path | None = None, regression_check: bool = False) -> dict:
    """Score one frozen pass. ``regression_check`` runs a spent river in a caller-chosen folder, with no hash gate."""
    if regression_check:
        if site.name in PASSES:
            raise ValueError(f"{site.name} is held out: regression checks may not read it")
        if out_dir is None:
            raise ValueError("a regression check needs its own out_dir")
    elif pair_name not in PASSES.get(site.name, ()):
        raise ValueError(f"{site.name}/{pair_name} is not a frozen Edouard pass")
    out_dir = Path(out_dir or REPO_ROOT / "outputs" / site.name / pair_name)
    result_path = out_dir / "frozen_edouard_metrics.json"
    if result_path.exists():
        raise FileExistsError(f"{result_path} exists; each frozen Edouard pass runs once")
    if not regression_check:
        changed = check_receipt()
        if changed:
            raise RuntimeError(f"changed since the freeze, not running: {changed}")
    cfg = settings_from(json.loads(RECEIPT_V3.read_text()))

    out_dir.mkdir(parents=True, exist_ok=True)
    attempt = {"started_utc": datetime.now(UTC).isoformat(timespec="seconds"), "git_head": _git_head(), "site": site.name,
               "pair": pair_name, "regression_check": regression_check}
    with open(out_dir / "frozen_edouard_attempts.log", "a") as log:   # written before any imagery is read
        log.write(json.dumps(attempt) + "\n")

    grid = analysis_grid(site)
    pair = site.pairs[pair_name]
    dem = dem_on_grid(site.dem_path, grid)
    ctx = truth_context(site, pair.wet_time, dem=dem, grid=grid)
    t = ctx.truth
    feats = pair_features(read_gcov(site.gcov_path(pair.dry), grid), read_gcov(site.gcov_path(pair.wet), grid))
    hand = height_above_river(dem, t.distance_m, t.chainage_m)
    lc = worldcover_class(worldcover_on_grid(data_root() / "worldcover", grid))
    classes = np.array([timing_class(usgs_series(site.gauges_dir, g), pair.wet_time) for g in site.gauges], np.uint8)
    timing = classes[np.argmin(np.abs(t.chainage_m[..., None] - np.asarray(ctx.gauge_chainage_m)), axis=-1)]
    crest = peak_envelope_wet(site, grid, dem, ctx.line, ctx.permanent_water, peak_stage_wse(site, pair.dry_time, pair.wet_time))
    ambiguous = t.dry & crest & ~t.wet

    pred, mapped, thr = cfg.rule.apply(feats, lc, timing, hand, t.distance_m)
    v1_pred = cfg.v1.apply(feats)
    try:
        v2_pred, v2_thr = cfg.v2.apply(feats, hand, t.distance_m)
    except ValueError:                     # too few upland pixels: the v2 baseline cannot run here
        v2_pred, v2_thr = None, None
    blocks = block_ids(t.chainage_m, cfg.block_m)
    area = grid.pixel_area_ha
    region = ctx.supported & ~ctx.permanent_water
    scored = region & mapped

    def report(p, reg, dry=t.dry):
        s = score(p, t.wet, dry, reg)
        judged = s.tp + s.fn + s.fp > 0
        ci = block_bootstrap(p, t.wet, dry, blocks, reg, n_boot=cfg.n_boot, seed=cfg.seed) if judged else None
        return {"scores": s.to_dict(area), "ci95": ci}

    wet_region = t.wet & region
    labelled = (t.wet | t.dry) & scored
    result = {
        "site": site.name, "pair": pair_name, "protocol": "research/EDOUARD_PROTOCOL.md", "regression_check": regression_check,
        "attempt": attempt, "v3_rule": cfg.rule.to_dict(), "v3_threshold_db": thr, "v2_threshold_db": v2_thr,
        "gauge_wse_navd88_m": ctx.gauge_wse_m,
        "gauge_timing_class": {g.name: int(c) for g, c in zip(site.gauges, classes, strict=True)},
        "upland_warning": upland_warning(feats.d_hh, feats.valid, lc, hand, t.distance_m),
        "coverage_of_confirmed_flooding": float((wet_region & mapped).sum() / wet_region.sum()) if wet_region.any() else None,
        "truth_ha": {"wet_primary": float((t.wet & scored).sum() * area), "dry_primary": float((t.dry & scored).sum() * area),
                     "wet_supported": float(wet_region.sum() * area), "ambiguous_left_out": float((ambiguous & scored).sum() * area)},
        "valid_share_of_labelled": float(feats.valid[labelled].mean()) if labelled.any() else None,
        "primary_v3_mapped_area": report(pred, scored),
        "secondary_v3_ponding_tolerant": report(pred, scored, t.dry & ~ambiguous),
        "secondary_v3_full_corridor": report(pred, mapped & ~ctx.permanent_water),
        "baseline_v2_same_pixels": report(v2_pred, scored) if v2_pred is not None else None,
        "baseline_v1_same_pixels": report(v1_pred, scored),
        "v3_minus_v2_csi": paired_csi_difference(pred, v2_pred, t.wet, t.dry, blocks, scored, cfg.n_boot, cfg.seed) if v2_pred is not None and labelled.any() else None,
        "v3_minus_v1_csi": paired_csi_difference(pred, v1_pred, t.wet, t.dry, blocks, scored, cfg.n_boot, cfg.seed) if labelled.any() else None,
        "by_landcover": {name: report(pred, scored & (lc == code)) for code, name in
                         ((1, "tree cover"), (2, "herbaceous wetland"), (0, "other"), (3, "crop/grass/shrub"))
                         if (t.wet & scored & (lc == code)).any()},
        "provenance": {"wet": identification(site.gcov_path(pair.wet)), "dry": identification(site.gcov_path(pair.dry))},
    }
    result_path.write_text(json.dumps(result, indent=2, default=str))
    np.savez_compressed(out_dir / "frozen_edouard_layers.npz", pred=pred, mapped=mapped, v1_pred=v1_pred, wet=t.wet, dry=t.dry,
                        region=region, ambiguous=ambiguous, landcover=lc, timing=timing, chainage=t.chainage_m,
                        hand=hand.astype(np.float32), d_hh=feats.d_hh.astype(np.float32), d_hv=feats.d_hv.astype(np.float32))
    return result
