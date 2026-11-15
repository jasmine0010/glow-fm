"""Frozen evaluation of method v4 on three new rivers — research/V4_PROTOCOL.md.

Scenes come from ``research/v4_test_scenes.json`` and are read as corridor-only windows. The run refuses to start if any
hashed file has changed, logs each attempt before reading imagery, writes each result once and refuses to overwrite it.
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
from hidden_floods.detect import ChangeRule, PairFeatures
from hidden_floods.frozen_edouard import upland_warning
from hidden_floods.frozen_v3 import RECEIPT_V3, paired_csi_difference, settings_from
from hidden_floods.io.dem import dem_on_grid
from hidden_floods.io.gauges import usgs_series
from hidden_floods.metrics import block_bootstrap, block_ids, score
from hidden_floods.pipeline import analysis_grid
from hidden_floods.selfcal import height_above_river
from hidden_floods.stack import Scene, read_scene
from hidden_floods.trust import timing_class, worldcover_class, worldcover_on_grid
from hidden_floods.v3 import peak_envelope_wet, peak_stage_wse
from hidden_floods.v4 import V4Rule, median_baseline

RECEIPT = REPO_ROOT / "research" / "freeze_receipt_v4.json"
SCENES = REPO_ROOT / "research" / "v4_test_scenes.json"
HASHED = ("research/V4_PROTOCOL.md", "research/v4_test_scenes.json", "research/freeze_receipt_v3.json", "sites/pee_dee.toml", "sites/neuse.toml", "sites/lower_sabine.toml",
          "scripts/run_frozen_v4.py", "src/hidden_floods/frozen_v4.py", "src/hidden_floods/v4.py", "src/hidden_floods/stack.py", "src/hidden_floods/v3.py",
          "src/hidden_floods/frozen_v3.py", "src/hidden_floods/frozen_edouard.py", "src/hidden_floods/trust.py", "src/hidden_floods/audit.py", "src/hidden_floods/selfcal.py",
          "src/hidden_floods/detect.py", "src/hidden_floods/truth.py", "src/hidden_floods/metrics.py", "src/hidden_floods/grid.py", "src/hidden_floods/config.py",
          "src/hidden_floods/pipeline.py", "src/hidden_floods/frozen.py", "src/hidden_floods/io/nisar.py", "src/hidden_floods/io/gauges.py", "src/hidden_floods/io/dem.py")
PASSES = {"pee_dee": "098D_jul27", "neuse": "090A_jul26", "lower_sabine": "134A_jul17"}


def digest(rel: str) -> str:
    return hashlib.sha256((REPO_ROOT / rel).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def check_receipt(path: Path = RECEIPT) -> list[str]:
    rec = json.loads(Path(path).read_text())
    return [r for r in HASHED if rec["sha256"].get(r) != digest(r)]


def rule_from(rec: dict) -> V4Rule:
    r = {k: v for k, v in rec["v4_rule"].items() if k != "type"}
    r["landcover"], r["abstain_timing"] = tuple(r["landcover"]), tuple(r["abstain_timing"])
    return V4Rule(**r)


def _git_head() -> str:
    run = subprocess.run(["git", "rev-parse", "HEAD"], check=False, cwd=REPO_ROOT, capture_output=True, text=True)
    return run.stdout.strip() if run.returncode == 0 else "no commit"


def evaluate_v4(site: Site, pair_name: str, scenes: list[Scene], rule: V4Rule, out_dir: Path | None = None, regression_check: bool = False) -> dict:
    """Score one frozen pass. ``regression_check`` runs a spent river in a caller-chosen folder, with no hash gate."""
    if regression_check:
        if site.name in PASSES:
            raise ValueError(f"{site.name} is held out: regression checks may not read it")
        if out_dir is None:
            raise ValueError("a regression check needs its own out_dir")
    elif PASSES.get(site.name) != pair_name:
        raise ValueError(f"{site.name}/{pair_name} is not a frozen v4 pass")
    out_dir = Path(out_dir or REPO_ROOT / "outputs" / site.name / pair_name)
    result_path = out_dir / "frozen_v4_metrics.json"
    if result_path.exists():
        raise FileExistsError(f"{result_path} exists; each frozen v4 pass runs once")
    if not regression_check:
        changed = check_receipt()
        if changed:
            raise RuntimeError(f"changed since the freeze, not running: {changed}")
    cfg = settings_from(json.loads(RECEIPT_V3.read_text()))

    out_dir.mkdir(parents=True, exist_ok=True)
    attempt = {"started_utc": datetime.now(UTC).isoformat(timespec="seconds"), "git_head": _git_head(), "site": site.name,
               "pair": pair_name, "regression_check": regression_check}
    with open(out_dir / "frozen_v4_attempts.log", "a") as log:   # written before any imagery is read
        log.write(json.dumps(attempt) + "\n")

    grid = analysis_grid(site)
    pair = site.pairs[pair_name]
    dem = dem_on_grid(site.dem_path, grid)
    ctx = truth_context(site, pair.wet_time, dem=dem, grid=grid)
    t = ctx.truth
    wet_name, dry_name = Path(site.gcov[pair.wet]).name, Path(site.gcov[pair.dry]).name
    by_name = {s.name: s for s in scenes}
    wet, dry = read_scene(site, grid, by_name[wet_name]), read_scene(site, grid, by_name[dry_name])
    base_scenes = [s for s in scenes if s.time[:10] != pair.wet_time[:10]]
    stack = [read_scene(site, grid, s) for s in base_scenes]
    hh_base, hv_base = median_baseline(np.stack([x["hh"] for x in stack])), median_baseline(np.stack([x["hv"] for x in stack]))

    hand = height_above_river(dem, t.distance_m, t.chainage_m)
    lc = worldcover_class(worldcover_on_grid(data_root() / "worldcover", grid))
    classes = np.array([timing_class(usgs_series(site.gauges_dir, g), pair.wet_time) for g in site.gauges], np.uint8)
    timing = classes[np.argmin(np.abs(t.chainage_m[..., None] - np.asarray(ctx.gauge_chainage_m)), axis=-1)]
    crest = peak_envelope_wet(site, grid, dem, ctx.line, ctx.permanent_water, peak_stage_wse(site, pair.dry_time, pair.wet_time))
    ambiguous = t.dry & crest & ~t.wet

    v4 = rule.apply(wet["hh"] - hh_base, wet["hv"] - hv_base, lc, timing, hand, t.distance_m)
    single = rule.apply(wet["hh"] - dry["hh"], wet["hv"] - dry["hv"], lc, timing, hand, t.distance_m)
    feats = PairFeatures(dry["hh"], dry["hv"], wet["hh"], wet["hv"])
    v3_pred, v3_mapped, v3_thr = cfg.rule.apply(feats, lc, timing, hand, t.distance_m)
    v1_pred = ChangeRule(cfg.v1.d_hh_db, cfg.v1.forest_hv_db).apply(feats)

    blocks = block_ids(t.chainage_m, cfg.block_m)
    area = grid.pixel_area_ha
    region = ctx.supported & ~ctx.permanent_water
    scored = region & v4["mapped"]

    def report(p, reg, dry_labels=t.dry):
        s = score(p, t.wet, dry_labels, reg)
        judged = s.tp + s.fn + s.fp > 0
        ci = block_bootstrap(p, t.wet, dry_labels, blocks, reg, n_boot=cfg.n_boot, seed=cfg.seed) if judged else None
        return {"scores": s.to_dict(area), "ci95": ci}

    labelled = (t.wet | t.dry) & scored
    wet_region = t.wet & region
    diff = lambda a, b: paired_csi_difference(a, b, t.wet, t.dry, blocks, scored, cfg.n_boot, cfg.seed) if labelled.any() else None
    result = {
        "site": site.name, "pair": pair_name, "protocol": "research/V4_PROTOCOL.md", "regression_check": regression_check, "attempt": attempt,
        "v4_rule": rule.to_dict(), "v4_threshold_db": v4["threshold_db"], "v3_threshold_db": v3_thr, "used_hh_minus_hv": v4["used_hh_minus_hv"],
        "confident": v4["confident"], "low_minus_high_db": v4["low_minus_high_db"], "high_ground_db": v4["high_db"],
        "baseline_scenes": [s.time[:10] for s in base_scenes], "upland_warning": upland_warning(wet["hh"] - dry["hh"], feats.valid, lc, hand, t.distance_m),
        "gauge_wse_navd88_m": ctx.gauge_wse_m, "gauge_timing_class": {g.name: int(c) for g, c in zip(site.gauges, classes, strict=True)},
        "coverage_of_confirmed_flooding": float((wet_region & v4["mapped"]).sum() / wet_region.sum()) if wet_region.any() else None,
        "truth_ha": {"wet_primary": float((t.wet & scored).sum() * area), "dry_primary": float((t.dry & scored).sum() * area),
                     "wet_supported": float(wet_region.sum() * area), "ambiguous_left_out": float((ambiguous & scored).sum() * area)},
        "primary_v4": report(v4["pred"], scored), "baseline_v3_same_pixels": report(v3_pred, scored), "baseline_v1_same_pixels": report(v1_pred, scored),
        "secondary_v4_ponding_tolerant": report(v4["pred"], scored, t.dry & ~ambiguous), "secondary_v4_single_dry_pass": report(single["pred"], scored),
        "secondary_v4_full_corridor": report(v4["pred"], v4["mapped"] & ~ctx.permanent_water),
        "v4_minus_v3_csi": diff(v4["pred"], v3_pred), "v4_minus_v1_csi": diff(v4["pred"], v1_pred),
        "by_landcover": {name: report(v4["pred"], scored & (lc == code)) for code, name in
                         ((1, "tree cover"), (2, "herbaceous wetland"), (0, "other"), (3, "crop/grass/shrub")) if (t.wet & scored & (lc == code)).any()},
        "scenes": {"wet": wet_name, "dry": dry_name},
    }
    result_path.write_text(json.dumps(result, indent=2, default=str))
    np.savez_compressed(out_dir / "frozen_v4_layers.npz", pred=v4["pred"], v3_pred=v3_pred, mapped=v4["mapped"], wet=t.wet, dry=t.dry, region=region,
                        landcover=lc, timing=timing, chainage=t.chainage_m, hand=hand.astype(np.float32), depth=t.depth_m.astype(np.float32),
                        d_hh=(wet["hh"] - hh_base).astype(np.float32), d_hv=(wet["hv"] - hv_base).astype(np.float32))
    return result
