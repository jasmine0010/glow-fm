"""Prepare every flood the dashboard shows, so each one can run in Run it yourself.

    python scripts/prepare_all_floods.py --check     # NASA's catalog only: which floods can run, and why the rest can't
    python scripts/prepare_all_floods.py             # prepare every runnable flood not prepared yet
    python scripts/prepare_all_floods.py --max 10    # at most 10 new floods this time

The live protocol (research/LIVE_PROTOCOL.md) picks up to 6 US and 4 world floods per run. This job runs the same
frozen job (scripts/live_cases.py with protocol v2's inputs, as scripts/live_cases_v2.py does) on every flood the
dashboard lists, with no cap. Nothing about the method changes: same receipts, same rule, same pack. What differs is
only which floods are run, so each case it adds is marked "selection": "coverage" and its attempts go to
research/coverage_attempts.log, apart from the protocol's own log. Cases already published are never rebuilt.

Besides the protocol's candidates it takes:
- US flood gauges whose NOAA record links no USGS gauge: the nearest USGS gauge on the same river (USGS NLDI), within
  2 km, stands in, so the box still gets its river line, lidar and gauges. With none, the flood runs map-only like a
  world flood (NISAR's map, FABDEM heights, WorldCover water), unscored, since NISAR alone still gives the area;
- GDACS floods inside the US, run as map-only cases like the world floods.

Radar is read with your Earthdata sign-in (~/.netrc) by HTTP range requests: only each 24 km box is read from each
granule. FABDEM tiles are cached by 1-degree tile, and floods are run tile by tile so each tile is read once.
Run scripts/build_world_floods.py first, and scripts/build_live_roads.py after. It ends by running
scripts/scope_cases.cjs, which marks the floods GLOWfm applies to, and scripts/pass_stage.py, which marks the US floods
whose river was below flood stage when NISAR passed.
"""

import argparse
import gzip
import json
import math
import subprocess
import sys
import time
import urllib.parse
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import live_cases as v1
import live_cases_v2 as v2
import pass_stage

from hidden_floods import live, live_v2
from hidden_floods.config import REPO_ROOT
from hidden_floods.stamps import stamp

INDEX = live_v2.OUT / "index.json"
CHECK = REPO_ROOT / "outputs" / "coverage_check.json"
ATTEMPTS = REPO_ROOT / "research" / "coverage_attempts.log"
NLDI = "https://api.water.usgs.gov/nldi/linked-data"
NO_LINK = "No USGS gauge is linked"
STAND_IN_KM = 2.0


def km(a, b):
    return math.hypot((b[0] - a[0]) * 111.32 * math.cos(math.radians(a[1])), (b[1] - a[1]) * 110.57)


def stand_in_gauge(lon, lat):
    """The nearest USGS gauge on the river at (lon, lat), within STAND_IN_KM, from USGS NLDI; None if there's none."""
    pos = json.loads(live._get(f"{NLDI}/comid/position?" + urllib.parse.urlencode({"f": "json", "coords": f"POINT({lon} {lat})"})))
    comid = pos["features"][0]["properties"]["identifier"]
    best = None
    for nav in ("UM", "DM"):
        try:
            g = json.loads(live._get(f"{NLDI}/comid/{comid}/navigation/{nav}/nwissite?distance=10"))
        except Exception:  # noqa: BLE001, S112  (public sources fail in many ways; the flood moves on)
            continue
        for f in g.get("features", []):
            sid = f["properties"].get("identifier", "")
            if sid.startswith("USGS-"):
                d = km((lon, lat), f["geometry"]["coordinates"][:2])
                if d <= STAND_IN_KM and (best is None or d < best[1]):
                    best = (sid.removeprefix("USGS-"), d)
    return best


def past_us_floods(now):
    """The past 60 days' US floods, from today's list if there is one, otherwise found now (scripts/past_us_floods.py)."""
    saved = REPO_ROOT / "outputs" / "past_us_floods.json"
    if saved.exists():
        rec = json.loads(saved.read_text())
        if now - datetime.fromisoformat(rec["made_utc"]) < timedelta(days=1):
            return rec["floods"]
    import past_us_floods as finder
    return finder.find(60, now)["floods"]


