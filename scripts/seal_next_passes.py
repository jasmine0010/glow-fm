"""Seal the next NISAR passes over US rivers in flood, before they happen (research/SEALED_TEST_PROTOCOL.md §2).

    python scripts/seal_next_passes.py            # seal once: writes research/sealed/sealed_<date>.json and the receipt
    python scripts/seal_next_passes.py --dry-run  # the same list, written to outputs/sealed_dry/ and not sealed

Reads only NOAA's gauge list and stage records and NASA's catalog dates: no radar, no estimate, no score. Uses the
frozen live code (hidden_floods.live) without changing it. Refuses to seal twice.
"""

import argparse
import json
import subprocess
import sys
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hidden_floods import live
from hidden_floods.config import REPO_ROOT
from hidden_floods.sealed import BASELINE_DAYS, MAX_BASELINE, MIN_BASELINE, digest, predicted_times

SEALED_DIR = REPO_ROOT / "research" / "sealed"
RECEIPT = REPO_ROOT / "research" / "freeze_receipt_sealed.json"
HASHED = ("research/SEALED_TEST_PROTOCOL.md", "scripts/seal_next_passes.py", "scripts/score_sealed.py", "src/hidden_floods/sealed.py",
          "src/hidden_floods/live.py", "scripts/live_cases.py", "research/freeze_receipt_live.json", "research/freeze_receipt_v4.json",
          "research/OVERBANK_PROTOCOL.md", "scripts/rain_imerg.py")


def git_head() -> str:
    out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=False,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return out.stdout.strip()


def iso(t: datetime) -> str:
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def seal(now: datetime) -> dict:
    passes, left_out = [], []
    gauges = live.us_candidates()
    print(f"{len(gauges)} NOAA gauges at flood stage", flush=True)
    for g in sorted(gauges, key=lambda g: (g["state"], g["name"])):
        where = {"lid": g["lid"], "name": g["name"], "state": g["state"], "category": g["category"]}
        try:
            w = live.us_flood_window(g["lid"], now)
        except Exception as e:  # noqa: BLE001
            left_out.append(where | {"reason": f"NOAA's record didn't answer ({type(e).__name__})."})
            continue
        if not w.get("usgs"):
            left_out.append(where | {"reason": "No USGS gauge is linked to this NOAA gauge."})
            continue
        if not w.get("from"):
            left_out.append(where | {"reason": "NOAA's record doesn't show when this flood began."})
            continue
        start = w["from"]
        try:
            scenes = live.scenes_over(g["lon"], g["lat"], start - timedelta(days=BASELINE_DAYS), now)
        except Exception as e:  # noqa: BLE001
            left_out.append(where | {"reason": f"NASA's catalog didn't answer ({type(e).__name__})."})
            continue
        if not scenes:
            left_out.append(where | {"reason": "No NISAR pass of the method's kind (40 MHz, HH and HV) over this point since 60 days before the flood."})
            continue
        stacks = defaultdict(list)
        for s in scenes:
            stacks[s.stack_key].append(s)
        for key, ss in sorted(stacks.items()):
            pre = [s for s in ss if s.time < start]
            if len(pre) < MIN_BASELINE:
                left_out.append(where | {"stack": key, "reason": f"Only {len(pre)} pass{'' if len(pre) == 1 else 'es'} on this track in the 60 days before the flood; the method needs {MIN_BASELINE}."})
                continue
            latest = max(s.time for s in ss)
            times = predicted_times(latest, now)
            if not times:
                left_out.append(where | {"stack": key, "reason": "No pass on this track falls within the next 24 days."})
                continue
            for t in times:
                passes.append(where | {"id": f"{g['lid'].lower()}_{key}_{t:%Y%m%dT%H%M}", "lat": g["lat"], "lon": g["lon"], "usgs": w["usgs"],
                                       "flood_from": iso(start), "stack": key, "latest_pass": iso(latest), "predicted_utc": iso(t),
                                       "baseline": [s.scene.name for s in pre[-MAX_BASELINE:]]})
        print(f"  {g['lid']} {g['name']}, {g['state']}: {sum(p['lid'] == g['lid'] for p in passes)} passes sealed", flush=True)
    passes.sort(key=lambda p: p["predicted_utc"])
    return {"sealed_utc": iso(now), "git_head": git_head(), "protocol": "research/SEALED_TEST_PROTOCOL.md",
            "rules": {"repeat_days": 12, "horizon_days": 24, "match_hours": 1, "missing_after_days": 30, "min_baseline": MIN_BASELINE,
                      "baseline_days": BASELINE_DAYS, "trust": "OVERBANK_PROTOCOL.md §4", "judgeable": "OVERBANK_PROTOCOL.md §6"},
            "passes": passes, "left_out": left_out}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="write the list to outputs/sealed_dry/ without sealing")
    args = ap.parse_args()
    if not args.dry_run and RECEIPT.exists():
        raise SystemExit(f"already sealed: {RECEIPT.relative_to(REPO_ROOT)}. A sealed list is never replaced.")
    now = datetime.now(UTC)
    record = seal(now)
    folder = REPO_ROOT / "outputs" / "sealed_dry" if args.dry_run else SEALED_DIR
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"sealed_{now:%Y%m%dT%H%M}.json"
    path.write_text(json.dumps(record, indent=1))
    print(f"{len(record['passes'])} passes sealed, {len(record['left_out'])} gauges or tracks left out -> {path.relative_to(REPO_ROOT)}")
    if args.dry_run:
        return
    files = (*HASHED, str(path.relative_to(REPO_ROOT)).replace("\\", "/"))
    RECEIPT.write_text(json.dumps({"sealed_utc": record["sealed_utc"], "list": files[-1], "sha256": {f: digest(REPO_ROOT / f) for f in files}}, indent=1))
    print(f"receipt -> {RECEIPT.relative_to(REPO_ROOT)}. Commit both before {record['passes'][0]['predicted_utc'] if record['passes'] else 'the first pass'}.")


if __name__ == "__main__":
    main()
