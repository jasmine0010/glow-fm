"""One-time test of unchanged method v4, and of a trust signal fixed in advance, on unread rivers (research/OVERBANK_PROTOCOL.md).

Mapping and scoring come from the hashed ``frozen_v4.evaluate_v4``. Its ``regression_check`` flag only means it skips the v4 river
list and receipt, because this module runs its own hash gate, attempt log and write-once check.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from hidden_floods.audit import truth_context
from hidden_floods.config import REPO_ROOT, Site
from hidden_floods.frozen_v3 import RECEIPT_V3, paired_csi_difference, settings_from
from hidden_floods.frozen_v4 import HASHED as V4_HASHED
from hidden_floods.frozen_v4 import RECEIPT as V4_RECEIPT
from hidden_floods.frozen_v4 import check_receipt as check_v4_receipt
from hidden_floods.frozen_v4 import evaluate_v4, rule_from
from hidden_floods.metrics import block_bootstrap, block_ids, score
from hidden_floods.stack import Scene

RECEIPT = REPO_ROOT / "research" / "freeze_receipt_overbank.json"
SCENES = REPO_ROOT / "research" / "overbank_scenes.json"
RAIN = REPO_ROOT / "research" / "overbank_rain.json"
LIDAR_LIMIT_M, LIDAR_LANDCOVER, NEAR_GAUGE_M = 2.0, (0, 1, 2), 5000.0
SELF = ("research/OVERBANK_PROTOCOL.md", "research/overbank_scenes.json", "research/overbank_rain.json", "research/freeze_receipt_v4.json",
        "scripts/run_frozen_overbank.py", "src/hidden_floods/frozen_overbank.py")


def trust_signal(confident: bool, rainy: bool) -> str:
    """Green means trust the map: the confidence label is High and it hasn't rained recently. Anything else is red."""
    return "green" if confident and not rainy else "red"


def digest(rel: str) -> str:
    return hashlib.sha256((REPO_ROOT / rel).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def hashed_files() -> list[str]:
    sites = [f"sites/{river}.toml" for river in json.loads(SCENES.read_text())]
    return [*SELF, *sites, *[f for f in V4_HASHED if f not in SELF]]


def check_receipt(path: Path = RECEIPT) -> list[str]:
    rec = json.loads(Path(path).read_text())
    return [r for r in hashed_files() if rec["sha256"].get(r) != digest(r)]


def _git_head() -> str:
    run = subprocess.run(["git", "rev-parse", "HEAD"], check=False, cwd=REPO_ROOT, capture_output=True, text=True)
    return run.stdout.strip() if run.returncode == 0 else "no commit"


def evaluate(site: Site, pair_name: str) -> dict:
    """Run one listed pass once. Refuses if any hashed file has changed or the pass has already been scored."""
    listing, rain = json.loads(SCENES.read_text()), json.loads(RAIN.read_text())
    if pair_name not in listing.get(site.name, {}).get("passes", {}):
        raise ValueError(f"{site.name}/{pair_name} is not a listed overbank pass")
    out_dir = REPO_ROOT / "outputs" / site.name / pair_name
    result_path = out_dir / "frozen_overbank_metrics.json"
    if result_path.exists():
        raise FileExistsError(f"{result_path} exists; each overbank pass runs once")
    changed = check_receipt() + check_v4_receipt()
    if changed:
        raise RuntimeError(f"changed since the freeze, not running: {changed}")
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "frozen_overbank_attempts.log", "a") as log:      # written before any imagery is read
        log.write(json.dumps({"started_utc": datetime.now(UTC).isoformat(timespec="seconds"), "git_head": _git_head(), "site": site.name, "pair": pair_name}) + "\n")

    scenes = [Scene(**s) for s in listing[site.name]["passes"][pair_name]["scenes"]]
    result = score_pass(site, pair_name, scenes, rain[site.name][pair_name], out_dir)
    result_path.write_text(json.dumps(result, indent=2, default=str))
    return result


def score_pass(site: Site, pair_name: str, scenes: list[Scene], day_rain: dict, out_dir: Path) -> dict:
    """Map and score one pass with the hashed v4 code, then add the lidar comparison, the near-gauge check and the trust signal."""
    v4 = evaluate_v4(site, pair_name, scenes, rule_from(json.loads(V4_RECEIPT.read_text())), out_dir=out_dir, regression_check=True)

    cfg = settings_from(json.loads(RECEIPT_V3.read_text()))
    z = np.load(out_dir / "frozen_v4_layers.npz")
    pred, wet, dry, region, mapped, lc, hand, chain = z["pred"], z["wet"], z["dry"], z["region"], z["mapped"], z["landcover"], z["hand"], z["chainage"]
    scored = region & mapped
    area = 0.25
    blocks = block_ids(chain, cfg.block_m)
    lidar = np.isin(lc, LIDAR_LANDCOVER) & (hand < LIDAR_LIMIT_M)
    ctx = truth_context(site, site.pairs[pair_name].wet_time)
    near = np.min(np.abs(chain[..., None] - np.asarray(ctx.gauge_chainage_m)), axis=-1) <= NEAR_GAUGE_M

    def report(p, reg):
        s = score(p, wet, dry, reg)
        return {"scores": s.to_dict(area), "ci95": block_bootstrap(p, wet, dry, blocks, reg, n_boot=cfg.n_boot, seed=cfg.seed) if s.tp + s.fn + s.fp > 0 else None}

    judged = float((wet & scored).sum() * area) >= 500.0 and (v4["coverage_of_confirmed_flooding"] or 0) >= 0.6
    csi = v4["primary_v4"]["scores"]["csi"]
    signal = trust_signal(v4["confident"], day_rain["rainy"])
    return {
        "site": site.name, "pair": pair_name, "protocol": "research/OVERBANK_PROTOCOL.md", "git_head": _git_head(), "rain": day_rain, "confident": v4["confident"], "trust_signal": signal,
        "judgeable": judged, "v4_csi": csi, "signal_right": bool((csi >= 0.6) == (signal == "green")) if judged else None, "truth_ha": v4["truth_ha"], "coverage": v4["coverage_of_confirmed_flooding"],
        "primary_v4": v4["primary_v4"], "baseline_v3_same_pixels": v4["baseline_v3_same_pixels"], "v4_minus_v3_csi": v4["v4_minus_v3_csi"], "upland_warning": v4["upland_warning"],
        "high_ground_db": v4["high_ground_db"], "low_minus_high_db": v4["low_minus_high_db"], "used_hh_minus_hv": v4["used_hh_minus_hv"],
        "lidar_2m_same_pixels": report(lidar, scored), "v4_minus_lidar_csi": paired_csi_difference(pred, lidar, wet, dry, blocks, scored, cfg.n_boot, cfg.seed) if ((wet | dry) & scored).any() else None,
        "within_5km_of_gauge": {"v4": report(pred, scored & near), "lidar_2m": report(lidar, scored & near), "estimated_ha": float((wet & scored & near).sum() * area)},
        "wet_share_of_labelled": float((wet & scored).sum() / max(((wet | dry) & scored).sum(), 1)),
    }