def candidates(now):
    """The protocol's candidates (scripts/live_cases.py collect), plus the two extras above, world floods by FABDEM tile."""
    cases = v1.collect(now)
    for c in cases:
        if c.get("kind") == "us" and NO_LINK in c.get("skip", "") and c.get("lat") is not None:
            try:
                found = stand_in_gauge(c["lon"], c["lat"])
                w = live.us_flood_window(c["key"], now)
            except Exception as e:  # noqa: BLE001
                c["skip"] += f" Looking for a nearby USGS gauge failed ({type(e).__name__})."
                continue
            if not found and w.get("from"):
                # No gauge to grade it against: NISAR's map alone still gives the area and the rest, as for world floods
                # (heights from FABDEM, water from WorldCover), unscored.
                c.pop("skip")
                c.update({"kind": "world", "noaa": c["key"], "from": w["from"], "to": now, "report": None, "map_only": True,
                          "from_is_record_start": w.get("from_is_record_start", False)})
            elif not w.get("from"):
                c["skip"] = "NOAA's record doesn't show when this flood began."
            else:
                c.pop("skip")
                c.update({"usgs": found[0], "usgs_stand_in_km": round(found[1], 2), "from": w["from"], "to": now,
                          "from_is_record_start": w.get("from_is_record_start", False), "stage_now_ft": w.get("stage_now_ft"), "minor_ft": w.get("minor_ft")})
    # US floods from the past 60 days that have already receded (scripts/past_us_floods.py): NOAA's live list only has
    # the gauges in flood now, while the world list looks back 60 days. Each is a US case like the live ones, with its
    # USGS gauge, its window from the daily levels, and graded against its gauges and lidar where they allow it.
    now_lids = {str(c["key"]) for c in cases if c.get("kind") == "us"}
    for f in past_us_floods(now):
        if f["lid"] in now_lids:
            continue
        cases.append({"kind": "us", "key": f["lid"], "name": f["name"], "place": f"{f['name']}, {f['state']}", "category": f["category"],
                      "lat": f["lat"], "lon": f["lon"], "usgs": f["usgs"], "from": datetime.fromisoformat(f["from"]),
                      "to": min(datetime.fromisoformat(f["to"]), now), "from_is_record_start": f.get("from_is_window_start", False),
                      "minor_ft": f["minor_ft"], "past": not f.get("ongoing")})
    saved = json.loads((REPO_ROOT / "app" / "data" / "dashboard" / "world_floods.json").read_text(encoding="utf8"))
    us_gdacs = [e for e in saved["events"] if e["country"] == "United States" and (e["nisar"] or {}).get("count")]
    for c in live.world_candidates(us_gdacs):
        cases.append({"kind": "world", "key": c["id"], "name": c["name"], "place": c["country"], "category": c["alert"].lower(), "lat": c["lat"], "lon": c["lon"],
                      "from": c["from"], "to": min(c["to"], now), "report": c["report"]})
    us = [c for c in cases if c["kind"] == "us"]
    world = sorted((c for c in cases if c["kind"] == "world"), key=lambda c: (math.floor(c["lat"]), math.floor(c["lon"])))
    return us + world


def check(now, cands=None):
    """NASA's catalog only: for every candidate, the pass it would run, or why it can't."""
    runnable, skipped = [], []
    for c in cands if cands is not None else candidates(now):
        row = {"kind": c["kind"], "key": str(c["key"]), "name": c["name"], "place": c.get("place")}
        if c["kind"] == "world" and not c.get("noaa"):
            row["gdacs"] = str(c["key"])
        if c.get("skip"):
            skipped.append(row | {"skip": c["skip"]})
            continue
        try:
            picked = v1.with_retry(lambda c=c: live.pick_scenes(c["lon"], c["lat"], c["from"], c["to"]))
        except Exception as e:  # noqa: BLE001
            skipped.append(row | {"skip": f"NASA's catalog didn't answer ({type(e).__name__})"})
            continue
        if not picked["ok"]:
            skipped.append(row | {"skip": picked["reason"]})
            continue
        wet = picked["wet"]
        row |= {"id": f"{c['kind']}_{str(c['key']).lower()}_{wet.time:%Y%m%d}", "wet": live._iso(wet.time), "baseline": len(picked["baseline"])}
        runnable.append(row)
        print(f"  can run  {row['id']}: {c.get('place')}, {len(picked['baseline'])} earlier passes", flush=True)
    done = {c["id"] for c in json.loads(INDEX.read_text())["cases"]}
    out = {**stamp("checked_utc"), "runnable": runnable, "skipped": skipped, "new": [r["id"] for r in runnable if r["id"] not in done]}
    CHECK.parent.mkdir(parents=True, exist_ok=True)
    CHECK.write_text(json.dumps(out, indent=2, default=str))
    reasons = {}
    for s in skipped:
        reasons[s["skip"].split(";")[0][:90]] = reasons.get(s["skip"].split(";")[0][:90], 0) + 1
    print(f"\n{len(runnable)} can run ({len(out['new'])} not prepared yet), {len(skipped)} can't:")
    for r, n in sorted(reasons.items(), key=lambda x: -x[1]):
        print(f"  {n:3d}  {r}")
    print(f"-> {CHECK}")
    return out


def no_nan(x):
    """Strict JSON for the browser: NaN and infinities become null."""
    if isinstance(x, float) and not math.isfinite(x):
        return None
    if isinstance(x, dict):
        return {k: no_nan(v) for k, v in x.items()}
    if isinstance(x, list):
        return [no_nan(v) for v in x]
    return x


