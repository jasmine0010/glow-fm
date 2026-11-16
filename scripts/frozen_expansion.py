"""One-time replication of the overbank test on unread rivers (research/EXPANSION_PROTOCOL.md).

Scoring is the overbank test's own ``score_pass`` (src/hidden_floods/frozen_overbank.py), unchanged and hashed here. It maps
with the hashed v4 code and adds the lidar comparison, the near-gauge check and the trust signal. This wrapper only adds its
own hash gate, attempt log and write-once rule, and labels each result with this protocol. It lives in scripts/ so that
src/hidden_floods/, which earlier receipts hash, stays as it was.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from hidden_floods.config import REPO_ROOT, Site
from hidden_floods.frozen_overbank import _git_head, digest, score_pass
from hidden_floods.frozen_v4 import HASHED as V4_HASHED
from hidden_floods.frozen_v4 import check_receipt as check_v4_receipt
from hidden_floods.stack import Scene

RECEIPT = REPO_ROOT / "research" / "freeze_receipt_expansion.json"
SCENES = REPO_ROOT / "research" / "expansion_scenes.json"
RAIN = REPO_ROOT / "research" / "expansion_rain.json"
PROTOCOL = "research/EXPANSION_PROTOCOL.md"
SELF = (PROTOCOL, "research/expansion_scenes.json", "research/expansion_rain.json", "research/expansion_gauges.json", "research/expansion_dropped.json",
        "research/expansion_screen.json", "research/freeze_receipt_v4.json", "research/freeze_receipt_overbank.json", "src/hidden_floods/frozen_overbank.py",
        "scripts/frozen_expansion.py", "scripts/run_frozen_expansion.py", "scripts/setup_expansion.py", "scripts/screen_expansion.py")


def hashed_files() -> list[str]:
    sites = [f"sites/{river}.toml" for river in json.loads(SCENES.read_text())]
    return [*SELF, *sites, *[f for f in V4_HASHED if f not in SELF]]


def check_receipt(path: Path = RECEIPT) -> list[str]:
    rec = json.loads(Path(path).read_text())
    return [r for r in hashed_files() if rec["sha256"].get(r) != digest(r)]


def evaluate(site: Site, pair_name: str) -> dict:
    """Run one listed pass once. Refuses if any hashed file has changed or the pass has already been scored."""
    listing, rain = json.loads(SCENES.read_text()), json.loads(RAIN.read_text())
    if pair_name not in listing.get(site.name, {}).get("passes", {}):
        raise ValueError(f"{site.name}/{pair_name} is not a listed expansion pass")
    out_dir = REPO_ROOT / "outputs" / site.name / pair_name
    result_path = out_dir / "frozen_expansion_metrics.json"
    if result_path.exists():
        raise FileExistsError(f"{result_path} exists; each expansion pass runs once")
    changed = check_receipt() + check_v4_receipt()
    if changed:
        raise RuntimeError(f"changed since the freeze, not running: {changed}")
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "frozen_expansion_attempts.log", "a") as log:      # written before any imagery is read
        log.write(json.dumps({"started_utc": datetime.now(UTC).isoformat(timespec="seconds"), "git_head": _git_head(), "site": site.name, "pair": pair_name}) + "\n")
    scenes = [Scene(**s) for s in listing[site.name]["passes"][pair_name]["scenes"]]
    result = score_pass(site, pair_name, scenes, rain[site.name][pair_name], out_dir) | {"protocol": PROTOCOL}
    result_path.write_text(json.dumps(result, indent=2, default=str))
    return result
