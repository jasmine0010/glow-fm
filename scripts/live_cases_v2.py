"""Live cases under protocol v2 (research/LIVE_PROTOCOL_V2.md): v1 with FABDEM heights where there is no lidar.

    python scripts/live_cases_v2.py --check     # replay: rebuild each v1 world case with v1's heights; must give v1's run back
    python scripts/live_cases_v2.py --freeze    # write research/freeze_receipt_live_v2.json
    python scripts/live_cases_v2.py --rebuild   # once: publish <id>_v2 for every v1 world case, FABDEM heights, nothing else changed
    python scripts/live_cases_v2.py --dev       # new floods, development: no estimate, no score, into outputs/live_dev
    python scripts/live_cases_v2.py             # new floods, the frozen run

New floods run the v1 job (scripts/live_cases.py, unchanged and still hashed in the v1 receipt) with
hidden_floods.live_v2 in place of hidden_floods.live, so the only difference is where a box's heights come from.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import live_cases as v1

from hidden_floods import live_v2
from hidden_floods.frozen_v4 import RECEIPT as RECEIPT_V4
from hidden_floods.frozen_v4 import rule_from
from hidden_floods.stamps import stamp

HASHED = (*v1.HASHED, "research/freeze_receipt_live.json", "research/LIVE_PROTOCOL_V2.md", "scripts/live_cases_v2.py", "src/hidden_floods/live_v2.py")
INDEX = live_v2.OUT / "index.json"


def changed() -> list[str]:
    if not live_v2.RECEIPT.exists():
        return ["no v2 receipt: run with --freeze first"]
    rec = json.loads(live_v2.RECEIPT.read_text())["sha256"]
    return [rel for rel in HASHED if rec.get(rel) != v1.digest(rel)] + [f"v1: {x}" for x in v1.changed_since_freeze()]


def v1_world_cases() -> list[str]:
    index = json.loads(INDEX.read_text())
    return [c["id"] for c in index["cases"] if c["kind"] == "world" and c.get("protocol", 1) == 1]


def check() -> None:
    """The replay: v1's own heights, rebuilt on the rebuilt grid, must reproduce every v1 world run. No FABDEM is read."""
    rule = rule_from(json.loads(RECEIPT_V4.read_text()))
    bad = 0
    for cid in v1_world_cases():
        rec = json.loads((live_v2.OUT / cid / "case.json").read_text(encoding="utf8"))
        r = live_v2.replay_v1(rec, live_v2.OUT / cid, rule)
        bad += not r["agrees"]
        print(f"{'ok  ' if r['agrees'] else 'FAIL'} {cid}: flagged {r['flagged_px']} vs {r['flagged_px_v1']} px, cut-off {r['threshold_db']:.4f} vs "
              f"{r['threshold_db_v1']:.4f} dB, heights within {r['height_max_diff_m']:.3f} m on {r['height_px']} px ({r['height_nan_mismatch_px']} gaps differ)", flush=True)
    print(f"{bad} FAILED" if bad else "LIVE V2 REPLAY PASSED")
    if bad:
        raise SystemExit(1)


def rebuild() -> None:
    """Once, from the frozen receipt: every v1 world case gets a v2 twin. The attempt is logged before any FABDEM is read."""
    if changed():
        raise SystemExit(f"changed since the v2 freeze, not running: {changed()}")
    rule = rule_from(json.loads(RECEIPT_V4.read_text()))
    index = json.loads(INDEX.read_text())
    todo = v1_world_cases()
    if any((live_v2.OUT / f"{cid}{live_v2.SUFFIX}").exists() for cid in todo):
        raise SystemExit("v2 cases already exist; a published case is never rebuilt")
    for cid in todo:
        attempt = {**stamp("started_utc"), "case": f"{cid}{live_v2.SUFFIX}", "rebuilt_from": cid, "git_head": v1.git_head()}
        with open(live_v2.ATTEMPTS, "a") as log:
            log.write(json.dumps(attempt) + "\n")
        rec = live_v2.rerun_world(cid, rule)
        rec["attempt"] = attempt
        (live_v2.OUT / rec["id"] / "case.json").write_text(json.dumps(rec, indent=2, default=str))
        old = next(c for c in index["cases"] if c["id"] == cid)
        old["superseded_by"] = rec["id"]
        index["cases"].append({**{k: v for k, v in old.items() if k != "superseded_by"}, "id": rec["id"], "protocol": 2, "rebuilt_from": cid})
        v = rec["v1_run"]
        print(f"{rec['id']}: {rec['frozen_run']['flagged_ha']:,.0f} ha flagged (v1: {v['flagged_ha']:,.0f}), confident {rec['frozen_run']['confident']} (v1: {v['confident']})", flush=True)
    index["protocols"] = ["research/LIVE_PROTOCOL.md", live_v2.PROTOCOL]
    INDEX.write_text(json.dumps(index, indent=2, default=str))
    print("LIVE V2 REBUILD DONE")


def run_new(dev: bool) -> None:
    """The v1 job with v2's inputs and receipt. Cases it adds are marked protocol 2 in the index."""
    v1.live, v1.HASHED = live_v2, HASHED
    out = v1.REPO_ROOT / "outputs" / "live_dev" if dev else live_v2.OUT
    v1.run(dev)
    path = out / "index.json"
    index = json.loads(path.read_text())
    for c in index["cases"]:
        case = json.loads((out / c["id"] / "case.json").read_text(encoding="utf8"))
        if case.get("inputs", {}).get("protocol") == live_v2.PROTOCOL:
            c["protocol"] = 2
    index.pop("protocol", None)
    index["protocols"] = ["research/LIVE_PROTOCOL.md", live_v2.PROTOCOL]
    path.write_text(json.dumps(index, indent=2, default=str))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--check", action="store_true", help="replay the v1 world cases with v1's heights (no FABDEM is read)")
    g.add_argument("--freeze", action="store_true", help="write the v2 receipt")
    g.add_argument("--rebuild", action="store_true", help="once: v2 twins of the v1 world cases")
    g.add_argument("--dev", action="store_true", help="new floods, development run")
    a = ap.parse_args()
    if a.check:
        check()
    elif a.freeze:
        v1.live, v1.HASHED = live_v2, HASHED
        v1.write_receipt()
    elif a.rebuild:
        rebuild()
    else:
        run_new(a.dev)