def unscorable(rec, c):
    """A pass that left no gauge-and-lidar pixels to compare has no score (its match score is 0/0), so it is listed
    as unscored rather than with a score of NaN."""
    sc = (rec.get("score") or {}).get("scores") or {}
    if not sc or sum(sc.get(k) or 0 for k in ("tp", "fn", "fp", "tn")) > 0:
        return
    rec["score_empty"] = no_nan(rec.pop("score"))
    rec["unscored_why"] = "No gauge-and-lidar area to compare on this pass"
    c["scored"] = False


def prepare(now, most):
    if v2.changed():
        raise SystemExit(f"changed since the v2 freeze, not running: {v2.changed()}")
    cands = candidates(now)
    plan = check(now, cands)
    todo = set(plan["new"][:most] if most else plan["new"])
    if not todo:
        print("nothing new to prepare")
    before = json.loads(INDEX.read_text())
    # The frozen job, run as scripts/live_cases_v2.py runs it, on the runnable floods only and with no per-run cap.
    want = {r["key"] for r in plan["runnable"] if r["id"] in todo}
    v1.live, v1.HASHED = live_v2, v2.HASHED
    v1.MAX_US = v1.MAX_WORLD = 10**6
    v1.collect = lambda _now: [c for c in cands if str(c["key"]) in want and not c.get("skip")]
    live_v2.ATTEMPTS = ATTEMPTS
    t0 = time.time()
    if todo:
        v1.run(dev=False)
    after = json.loads(INDEX.read_text())
    old = {c["id"] for c in before["cases"]}
    by_key = {(s["name"], s.get("place")): s for s in plan["skipped"] + plan["runnable"]}
    failed = [by_key.get((s["name"], s.get("place")), {}) | s for s in after.get("considered", [])] if todo else []
    for c in after["cases"]:
        if c["id"] in old:
            continue
        rec_path = live_v2.OUT / c["id"] / "case.json"
        rec = json.loads(rec_path.read_text(encoding="utf8"))
        rec["selection"] = "coverage"
        cand = next((x for x in cands if str(x["key"]).lower() == c["id"].split("_")[1]), {})
        if cand.get("usgs_stand_in_km") is not None:     # the NOAA record named no USGS gauge; this one, on the same river, stood in
            rec["usgs_stand_in_km"] = cand["usgs_stand_in_km"]
        if cand.get("past"):             # a US flood that had already receded: it ran from this date to that one
            rec["flood_to"] = live._iso(cand["to"])
        if cand.get("noaa") and cand.get("map_only"):    # a US flood with no USGS gauge near it: NISAR's map only, unscored
            rec["noaa"] = c["noaa"] = cand["noaa"]
            rec["map_only"] = c["map_only"] = True
            c["gdacs"] = None
        unscorable(rec, c)
        rec_path.write_text(json.dumps(no_nan(rec), indent=2, default=str, allow_nan=False))
        c["selection"] = "coverage"
        pack = live_v2.OUT / c["id"] / "pack.bin"
        if pack.exists():     # stored gzipped, about half the size; app/live.js unpacks it
            (pack.parent / "pack.bin.gz").write_bytes(gzip.compress(pack.read_bytes(), 9, mtime=0))
            pack.unlink()
            c["pack"] = "gz"
        if rec.get("inputs", {}).get("protocol") == live_v2.PROTOCOL:
            c["protocol"] = 2
    # The protocol's own record of what it considered stays as it was; this job's goes under "coverage".
    after["considered"] = before.get("considered", [])
    after.pop("protocol", None)
    after["protocols"] = before.get("protocols", ["research/LIVE_PROTOCOL.md", live_v2.PROTOCOL])
    ran = {c["id"] for c in after["cases"]}
    skipped = plan["skipped"] + [f for f in failed if f.get("id") not in ran]
    after["coverage"] = {**stamp("checked_utc"), "about": "Every dashboard flood with a usable NISAR pass, prepared by scripts/prepare_all_floods.py "
                         "with the frozen method; not picked by the live protocol.",
                         "skipped": [{k: s[k] for k in ("kind", "gdacs", "key", "name", "place", "skip") if k in s} for s in skipped]}
    INDEX.write_text(json.dumps(after, indent=2, default=str))
    # Which floods GLOWfm applies to (app/livescope.js): mostly forest or wetland on the valley floor. The rest stay
    # prepared but aren't offered to run.
    subprocess.run(["node", str(REPO_ROOT / "scripts" / "scope_cases.cjs"), str(INDEX.parent)], check=True)
    # Whether each US river was at flood stage when NISAR passed (scripts/pass_stage.py); those that weren't aren't offered.
    pass_stage.main()
    new = sorted(ran - old)
    print(f"\n{len(new)} new floods prepared in {(time.time() - t0) / 60:.0f} min: {', '.join(new) or 'none'}")
    print("PREPARE ALL FLOODS DONE")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="NASA's catalog only; nothing is read or written but outputs/coverage_check.json")
    ap.add_argument("--max", type=int, default=0, help="at most this many new floods (0: all)")
    a = ap.parse_args()
    now = datetime.now(UTC)
    if a.check:
        check(now)
    else:
        prepare(now, a.max)
