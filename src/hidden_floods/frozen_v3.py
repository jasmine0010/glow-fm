"""Frozen evaluation of method v3 on the Yellow River — research/V3_YELLOW_PROTOCOL.md.

Settings come from ``research/freeze_receipt_v3.json``. Unlike the v1 and v2 runs, this one refuses to start if any
hashed file has changed. Each attempt is logged before any imagery is read, the result is written once, and
overwriting it is refused. ``development_check=True`` exercises the same code on a spent river for regression only.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from hidden_floods.audit import truth_context
from hidden_floods.config import REPO_ROOT, Site, data_root
from hidden_floods.detect import ChangeRule, pair_features
from hidden_floods.io.dem import dem_on_grid
from hidden_floods.io.gauges import usgs_series
from hidden_floods.io.nisar import identification, read_gcov
from hidden_floods.metrics import block_bootstrap, block_ids, score
from hidden_floods.pipeline import analysis_grid
from hidden_floods.selfcal import SelfCalRule, height_above_river
from hidden_floods.trust import timing_class, worldcover_class, worldcover_on_grid
from hidden_floods.v3 import V3OtsuRule, peak_envelope_wet, peak_stage_wse

RECEIPT_V3 = REPO_ROOT / "research" / "freeze_receipt_v3.json"
HASHED_V3 = ("research/V3_YELLOW_PROTOCOL.md", "sites/yellow.toml", "scripts/run_frozen_v3.py",
             "src/hidden_floods/frozen_v3.py", "src/hidden_floods/v3.py", "src/hidden_floods/trust.py",
             "src/hidden_floods/audit.py", "src/hidden_floods/selfcal.py", "src/hidden_floods/detect.py",
             "src/hidden_floods/truth.py", "src/hidden_floods/metrics.py", "src/hidden_floods/grid.py",
             "src/hidden_floods/config.py", "src/hidden_floods/pipeline.py", "src/hidden_floods/frozen.py",
             "src/hidden_floods/io/nisar.py", "src/hidden_floods/io/gauges.py", "src/hidden_floods/io/dem.py",
             "src/hidden_floods/io/operational.py")
FROZEN_PAIRS = {"yellow": ("004A_oct12", "055D_oct16")}


def digest(rel: str) -> str:
    return hashlib.sha256((REPO_ROOT / rel).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def check_receipt_v3(path: Path = RECEIPT_V3) -> dict:
    rec = json.loads(Path(path).read_text())
    return {"receipt": rec, "changed_since_freeze": [r for r in HASHED_V3 if rec["sha256"].get(r) != digest(r)]}


@dataclass(frozen=True)
class Settings:
    rule: V3OtsuRule
    v1: ChangeRule
    v2: SelfCalRule
    block_m: float
    n_boot: int
    seed: int


def settings_from(rec: dict) -> Settings:
    r3 = {k: v for k, v in rec["v3_rule"].items() if k != "type"}
    r3["landcover"], r3["abstain_timing"] = tuple(r3["landcover"]), tuple(r3["abstain_timing"])
    return Settings(V3OtsuRule(**r3), ChangeRule(rec["v1_rule"]["d_hh_db"], rec["v1_rule"]["forest_hv_db"]),
                    SelfCalRule(**{k: v for k, v in rec["v2_rule"].items() if k != "type"}),
                    rec["metrics"]["bootstrap_block_m"], rec["metrics"]["n_boot"], rec["metrics"]["seed"])


def paired_csi_difference(a, b, wet, dry, blocks, region, n_boot: int = 2000, seed: int = 0) -> dict:
    """CSI(a) - CSI(b) on the same labelled pixels, with one interval from shared block resamples."""
    lab = (wet | dry) & region
    uniq, inv = np.unique(blocks[lab], return_inverse=True)
    pa, pb, w = a[lab], b[lab], wet[lab]
    per = np.zeros((len(uniq), 6))
    for i, (p, q) in enumerate(((pa, w), (~pa, w), (pa, ~w), (pb, w), (~pb, w), (pb, ~w))):
        np.add.at(per, (inv, i), p & q)
    rng = np.random.default_rng(seed)
    draws = per[rng.integers(0, len(uniq), size=(n_boot, len(uniq)))].sum(axis=1)

    def csi(tp, fn, fp):
        with np.errstate(invalid="ignore", divide="ignore"):
            return tp / (tp + fn + fp)

    total = per.sum(axis=0)
    diff = csi(draws[:, 0], draws[:, 1], draws[:, 2]) - csi(draws[:, 3], draws[:, 4], draws[:, 5])
    return {"difference": float(csi(*total[:3]) - csi(*total[3:])),
            "ci95": (float(np.nanpercentile(diff, 2.5)), float(np.nanpercentile(diff, 97.5)))}


def _git_head() -> str:
    run = subprocess.run(["git", "rev-parse", "HEAD"], check=False, cwd=REPO_ROOT, capture_output=True, text=True)
    return run.stdout.strip() if run.returncode == 0 else "no commit"


def evaluate_frozen_v3(site: Site, pair_name: str, out_dir: Path | None = None, development_check: bool = False,
                       receipt: Path = RECEIPT_V3) -> dict:
    """Score one pair. ``development_check`` uses a spent river, with a caller-chosen folder, and skips the hash gate."""
    allowed = FROZEN_PAIRS.get(site.name, ())
    if development_check:
        if site.name in FROZEN_PAIRS:
            raise ValueError(f"{site.name} is held out: development checks may not read it")
        if out_dir is None:
            raise ValueError("a development check needs its own out_dir")
    elif pair_name not in allowed:
        raise ValueError(f"{site.name}/{pair_name} is not a frozen v3 pair")
    out_dir = Path(out_dir or REPO_ROOT / "outputs" / site.name / pair_name)
    result_path = out_dir / "frozen_v3_metrics.json"
    if result_path.exists():
        raise FileExistsError(f"{result_path} exists; the frozen v3 run happens once")
    integrity = check_receipt_v3(receipt)
    if integrity["changed_since_freeze"] and not development_check:
        raise RuntimeError(f"changed since the freeze, not running: {integrity['changed_since_freeze']}")
    rec = integrity["receipt"]
    cfg = settings_from(rec)

    out_dir.mkdir(parents=True, exist_ok=True)
    attempt = {"started_utc": datetime.now(UTC).isoformat(timespec="seconds"), "git_head": _git_head(),
               "site": site.name, "pair": pair_name, "development_check": development_check}
    with open(out_dir / "frozen_v3_attempts.log", "a") as log:   # written before any imagery is read
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
    nearest = np.argmin(np.abs(t.chainage_m[..., None] - np.asarray(ctx.gauge_chainage_m)), axis=-1)
    timing = classes[nearest]
    crest = peak_envelope_wet(site, grid, dem, ctx.line, ctx.permanent_water,
                              peak_stage_wse(site, pair.dry_time, pair.wet_time))
    ambiguous = t.dry & crest & ~t.wet

    pred, mapped, thr = cfg.rule.apply(feats, lc, timing, hand, t.distance_m)
    v2_pred, v2_thr = cfg.v2.apply(feats, hand, t.distance_m)
    v1_pred = cfg.v1.apply(feats)
    blocks = block_ids(t.chainage_m, cfg.block_m)
    area = grid.pixel_area_ha
    region = ctx.supported & ~ctx.permanent_water
    scored = region & mapped

    def report(p, reg, dry=t.dry):
        return {"scores": score(p, t.wet, dry, reg).to_dict(area),
                "ci95": block_bootstrap(p, t.wet, dry, blocks, reg, n_boot=cfg.n_boot, seed=cfg.seed)}

    wet_region = t.wet & region
    result = {
        "site": site.name, "pair": pair_name, "protocol": "research/V3_YELLOW_PROTOCOL.md",
        "development_check": development_check, "attempt": attempt, "receipt_created_utc": rec["created_utc"],
        "changed_since_freeze": integrity["changed_since_freeze"], "v3_rule": cfg.rule.to_dict(),
        "v3_threshold_db": thr, "v2_threshold_db": v2_thr, "gauge_wse_navd88_m": ctx.gauge_wse_m,
        "gauge_timing_class": {g.name: int(c) for g, c in zip(site.gauges, classes, strict=True)},
        "coverage_of_confirmed_flooding": float((wet_region & mapped).sum() / wet_region.sum()) if wet_region.any() else None,
        "truth_ha": {"wet_primary": float((t.wet & scored).sum() * area), "dry_primary": float((t.dry & scored).sum() * area),
                     "wet_supported": float(wet_region.sum() * area), "ambiguous_left_out": float((ambiguous & scored).sum() * area)},
        "valid_share_of_labelled": float(feats.valid[(t.wet | t.dry) & scored].mean()) if ((t.wet | t.dry) & scored).any() else None,
        "primary_v3_mapped_area": report(pred, scored),
        "secondary_v3_ponding_tolerant": report(pred, scored, t.dry & ~ambiguous),
        "secondary_v3_no_abstention": report(cfg.rule.apply(feats, lc, np.zeros_like(timing), hand, t.distance_m)[0], region),
        "secondary_v3_full_corridor": report(pred, mapped & ~ctx.permanent_water),
        "baseline_v2_same_pixels": report(v2_pred, scored),
        "baseline_v1_same_pixels": report(v1_pred, scored),
        "v3_minus_v2_csi": paired_csi_difference(pred, v2_pred, t.wet, t.dry, blocks, scored, cfg.n_boot, cfg.seed),
        "v3_minus_v1_csi": paired_csi_difference(pred, v1_pred, t.wet, t.dry, blocks, scored, cfg.n_boot, cfg.seed),
        "by_landcover": {name: report(pred, scored & (lc == code)) for code, name in
                         ((1, "tree cover"), (2, "herbaceous wetland"), (0, "other"), (3, "crop/grass/shrub"))
                         if (t.wet & scored & (lc == code)).any()},
        "provenance": {"wet": identification(site.gcov_path(pair.wet)), "dry": identification(site.gcov_path(pair.dry))},
    }
    result_path.write_text(json.dumps(result, indent=2, default=str))
    np.savez_compressed(out_dir / "frozen_v3_layers.npz", pred=pred, mapped=mapped, v2_pred=v2_pred, v1_pred=v1_pred,
                        wet=t.wet, dry=t.dry, region=region, ambiguous=ambiguous, landcover=lc, timing=timing,
                        chainage=t.chainage_m, hand=hand.astype(np.float32))
    return result
