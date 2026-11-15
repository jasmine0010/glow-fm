"""Prepare live cases: run the frozen method v4 on floods happening now (research/LIVE_PROTOCOL.md).

    python scripts/live_cases.py --dev     # build inputs and run the method, no estimate and no score (for development)
    python scripts/live_cases.py           # the frozen run: checks the receipt, logs each attempt, scores US cases once

Runs on your computer only. NISAR scenes are read with your Earthdata sign-in through curl and ~/.netrc, as the rest
of the project does; the sign-in never reaches the site. Everything else is public: NOAA gauges, USGS river lines and
gauges, 3DEP lidar, ESA WorldCover, Copernicus GLO-30 and GDACS (through app/data/dashboard/world_floods.json, so run
scripts/build_world_floods.py first).
"""

import argparse
import hashlib
import http.client
import json
import subprocess
import sys
import time
import urllib.error
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hidden_floods import live
from hidden_floods.config import REPO_ROOT
from hidden_floods.frozen_v3 import RECEIPT_V3, settings_from
from hidden_floods.frozen_v4 import RECEIPT as RECEIPT_V4
from hidden_floods.frozen_v4 import rule_from
from hidden_floods.stamps import stamp

HASHED = ("research/LIVE_PROTOCOL.md", "scripts/live_cases.py", "src/hidden_floods/live.py", "src/hidden_floods/v4.py", "src/hidden_floods/truth.py",
          "src/hidden_floods/metrics.py", "src/hidden_floods/selfcal.py", "src/hidden_floods/stack.py", "src/hidden_floods/io/nisar.py",
          "src/hidden_floods/io/gauges.py", "src/hidden_floods/io/dem.py", "src/hidden_floods/grid.py", "src/hidden_floods/trust.py",
          "src/hidden_floods/audit.py", "research/freeze_receipt_v4.json")
MAX_US, MAX_WORLD = 6, 4
ALERT_RANK = {"Red": 0, "Orange": 1, "Green": 2}


def digest(rel: str) -> str:
    return hashlib.sha256((REPO_ROOT / rel).read_bytes()).hexdigest()


def write_receipt() -> None:
    rec = {**stamp("created_utc"), "sha256": {rel: digest(rel) for rel in HASHED}}
    live.RECEIPT.write_text(json.dumps(rec, indent=2) + "\n")
    print(f"receipt written: {live.RECEIPT}")


def changed_since_freeze() -> list[str]:
    if not live.RECEIPT.exists():
        return ["no receipt: run with --freeze first"]
    rec = json.loads(live.RECEIPT.read_text())["sha256"]
    return [rel for rel in HASHED if rec.get(rel) != digest(rel)]


def git_head() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except Exception:  # noqa: BLE001
        return "no commits"


def quicklook(granule: dict) -> dict | None:
    link = next((u["URL"] for u in granule.get("RelatedUrls", []) if u.get("Type") == "GET RELATED VISUALIZATION" and u["URL"].startswith("https")
                 and u["URL"].endswith("_LATLON.png")), None)
    pts = granule["SpatialExtent"]["HorizontalSpatialDomain"]["Geometry"]["GPolygons"][0]["Boundary"]["Points"][:4]
    return {"url": link, "corners": [[p["Longitude"], p["Latitude"]] for p in pts]} if link else None


NETWORK = (urllib.error.URLError, ConnectionError, TimeoutError, http.client.HTTPException, subprocess.CalledProcessError)


def with_retry(step):
    """A dropped connection gets one more try a minute later; any other failure is reported as it is."""
    try:
        return step()
    except NETWORK as e:
        print(f"   network trouble ({type(e).__name__}), trying again in a minute", flush=True)
        time.sleep(60)
        return step()


