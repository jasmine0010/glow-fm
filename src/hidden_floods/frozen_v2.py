"""Frozen evaluation of method v2 on the third (held-out) event — research/THIRD_EVENT_PROTOCOL.md.

Settings come from ``research/freeze_receipt_v2.json``; the scientific modules must be byte-identical to the freeze.
Writes ``frozen_v2_metrics.json`` once and refuses to overwrite it.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from hidden_floods.config import REPO_ROOT, Site
from hidden_floods.detect import ChangeRule, pair_features
from hidden_floods.frozen import reference_water
from hidden_floods.io.dem import dem_on_grid
from hidden_floods.io.nisar import identification, read_gcov
from hidden_floods.metrics import block_bootstrap, block_ids, score
from hidden_floods.pipeline import analysis_grid, gauge_water_surfaces
from hidden_floods.selfcal import SelfCalRule, gauge_supported, height_above_river
from hidden_floods.truth import ValleyLine, hydraulic_truth, refine_centerline

RECEIPT_V2 = REPO_ROOT / "research" / "freeze_receipt_v2.json"
HASHED_V2 = ("src/hidden_floods/selfcal.py", "src/hidden_floods/detect.py", "src/hidden_floods/truth.py",
             "src/hidden_floods/metrics.py", "src/hidden_floods/grid.py", "src/hidden_floods/io/nisar.py",
             "src/hidden_floods/io/gauges.py", "src/hidden_floods/io/dem.py", "src/hidden_floods/frozen.py",
             "src/hidden_floods/pipeline.py", "src/hidden_floods/frozen_v2.py")


def _digest(rel: str) -> str:
    return hashlib.sha256((REPO_ROOT / rel).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def check_receipt_v2() -> dict:
    rec = json.loads(RECEIPT_V2.read_text())
    changed = [rel for rel in HASHED_V2 if rec["sha256"].get(rel) != _digest(rel)]
    return {"receipt": rec, "changed_since_freeze": changed}


def evaluate_frozen_v2(site: Site, pair_name: str, out_dir: Path | None = None) -> dict:
    out_dir = Path(out_dir or REPO_ROOT / "outputs" / site.name / pair_name)
    result_path = out_dir / "frozen_v2_metrics.json"
    if result_path.exists():
        raise FileExistsError(f"{result_path} exists; the frozen v2 run happens once")
    out_dir.mkdir(parents=True, exist_ok=True)

    integrity = check_receipt_v2()
    rec = integrity["receipt"]
    rule = SelfCalRule(**{k: v for k, v in rec["v2_rule"].items() if k != "type"})
    tset, mset = rec["truth"], rec["metrics"]

    grid = analysis_grid(site)
    pair = site.pairs[pair_name]
    feats = pair_features(read_gcov(site.gcov_path(pair.dry), grid), read_gcov(site.gcov_path(pair.wet), grid))
    dem = dem_on_grid(site.dem_path, grid)
    channel = reference_water(site.operational_dir, grid)
    coarse = ValleyLine.from_lonlat(grid, site.valley_line)
    dist0, _ = coarse.project(*grid.meshgrid())
    line = refine_centerline(coarse, channel & (dist0 < tset["corridor_m"]), grid)
    dist, chain = line.project(*grid.meshgrid())
    gxy = [grid.to_xy(g.lon, g.lat) for g in site.gauges]
    _, g_chain = line.project(*map(np.array, zip(*gxy, strict=True)))
    wse = gauge_water_surfaces(site, pair.wet_time)
    truth = hydraulic_truth(grid, dem, line, gxy, [wse[g.name] for g in site.gauges], tset["corridor_m"],
                            tset["margin_m"], tset["max_dry_height_m"],
                            channel_seeds=channel if tset["connectivity"] else None)
    supported = gauge_supported(chain, g_chain, tset["gauge_support_m"])

    hand = height_above_river(dem, dist, chain)
    pred, thr = rule.apply(feats, hand, dist)
    v1_pred = ChangeRule(rec["v1_rule"]["d_hh_db"], rec["v1_rule"]["forest_hv_db"]).apply(feats)
    blocks = block_ids(chain, mset["bootstrap_block_m"])
    area = grid.pixel_area_ha

    def report(p, region):
        s = score(p, truth.wet, truth.dry, region)
        ci = block_bootstrap(p, truth.wet, truth.dry, blocks, region, n_boot=mset["n_boot"], seed=mset["seed"])
        return {"scores": s.to_dict(area), "ci95": ci}

    result = {
        "site": site.name, "pair": pair_name, "protocol": "research/THIRD_EVENT_PROTOCOL.md",
        "receipt_created_utc": rec["created_utc"], "modules_changed_since_freeze": integrity["changed_since_freeze"],
        "v2_rule": rule.to_dict(), "v2_threshold_db": thr, "truth_settings": tset,
        "gauge_wse_navd88_m": wse,
        "truth_ha": {"wet_supported": float((truth.wet & supported).sum() * area),
                     "dry_supported": float((truth.dry & supported).sum() * area),
                     "wet_all": float(truth.wet.sum() * area), "dry_all": float(truth.dry.sum() * area)},
        "primary_v2_gauge_supported": report(pred, supported),
        "secondary_v2_full_corridor": report(pred, None),
        "baseline_v1_gauge_supported": report(v1_pred, supported),
        "provenance": {"wet": identification(site.gcov_path(pair.wet)), "dry": identification(site.gcov_path(pair.dry))},
    }
    result_path.write_text(json.dumps(result, indent=2, default=str))
    np.savez_compressed(out_dir / "frozen_v2_layers.npz", pred=pred, v1_pred=v1_pred, wet=truth.wet, dry=truth.dry,
                        supported=supported, chainage=chain, hand=hand.astype(np.float32))
    return result
