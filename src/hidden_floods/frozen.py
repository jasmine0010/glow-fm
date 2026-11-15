"""Frozen evaluation on a held-out event (research/SECOND_EVENT_PROTOCOL.md).

Nothing is tuned here: the rule and truth settings come from ``research/freeze_receipt.json``, and the detector,
truth and metric functions are the hashed ones. Results are written once to ``frozen_metrics.json``; the function
refuses to overwrite an existing result.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from hidden_floods.config import REPO_ROOT, Site
from hidden_floods.detect import ChangeRule, pair_features
from hidden_floods.grid import Grid, warp_to_grid
from hidden_floods.io.dem import dem_on_grid
from hidden_floods.io.nisar import identification, read_gcov
from hidden_floods.metrics import block_bootstrap, block_ids, score
from hidden_floods.pipeline import analysis_grid, gauge_water_surfaces
from hidden_floods.truth import ValleyLine, hydraulic_truth, refine_centerline

RECEIPT = REPO_ROOT / "research" / "freeze_receipt.json"
HASHED_MODULES = ("src/hidden_floods/detect.py", "src/hidden_floods/truth.py", "src/hidden_floods/metrics.py",
                  "src/hidden_floods/grid.py", "src/hidden_floods/io/nisar.py", "src/hidden_floods/io/gauges.py",
                  "src/hidden_floods/io/dem.py")


def check_receipt() -> dict:
    """Load the freeze receipt and confirm the scientific modules are byte-identical (LF-normalised) to the freeze."""
    rec = json.loads(RECEIPT.read_text())
    frozen_hashes = {k.replace("\\", "/"): v for k, v in rec["sha256"].items()}  # receipt was written on Windows
    changed = []
    for rel in HASHED_MODULES:
        digest = hashlib.sha256((REPO_ROOT / rel).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        if frozen_hashes.get(rel) != digest:
            changed.append(rel)
    return {"receipt": rec, "changed_since_freeze": changed}


def reference_water(ops_dir: Path, grid: Grid) -> np.ndarray:
    """Union of all GFM reference-water masks in ``ops_dir`` (a static layer) on ``grid``."""
    out = np.zeros(grid.shape, bool)
    for path in sorted(Path(ops_dir).glob("GFM_*_reference_water_mask.tif")):
        rw = warp_to_grid(path, grid, categorical=True, nodata=255)
        out |= (rw == 1) | (rw == 2)
    return out


def evaluate_frozen(site: Site, pair_name: str, out_dir: Path | None = None) -> dict:
    out_dir = Path(out_dir or REPO_ROOT / "outputs" / site.name / pair_name)
    result_path = out_dir / "frozen_metrics.json"
    if result_path.exists():
        raise FileExistsError(f"{result_path} exists; the frozen run happens once (see protocol section 3)")
    out_dir.mkdir(parents=True, exist_ok=True)

    integrity = check_receipt()
    rec = integrity["receipt"]
    rule = ChangeRule(rec["frozen_rule"]["d_hh_db"], rec["frozen_rule"]["forest_hv_db"])
    tset, mset = rec["truth"], rec["metrics"]

    grid = analysis_grid(site)
    pair = site.pairs[pair_name]
    feats = pair_features(read_gcov(site.gcov_path(pair.dry), grid), read_gcov(site.gcov_path(pair.wet), grid))
    dem = dem_on_grid(site.dem_path, grid)
    channel = reference_water(site.operational_dir, grid)
    coarse = ValleyLine.from_lonlat(grid, site.valley_line)
    dist, _ = coarse.project(*grid.meshgrid())
    line = refine_centerline(coarse, channel & (dist < tset["corridor_m"]), grid)
    wse = gauge_water_surfaces(site, pair.wet_time)
    truth = hydraulic_truth(grid, dem, line, [grid.to_xy(g.lon, g.lat) for g in site.gauges],
                            [wse[g.name] for g in site.gauges], tset["corridor_m"], tset["margin_m"],
                            tset["max_dry_height_m"], channel_seeds=channel if tset["connectivity"] else None)

    pred = rule.apply(feats)
    s = score(pred, truth.wet, truth.dry)
    ci = block_bootstrap(pred, truth.wet, truth.dry, block_ids(truth.chainage_m, mset["bootstrap_block_m"]),
                         n_boot=mset["n_boot"], seed=mset["seed"])
    area = grid.pixel_area_ha
    result = {
        "site": site.name, "pair": pair_name, "protocol": "research/SECOND_EVENT_PROTOCOL.md",
        "receipt_created_utc": rec["created_utc"], "modules_changed_since_freeze": integrity["changed_since_freeze"],
        "rule": rule.to_dict(), "truth_settings": tset,
        "gauge_wse_navd88_m": wse,
        "truth_ha": {"wet": float(truth.wet.sum() * area), "dry": float(truth.dry.sum() * area)},
        "scores": s.to_dict(area), "ci95": ci,
        "flagged_ha_in_corridor": float((pred & truth.corridor).sum() * area),
        "valid_fraction_in_corridor": float(feats.valid[truth.corridor].mean()) if truth.corridor.any() else 0.0,
        "provenance": {"wet": identification(site.gcov_path(pair.wet)), "dry": identification(site.gcov_path(pair.dry))},
    }
    result_path.write_text(json.dumps(result, indent=2, default=str))
    np.savez_compressed(out_dir / "frozen_layers.npz", pred=pred, wet=truth.wet, dry=truth.dry,
                        chainage=truth.chainage_m, d_hh=feats.d_hh.astype(np.float32), corridor=truth.corridor,
                        line_x=line.x, line_y=line.y)
    return result
