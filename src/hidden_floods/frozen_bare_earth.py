"""One-time test: does a global elevation model with trees removed (FABDEM) recover what losing lidar cost? (research/BARE_EARTH_PROTOCOL.md)

No radar is read. Each pass reuses the saved layers of its one-time v4 run, and the hashed v4 rule is applied again with height above the river
from FABDEM in place of lidar. The gauge-and-lidar estimate stays the reference, so it is independent of FABDEM. The Copernicus and lidar maps
are recomputed from their hashed inputs and must reproduce the recorded no-lidar results.

FABDEM is licensed CC BY-NC-SA 4.0. No tile or layer derived from it is written anywhere in the repository: only scores and summary numbers.
FABDEM is produced using Copernicus WorldDEM-30 (c) DLR e.V. 2010-2014 and (c) Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS
by the European Union and ESA; all rights reserved.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from hidden_floods.audit import truth_context
from hidden_floods.config import REPO_ROOT, Site, data_root, load_site
from hidden_floods.frozen_no_lidar import LAND, LIMIT_M, PASSES, SENSITIVITY_M, _git_head, digest, global_dem
from hidden_floods.frozen_no_lidar import RECEIPT as RECEIPT_NO_LIDAR
from hidden_floods.frozen_no_lidar import RESULTS as RESULTS_NO_LIDAR
from hidden_floods.frozen_no_lidar import check_receipt as check_no_lidar_receipt
from hidden_floods.frozen_no_lidar import check_tiles as check_copernicus_tiles
from hidden_floods.frozen_overbank import RECEIPT as RECEIPT_OVERBANK
from hidden_floods.frozen_overbank import check_receipt as check_overbank_receipt
from hidden_floods.frozen_v3 import RECEIPT_V3, paired_csi_difference, settings_from
from hidden_floods.frozen_v4 import RECEIPT as RECEIPT_V4
from hidden_floods.frozen_v4 import check_receipt as check_v4_receipt
from hidden_floods.frozen_v4 import rule_from
from hidden_floods.grid import warp_to_grid
from hidden_floods.metrics import block_bootstrap, block_ids, score
from hidden_floods.selfcal import height_above_river

RECEIPT = REPO_ROOT / "research" / "freeze_receipt_bare_earth.json"
RESULTS = REPO_ROOT / "research" / "bare_earth_results.json"
TILES = REPO_ROOT / "research" / "bare_earth_tiles.json"
ATTEMPTS = REPO_ROOT / "outputs" / "bare_earth_attempts.log"
SELF = ("research/BARE_EARTH_PROTOCOL.md", "research/bare_earth_tiles.json", "scripts/run_frozen_bare_earth.py", "src/hidden_floods/frozen_bare_earth.py",
        "research/freeze_receipt_v4.json", "research/freeze_receipt_overbank.json", "research/freeze_receipt_no_lidar.json")
DEM_DIR = data_root() / "fabdem"
PIXEL_HA = 0.25                    # the 50 m analysis grid
RECORD_TOL = 0.001                 # the recomputed Copernicus and lidar maps must match the recorded CSI this closely
HERO = ("satilla", "047A_oct15")   # the pass for prediction P1
P1_MAX_M = 2.0                     # P1: flooded ground's median height above the river by FABDEM is under this
P2_MIN_PASSES = 5                  # P2: FABDEM beats Copernicus against lidar on at least this many passes
GUARD_AREA_RATIO = 1.5             # Q1 guard: total mapped area against NISAR with lidar's
GUARD_SHARE_RATIO = 0.5            # Q1 guard: mean labelled share against NISAR with lidar's


def check_receipt(path: Path = RECEIPT) -> list[str]:
    rec = json.loads(Path(path).read_text())
    return [r for r in SELF if rec["sha256"].get(r) != digest(r)]


def check_tiles(rivers) -> list[str]:
    """Names of listed FABDEM tiles whose bytes differ from what was recorded before the freeze."""
    listed = json.loads(TILES.read_text())["tiles"]
    return [name for river in rivers for name, rec in listed[river].items()
            if hashlib.sha256((DEM_DIR / name).read_bytes()).hexdigest() != rec["sha256"]]


def fabdem(river: str, grid) -> np.ndarray:
    """FABDEM bare-earth heights averaged onto ``grid``, the same way Copernicus was."""
    out = np.full(grid.shape, np.nan, np.float32)
    for name in json.loads(TILES.read_text())["tiles"][river]:
        w = warp_to_grid(DEM_DIR / name, grid, categorical=False, nodata=np.nan, dtype=np.float32)
        out = np.where(np.isfinite(out), out, w)
    return out


def map_checks(pred, wet, dry, scored, depth, max_dry_height_m) -> dict:
    """Mapped area, the share of it the estimate labels, and area on ground well above the water (very likely wrong)."""
    mapped = pred & scored
    n = int(mapped.sum())
    return {"mapped_ha": n * PIXEL_HA, "labelled_share": float((mapped & (wet | dry)).sum() / max(n, 1)),
            "ha_more_than_5m_above_water": float((mapped & (depth <= -max_dry_height_m)).sum() * PIXEL_HA)}


def wet_heights(hand, hand_lidar, wet_scored) -> dict:
    """Where a model puts ground the estimate calls flooded: its median height above the river, and its median error against lidar."""
    ok = wet_scored & np.isfinite(hand) & np.isfinite(hand_lidar)
    if not ok.any():
        return {"median_m": None, "median_error_vs_lidar_m": None}
    return {"median_m": float(np.median(hand[ok])), "median_error_vs_lidar_m": float(np.median(hand[ok] - hand_lidar[ok]))}


def score_pass(site: Site, pair_name: str, folder: Path) -> dict:
    """All six maps for one pass, on the pixels its frozen v4 run scored."""
    z = np.load(folder / "frozen_v4_layers.npz")
    t = truth_context(site, site.pairs[pair_name].wet_time)
    truth = t.truth
    cfg = settings_from(json.loads(RECEIPT_V3.read_text()))
    rule = rule_from(json.loads(RECEIPT_V4.read_text()))
    wet, dry, lc, timing, hand_lidar, d_hh, d_hv, depth = z["wet"], z["dry"], z["landcover"], z["timing"], z["hand"], z["d_hh"], z["d_hv"], z["depth"]
    scored = z["region"] & z["mapped"]
    blocks = block_ids(truth.chainage_m, cfg.block_m)
    hand_cop = height_above_river(global_dem(site.name, t.grid), truth.distance_m, truth.chainage_m)
    hand_fab = height_above_river(fabdem(site.name, t.grid), truth.distance_m, truth.chainage_m)
    with_fab = rule.apply(d_hh, d_hv, lc, timing, hand_fab, truth.distance_m)
    replay = rule.apply(d_hh, d_hv, lc, timing, hand_lidar, truth.distance_m)   # the frozen run, redone: must agree with its saved map
    land = np.isin(lc, LAND)
    maps = {"nisar_with_fabdem": with_fab["pred"], "fabdem_height_map": land & (hand_fab < LIMIT_M),
            "nisar_with_copernicus": rule.apply(d_hh, d_hv, lc, timing, hand_cop, truth.distance_m)["pred"], "copernicus_height_map": land & (hand_cop < LIMIT_M),
            "nisar_with_lidar": z["pred"], "lidar_height_map": land & (hand_lidar < LIMIT_M)}

    def report(p):
        s = score(p, wet, dry, scored)
        return {"csi": float(s.csi), "recall": float(s.recall), "precision": float(s.precision),
                "ci95": block_bootstrap(p, wet, dry, blocks, scored, n_boot=cfg.n_boot, seed=cfg.seed)["csi"],
                **map_checks(p, wet, dry, scored, depth, site.max_dry_height_m)}

    diff = lambda a, b: paired_csi_difference(maps[a], maps[b], wet, dry, blocks, scored, cfg.n_boot, cfg.seed)
    limits = {str(m): float(score(land & (hand_fab < m), wet, dry, scored).csi) for m in SENSITIVITY_M}
    best = max(limits, key=limits.get)
    ws = wet & scored
    return {
        "site": site.name, "pair": pair_name, "estimated_ha": float(ws.sum() * PIXEL_HA), "maps": {k: report(v) for k, v in maps.items()},
        "q1_fabdem_minus_copernicus": diff("nisar_with_fabdem", "nisar_with_copernicus"),
        "q2_nisar_minus_fabdem_map": diff("nisar_with_fabdem", "fabdem_height_map"),
        "q3_fabdem_minus_lidar": diff("nisar_with_fabdem", "nisar_with_lidar"),
        "replay_agreement": float((replay["pred"] == z["pred"])[scored].mean()),
        "fabdem_map_by_limit": limits, "best_limit_m": float(best), "best_limit_csi": limits[best],
        "wet_ground": {"lidar": wet_heights(hand_lidar, hand_lidar, ws), "copernicus": wet_heights(hand_cop, hand_lidar, ws), "fabdem": wet_heights(hand_fab, hand_lidar, ws)},
        "threshold_db": with_fab["threshold_db"], "used_hh_minus_hv": with_fab["used_hh_minus_hv"],
    }


def check_record(rows: list[dict]) -> list[str]:
    """Maps recomputed here that don't match the recorded no-lidar results (the run stops if any don't)."""
    rec = {(p["site"], p["pair"]): p["maps"] for p in json.loads(RESULTS_NO_LIDAR.read_text())["passes"]}
    pairs = (("nisar_with_copernicus", "nisar_without_lidar"), ("copernicus_height_map", "global_height_map"), ("nisar_with_lidar", "nisar_with_lidar"), ("lidar_height_map", "lidar_height_map"))
    return [f"{r['site']} {r['pair']} {mine}" for r in rows for mine, theirs in pairs
            if abs(r["maps"][mine]["csi"] - rec[(r["site"], r["pair"])][theirs]["csi"]) > RECORD_TOL]


def _wins(rows, key) -> tuple[int, int]:
    ci = [r[key]["ci95"] for r in rows]
    return sum(lo > 0 for lo, _ in ci), sum(hi < 0 for _, hi in ci)


def read_q1(rows: list[dict]) -> dict:
    """Question 1 by the fixed table, then the guard (§5)."""
    gain = float(np.mean([r["maps"]["nisar_with_fabdem"]["csi"] - r["maps"]["nisar_with_copernicus"]["csi"] for r in rows]))
    won, lost = _wins(rows, "q1_fabdem_minus_copernicus")
    level = 2 if gain >= 0.05 and won >= 3 and lost == 0 else 1 if gain > 0 and won >= 1 else 0
    area = sum(r["maps"]["nisar_with_fabdem"]["mapped_ha"] for r in rows) / max(sum(r["maps"]["nisar_with_lidar"]["mapped_ha"] for r in rows), 1e-9)
    share = float(np.mean([r["maps"]["nisar_with_fabdem"]["labelled_share"] for r in rows])) / max(float(np.mean([r["maps"]["nisar_with_lidar"]["labelled_share"] for r in rows])), 1e-9)
    guarded = area > GUARD_AREA_RATIO or share < GUARD_SHARE_RATIO
    final = max(0, level - 1) if guarded else level
    return {"mean_gain": gain, "passes_won": won, "passes_lost": lost, "area_ratio_vs_lidar": area, "labelled_share_ratio_vs_lidar": share,
            "guard_triggered": guarded, "reading": ("Not supported", "Partly supported", "Supported")[final]}


def read_q2(rows: list[dict]) -> dict:
    gain = float(np.mean([r["maps"]["nisar_with_fabdem"]["csi"] - r["maps"]["fabdem_height_map"]["csi"] for r in rows]))
    won, lost = _wins(rows, "q2_nisar_minus_fabdem_map")
    level = 2 if gain > 0 and won >= 3 and lost == 0 else 1 if gain > 0 and won >= 1 else 0
    at_best = float(np.mean([r["maps"]["nisar_with_fabdem"]["csi"] - r["best_limit_csi"] for r in rows]))
    return {"mean_gain": gain, "passes_won": won, "passes_lost": lost, "mean_gain_vs_best_limit": at_best, "reading": ("Not supported", "Partly supported", "Supported")[level]}


def read_q3(rows: list[dict]) -> dict:
    gap = float(np.mean([r["maps"]["nisar_with_lidar"]["csi"] - r["maps"]["nisar_with_fabdem"]["csi"] for r in rows]))
    return {"mean_gap": gap, "reading": "Small" if gap <= 0.05 else "Moderate" if gap <= 0.15 else "Large"}


def read_mechanism(rows: list[dict]) -> dict:
    hero = next(r for r in rows if (r["site"], r["pair"]) == HERO)["wet_ground"]["fabdem"]["median_m"]
    closer = sum(abs(r["wet_ground"]["fabdem"]["median_error_vs_lidar_m"]) < abs(r["wet_ground"]["copernicus"]["median_error_vs_lidar_m"]) for r in rows
                 if r["wet_ground"]["fabdem"]["median_error_vs_lidar_m"] is not None and r["wet_ground"]["copernicus"]["median_error_vs_lidar_m"] is not None)
    return {"p1_hero_median_m": hero, "p1_holds": hero is not None and hero < P1_MAX_M, "p2_passes_closer": closer, "p2_holds": closer >= P2_MIN_PASSES}


def run() -> dict:
    """Runs every listed pass once. Refuses if any hashed file or tile has changed, if the results exist, or if the record doesn't reproduce."""
    if RESULTS.exists():
        raise FileExistsError(f"{RESULTS} exists; this test runs once")
    rivers = {r for r, _ in PASSES}
    changed = check_receipt() + check_v4_receipt() + check_overbank_receipt() + check_no_lidar_receipt() + check_copernicus_tiles(rivers) + check_tiles(rivers)
    if changed:
        raise RuntimeError(f"changed since the freeze, not running: {changed}")
    ATTEMPTS.parent.mkdir(parents=True, exist_ok=True)
    with open(ATTEMPTS, "a") as log:      # written before any FABDEM data over the test rivers is read
        log.write(json.dumps({"started_utc": datetime.now(UTC).isoformat(timespec="seconds"), "git_head": _git_head()}) + "\n")
    rows = []
    for river, pair in PASSES:
        rows.append(score_pass(load_site(river), pair, REPO_ROOT / "outputs" / river / pair))
        print(json.dumps({"site": river, "pair": pair} | {m: round(v["csi"], 3) for m, v in rows[-1]["maps"].items()}), flush=True)
    bad = check_record(rows)
    if bad:
        raise RuntimeError(f"recorded maps didn't reproduce, results not written: {bad}")
    result = {"protocol": "research/BARE_EARTH_PROTOCOL.md", "git_head": _git_head(), "receipts": [RECEIPT_V4.name, RECEIPT_OVERBANK.name, RECEIPT_NO_LIDAR.name],
              "fabdem": json.loads(TILES.read_text())["source"], "passes": rows,
              "readings": {"q1": read_q1(rows), "q2": read_q2(rows), "q3": read_q3(rows), "mechanism": read_mechanism(rows)}}
    RESULTS.write_text(json.dumps(result, indent=1, default=float))
    return result