def collect(now: datetime) -> list[dict]:
    """Every candidate, US first, each with its flood window; selection limits are applied after scene checks."""
    cases = []
    try:
        us = live.us_candidates()
    except Exception as e:  # noqa: BLE001
        us = []
        cases.append({"kind": "us", "key": "noaa", "name": "NOAA gauge list", "place": "All US gauges", "skip": f"NOAA's gauge list didn't answer this time ({type(e).__name__})."})
    for g in sorted(us, key=lambda g: ["major", "moderate", "minor"].index(g["category"])):
        try:
            w = live.us_flood_window(g["lid"], now)
        except Exception as e:  # noqa: BLE001
            cases.append({"kind": "us", "key": g["lid"], "name": g["name"], "skip": f"NOAA record unavailable ({type(e).__name__})"})
            continue
        base = {"kind": "us", "key": g["lid"], "name": g["name"], "place": f"{g['name']}, {g['state']}", "category": g["category"], "lat": g["lat"], "lon": g["lon"]}
        if not w.get("usgs"):
            cases.append(base | {"skip": "No USGS gauge is linked to this NOAA gauge, so there's no river line or datum."})
        elif not w.get("from"):
            cases.append(base | {"skip": "NOAA's record doesn't show when this flood began."})
        else:
            cases.append(base | {"usgs": w["usgs"], "from": w["from"], "to": now, "from_is_record_start": w.get("from_is_record_start", False),
                                 "stage_now_ft": w.get("stage_now_ft"), "minor_ft": w.get("minor_ft")})
    saved = json.loads((REPO_ROOT / "app" / "data" / "dashboard" / "world_floods.json").read_text(encoding="utf8"))
    world = [e for e in saved["events"] if e["country"] != "United States" and (e["nisar"] or {}).get("count")]
    world.sort(key=lambda e: (ALERT_RANK.get(e["alert"], 3), -e["nisar"]["count"]))
    for c in live.world_candidates(world):
        cases.append({"kind": "world", "key": c["id"], "name": c["name"], "place": c["country"], "category": c["alert"].lower(), "lat": c["lat"], "lon": c["lon"],
                      "from": c["from"], "to": min(c["to"], now), "report": c["report"]})
    return cases


