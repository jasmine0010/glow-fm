"""One-time test: without lidar, does NISAR beat a height map from a global elevation model? (research/NO_LIDAR_PROTOCOL.md)

No radar is read. Each pass reuses the saved layers of its one-time v4 run, and the hashed v4 rule is applied again with height above the river
from Copernicus GLO-30 in place of lidar. The gauge-and-lidar estimate stays the reference, so it is independent of the global elevation model.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from hidden_floods.audit import truth_context
from hidden_floods.config import REPO_ROOT, Site, data_root, load_site
from hidden_floods.frozen_overbank import RECEIPT as RECEIPT_OVERBANK
from hidden_floods.frozen_overbank import check_receipt as check_overbank_receipt
from hidden_floods.frozen_v3 import RECEIPT_V3, paired_csi_difference, settings_from
from hidden_floods.frozen_v4 import RECEIPT as RECEIPT_V4
from hidden_floods.frozen_v4 import check_receipt as check_v4_receipt
from hidden_floods.frozen_v4 import rule_from
from hidden_floods.grid import warp_to_grid
from hidden_floods.metrics import block_bootstrap, block_ids, score
from hidden_floods.selfcal import height_above_river

RECEIPT = REPO_ROOT / "research" / "freeze_receipt_no_lidar.json"
RESULTS = REPO_ROOT / "research" / "no_lidar_results.json"
TILES = REPO_ROOT / "research" / "global_dem_tiles.json"
ATTEMPTS = REPO_ROOT / "outputs" / "no_lidar_attempts.log"
SELF = ("research/NO_LIDAR_PROTOCOL.md", "research/global_dem_tiles.json", "scripts/run_frozen_no_lidar.py", "src/hidden_floods/frozen_no_lidar.py", "research/freeze_receipt_v4.json", "research/freeze_receipt_overbank.json")
PASSES = (("satilla", "047A_oct15"), ("satilla", "098D_oct19"), ("ochlockonee", "026D_oct14"), ("st_marys", "098D_oct07"), ("pee_dee", "098D_jul27"), ("neuse", "090A_jul26"), ("lower_sabine", "134A_jul17"))
LAND, LIMIT_M = (0, 1, 2), 2.0
SENSITIVITY_M = (1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0)
DEM_DIR = data_root() / "global_dem"


def digest(rel: str) -> str:
    return hashlib.sha256((REPO_ROOT / rel).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def check_receipt(path: Path = RECEIPT) -> list[str]:
    rec = json.loads(Path(path).read_text())
    return [r for r in SELF if rec["sha256"].get(r) != digest(r)]


def check_tiles(rivers) -> list[str]:
    """Names of listed elevation tiles whose bytes differ from what was recorded before the freeze."""
    listed = json.loads(TILES.read_text())
    bad = []
    for river in rivers:
        for name, sha in listed[river].items():
            if hashlib.sha256((DEM_DIR / f"{name}.tif").read_bytes()).hexdigest() != sha:
                bad.append(name)
    return bad


def global_dem(river: str, grid) -> np.ndarray:
    """Copernicus GLO-30 surface heights averaged onto ``grid``. This is a surface model, so it includes tree height."""
    out = np.full(grid.shape, np.nan, np.float32)
    for name in json.loads(TILES.read_text())[river]:
        w = warp_to_grid(DEM_DIR / f"{name}.tif", grid, categorical=False, nodata=np.nan, dtype=np.float32)
        out = np.where(np.isfinite(out), out, w)
    return out


def _git_head() -> str:
    run = subprocess.run(["git", "rev-parse", "HEAD"], check=False, cwd=REPO_ROOT, capture_output=True, text=True)
    return run.stdout.strip() if run.returncode == 0 else "no commit"


def score_pass(site: Site, pair_name: str, folder: Path) -> dict:
    """All the maps for one pass, on the pixels its frozen v4 run scored."""
    z = np.load(folder / "frozen_v4_layers.npz")
    t = truth_context(site, site.pairs[pair_name].wet_time)
    truth = t.truth
    cfg = settings_from(json.loads(RECEIPT_V3.read_text()))
    rule = rule_from(json.loads(RECEIPT_V4.read_text()))
    wet, dry, lc, timing, hand_lidar, d_hh, d_hv = z["wet"], z["dry"], z["landcover"], z["timing"], z["hand"], z["d_hh"], z["d_hv"]
    scored = z["region"] & z["mapped"]
    blocks = block_ids(truth.chainage_m, cfg.block_m)
    hand_global = height_above_river(global_dem(site.name, t.grid), truth.distance_m, truth.chainage_m)
    replay = rule.apply(d_hh, d_hv, lc, timing, hand_lidar, truth.distance_m)
    no_lidar = rule.apply(d_hh, d_hv, lc, timing, hand_global, truth.distance_m)
    land = np.isin(lc, LAND)
    maps = {"nisar_without_lidar": no_lidar["pred"], "global_height_map": land & (hand_global < LIMIT_M), "nisar_with_lidar": z["pred"], "lidar_height_map": land & (hand_lidar < LIMIT_M)}

    def report(p):
        s = score(p, wet, dry, scored)
        return {"csi": float(s.csi), "recall": float(s.recall), "precision": float(s.precision), "ci95": block_bootstrap(p, wet, dry, blocks, scored, n_boot=cfg.n_boot, seed=cfg.seed)["csi"]}

    diff = lambda a, b: paired_csi_difference(maps[a], maps[b], wet, dry, blocks, scored, cfg.n_boot, cfg.seed)
    limits = {str(m): float(score(land & (hand_global < m), wet, dry, scored).csi) for m in SENSITIVITY_M}
    best = max(limits, key=limits.get)
    return {
        "site": site.name, "pair": pair_name, "estimated_ha": float((wet & scored).sum() * 0.25), "maps": {k: report(v) for k, v in maps.items()},
        "nisar_minus_global_map": diff("nisar_without_lidar", "global_height_map"), "nisar_without_minus_with_lidar": diff("nisar_without_lidar", "nisar_with_lidar"), "global_minus_lidar_map": diff("global_height_map", "lidar_height_map"),
        "replay_agreement": float((replay["pred"] == z["pred"])[scored].mean()), "global_map_by_limit": limits, "best_limit_m": float(best), "best_limit_csi": limits[best],
        "threshold_db": no_lidar["threshold_db"], "used_hh_minus_hv": no_lidar["used_hh_minus_hv"],
    }


def run() -> dict:
    """Runs every listed pass once. Refuses if any hashed file or tile has changed, or if the results already exist."""
    if RESULTS.exists():
        raise FileExistsError(f"{RESULTS} exists; this test runs once")
    changed = check_receipt() + check_v4_receipt() + check_overbank_receipt() + check_tiles({r for r, _ in PASSES})
    if changed:
        raise RuntimeError(f"changed since the freeze, not running: {changed}")
    ATTEMPTS.parent.mkdir(parents=True, exist_ok=True)
    with open(ATTEMPTS, "a") as log:      # written before any elevation data over the test rivers is read
        log.write(json.dumps({"started_utc": datetime.now(UTC).isoformat(timespec="seconds"), "git_head": _git_head()}) + "\n")
    rows = []
    for river, pair in PASSES:
        rows.append(score_pass(load_site(river), pair, REPO_ROOT / "outputs" / river / pair))
        print(json.dumps({k: rows[-1][k] for k in ("site", "pair", "nisar_minus_global_map", "best_limit_csi", "replay_agreement")} | {m: round(v["csi"], 3) for m, v in rows[-1]["maps"].items()}), flush=True)
    result = {"protocol": "research/NO_LIDAR_PROTOCOL.md", "git_head": _git_head(), "receipts": [str(RECEIPT_V4.name), str(RECEIPT_OVERBANK.name)], "passes": rows}
    RESULTS.write_text(json.dumps(result, indent=1, default=float))
    return result