def run(dev: bool) -> None:
    now = datetime.now(UTC)
    out_root = REPO_ROOT / "outputs" / "live_dev" if dev else live.OUT
    if not dev:
        changed = changed_since_freeze()
        if changed:
            raise SystemExit(f"changed since the freeze, not running: {changed}")
    rule = rule_from(json.loads(RECEIPT_V4.read_text()))
    cfg = settings_from(json.loads(RECEIPT_V3.read_text()))
    index_path = out_root / "index.json"
    index = json.loads(index_path.read_text()) if index_path.exists() else {"cases": [], "considered": []}
    done = {c["id"] for c in index["cases"]}
    considered, counts = [], {"us": 0, "world": 0}
    for c in collect(now):
        if c.get("skip"):
            considered.append({k: c[k] for k in ("kind", "name", "place", "skip") if k in c})
            continue
        if counts[c["kind"]] >= (MAX_US if c["kind"] == "us" else MAX_WORLD):
            continue
        try:
            picked = with_retry(lambda c=c: live.pick_scenes(c["lon"], c["lat"], c["from"], c["to"]))
        except Exception as e:  # noqa: BLE001
            considered.append({"kind": c["kind"], "name": c["name"], "place": c.get("place"), "skip": f"NASA's catalog didn't answer ({type(e).__name__})"})
            continue
        if not picked["ok"]:
            considered.append({"kind": c["kind"], "name": c["name"], "place": c.get("place"), "skip": picked["reason"]})
            continue
        wet = picked["wet"]
        case_id = f"{c['kind']}_{str(c['key']).lower()}_{wet.time:%Y%m%d}"
        counts[c["kind"]] += 1
        if case_id in done:
            print(f"{case_id}: already run, kept as published")
            continue
        c["id"] = case_id
        attempt = {**stamp("started_utc"), "case": case_id, "dev": dev, "git_head": git_head()}
        if not dev:
            with open(live.ATTEMPTS, "a") as log:   # written before any imagery is read
                log.write(json.dumps(attempt) + "\n")
        print(f"{case_id}: {c['place']} - wet {wet.time:%Y-%m-%d}, {len(picked['baseline'])} earlier passes", flush=True)
        try:
            p = with_retry(lambda c=c, picked=picked: live.prepare(c, picked, score_it=(c["kind"] == "us" and not dev)))
            res = live.run_rule(p, rule)
        except Exception as e:  # noqa: BLE001
            considered.append({"kind": c["kind"], "name": c["name"], "place": c.get("place"), "skip": f"The method couldn't run here: {e}"})
            print(f"   failed: {e}", flush=True)
            continue
        folder = out_root / case_id
        layout = live.write_pack(p, folder)
        area = p.grid.pixel_area_ha
        # The browser's default run must match this one; the reference is computed on the stored (rounded) arrays.
        d = live.decode_pack(folder, layout)
        ref = rule.apply(d["wet_hh"] - d["median_hh"], d["wet_hv"] - d["median_hv"], d["landcover"], d["timing"], d["hand"], d["dist"])
        record = {
            "id": case_id, "kind": c["kind"], "name": c["name"], "place": c["place"], "category": c["category"], "lat": c["lat"], "lon": c["lon"],
            "flood_from": live._iso(c["from"]), "flood_from_is_record_start": c.get("from_is_record_start", False), **stamp("checked_utc"),
            "report": c.get("report"), "usgs": c.get("usgs"), "noaa": c["key"] if c["kind"] == "us" else None,
            "wet": {"time": live._iso(wet.time), "name": wet.scene.name, "stack": wet.stack_key, "quicklook": quicklook(wet.granule)},
            "baseline": [{"time": live._iso(s.time), "name": s.scene.name} for s in picked["baseline"]], "passes_during": picked["passes_during"],
            "corners": live.corners_lonlat(p.grid), "pixel_ha": area, "layout": layout, "inputs": p.info,
            "rule": rule.to_dict(), "frozen_run": {"threshold_db": res["threshold_db"], "used_hh_minus_hv": res["used_hh_minus_hv"], "confident": res["confident"],
                                                  "low_minus_high_db": res["low_minus_high_db"], "flagged_ha": float((res["pred"] & ~p.water).sum() * area),
                                                  "mapped_ha": float(res["mapped"].sum() * area)},
            "reference_run": {"threshold_db": ref["threshold_db"], "flagged_px": int(ref["pred"].sum()), "flagged_land_px": int((ref["pred"] & (d["water"] == 0)).sum()), "used_hh_minus_hv": ref["used_hh_minus_hv"],
                              "confident": ref["confident"], "low_minus_high_db": ref["low_minus_high_db"]},
            "score": None, "attempt": attempt, "dev": dev,
        }
        if p.truth is not None:
            record["score"] = live.score_case(p, res, cfg.block_m, cfg.n_boot, cfg.seed)
        elif c["kind"] == "us" and not dev:
            record["score_skipped"] = "No usable USGS gauge with a known height reference in the box."
        (folder / "case.json").write_text(json.dumps(record, indent=2, default=lambda o: o.item() if isinstance(o, np.generic) else str(o)))
        index["cases"] = [x for x in index["cases"] if x["id"] != case_id] + [{"id": case_id, "kind": c["kind"], "place": c["place"], "name": c["name"],
                                                                              "category": c["category"], "wet": record["wet"]["time"], "scored": record["score"] is not None,
                                                                              "lat": c["lat"], "lon": c["lon"], "gdacs": c["key"] if c["kind"] == "world" else None}]
        print(f"   done: {record['frozen_run']['flagged_ha']:,.0f} ha flagged" + ("" if record["score"] is None else ", scored"), flush=True)
    index = {k: v for k, v in index.items() if k != "checked_utc"} | {**stamp("checked_utc"), "considered": considered, "protocol": "research/LIVE_PROTOCOL.md"}
    out_root.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(index, indent=2, default=str))
    print(f"{len(index['cases'])} cases published, {len(considered)} considered and skipped -> {index_path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev", action="store_true", help="development run: no estimate, no score, written to outputs/live_dev")
    ap.add_argument("--freeze", action="store_true", help="write the receipt that fixes the rules before the first frozen run")
    a = ap.parse_args()
    if a.freeze:
        write_receipt()
    else:
        run(a.dev)
