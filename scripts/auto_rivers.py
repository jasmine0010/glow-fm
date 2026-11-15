"""Add US rivers in flood to the dashboard automatically: the dashboard's own rivers, not tests.

    python scripts/auto_rivers.py              add up to 3 new rivers, then rebuild the dashboard data
    python scripts/auto_rivers.py --dry-run    only say what it would add or skip, and why (reads no radar or lidar)
    python scripts/auto_rivers.py --max 5

For each NOAA gauge at minor flood stage or worse (hidden_floods.live.us_candidates, as Run it yourself uses), it
builds the river the way scripts/setup_st_johns.py did, and keeps it only if every check passes:
- the flooding gauge and at least one more on the same main stem (USGS river lines, within 60 km) have a height
  above NAVD88: a published datum, or one derived from their own readings (river_setup.datum_from_readings);
- the gauges span at least 8 km of river;
- at least 20% of the 4 km corridor is tree cover (ESA WorldCover), since GLOWfm is about floods under trees;
- NISAR has passed over the flooding gauge during the flood, with enough earlier passes (live.pick_scenes).
Then it fetches stage records, the NWS minor flood stage, lidar (USGS 3DEP) and the radar box around the flooding
gauge, runs the frozen v4 rule on that box (live.prepare and live.run_rule, read-only), saves the map, adds the river
to sites/auto_rivers.json and rebuilds the dashboard data (scripts/build_dashboard.py). If that build's checks fail,
the new rivers are taken out again and the build rerun.

Radar is read with the Earthdata login this computer already uses (as scripts/live_cases.py). Every decision is
appended to <data root>/auto_rivers/log.jsonl. Nothing here is scored, and Run it yourself's and the sealed test's
records are not touched. Dams and levees are not checked: these rivers are labelled "added automatically, not tested".
"""

import argparse
import json
import re
import subprocess
import sys
import tomllib
import urllib.error
from datetime import UTC, datetime, timedelta

import numpy as np
from river_setup import (
    datum_from_readings,
    km,
    length_km,
    main_stem,
    nws_minor_stage,
    stem_gauges,
    valley,
    worldcover_tiles,
)

from hidden_floods import live
from hidden_floods.config import REPO_ROOT, data_root, load_site
from hidden_floods.fetch import fetch_usgs_stage
from hidden_floods.frozen_v4 import RECEIPT as V4_RECEIPT
from hidden_floods.frozen_v4 import rule_from
from hidden_floods.grid import grid_from_lonlat_bbox
from hidden_floods.io.dem import fetch_3dep
from hidden_floods.sitegen import GaugeMeta, buffered_bbox, ngvd29_to_navd88_ft, site_toml, utm_epsg
from hidden_floods.trust import worldcover_on_grid
from hidden_floods.truth import ValleyLine

REGISTRY = REPO_ROOT / "sites" / "auto_rivers.json"
STEM_KM, MIN_SPAN_KM, MIN_TREES, CORRIDOR_M, ON_STEM_KM = 60, 8.0, 0.20, 4000.0, 0.5
LOG = data_root() / "auto_rivers" / "log.jsonl"


def log(entry):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({"utc": f"{datetime.now(UTC):%Y-%m-%dT%H:%M:%SZ}", **entry}) + "\n")
    print(f"{entry.get('lid', ''):7} {entry['decision']:8} {entry.get('name', '')[:46]:46} {entry.get('why', '')}", flush=True)


def registry():
    return json.loads(REGISTRY.read_text(encoding="utf-8")) if REGISTRY.exists() else {"rivers": []}


def known_gauges():
    out = set()
    for path in (REPO_ROOT / "sites").glob("*.toml"):
        out |= {g["id"].removeprefix("USGS-") for g in tomllib.loads(path.read_text(encoding="utf-8")).get("gauges", [])}
    return out


def gauge(usgs):
    """A gauge with its height above NAVD88, or None: a published datum (NGVD29 converted), else one derived from readings."""
    d = live.gauge_datum(usgs.removeprefix("USGS-"))
    if not d:
        return None
    sid = f"USGS-{d['usgs']}"
    if d["datum_ft"] is not None and d["datum"] in ("NAVD88", "NGVD29"):
        g = GaugeMeta(sid, d["name"], d["lon"], d["lat"], d["datum_ft"], d["datum"], None)
        g.navd88_offset_ft = ngvd29_to_navd88_ft(g.lon, g.lat) if g.datum == "NGVD29" else 0.0
        return g
    derived = datum_from_readings(sid)
    return None if derived is None else GaugeMeta(sid, d["name"], d["lon"], d["lat"], derived, "NAVD88", None)


def river_title(nws_name, state):
    river = re.split(r"\s+(?:at|near|nr|above|abv|below|blw|bl|ab)\s+", nws_name, maxsplit=1, flags=re.IGNORECASE)[0].strip()
    return f"{river}, {state}" if state else river


def tree_share(line, bbox):
    """Share of the corridor's land that is tree cover (WorldCover 10) or mangrove (95)."""
    crs = utm_epsg((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)
    grid = grid_from_lonlat_bbox(bbox, crs, 50.0, snap=50.0)
    worldcover_tiles(bbox)
    lc = worldcover_on_grid(data_root() / "worldcover", grid)
    dist, _ = ValleyLine.from_lonlat(grid, line).project(*grid.meshgrid())
    land = (dist < CORRIDOR_M) & (lc != 0) & (lc != 80)
    return float(np.isin(lc[land], (10, 95)).mean()) if land.any() else 0.0


def plan(c, now, known, taken):
    """Everything about one flooding NOAA gauge that needs no radar or lidar, or the reason to skip it."""
    base = {"lid": c["lid"], "name": c["name"]}
    w = live.us_flood_window(c["lid"], now)
    usgs = w.get("usgs")
    if not usgs:
        return base | {"decision": "skip", "why": "no USGS gauge linked to this NOAA gauge"}
    if usgs in known:
        return base | {"decision": "skip", "why": "already a dashboard river"}
    if usgs in taken:
        return base | {"decision": "skip", "why": "same river as another gauge in this run"}
    if not w.get("from"):
        return base | {"decision": "skip", "why": "NOAA's record doesn't show when this flood began"}
    sid = f"USGS-{usgs}"
    try:
        up, down = main_stem(sid, "UM", STEM_KM + 5), main_stem(sid, "DM", STEM_KM + 5)
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
        up = down = []
    if len(up) < 2 and len(down) < 2:
        return base | {"decision": "skip", "why": "USGS has no river line through this gauge"}
    line = up + (down[min(range(len(down)), key=lambda i: km(down[i], up[-1])) + 1:] if up and down else down)
    gauges = []
    for gid in stem_gauges(sid, STEM_KM):
        g = gauge(gid)
        if g and min(km(p, (g.lon, g.lat)) for p in line) <= ON_STEM_KM:
            gauges.append(g)
    if not any(g.id == sid for g in gauges):
        return base | {"decision": "skip", "why": "the flooding gauge has no height above NAVD88 (no datum, and no elevation readings)"}
    if len(gauges) < 2:
        return base | {"decision": "skip", "why": "only one gauge on this river has a height above NAVD88; the estimate needs two"}
    pos = {g.id: min(range(len(line)), key=lambda i, g=g: km(line[i], (g.lon, g.lat))) for g in gauges}
    gauges.sort(key=lambda g: pos[g.id])
    top, bottom = gauges[0], gauges[-1]
    span = length_km(line[pos[top.id]:pos[bottom.id] + 1])
    if span < MIN_SPAN_KM:
        return base | {"decision": "skip", "why": f"its gauges span only {span:.1f} km of river"}
    vline = valley(line, (top.lon, top.lat), (bottom.lon, bottom.lat))
    bbox = buffered_bbox(vline)
    trees = tree_share(vline, bbox)
    if trees < MIN_TREES:
        return base | {"decision": "skip", "why": f"only {trees:.0%} of its floodplain is under trees"}
    flood_gauge = next(g for g in gauges if g.id == sid)
    picked = live.pick_scenes(flood_gauge.lon, flood_gauge.lat, w["from"], now)
    if not picked["ok"]:
        return base | {"decision": "wait", "why": picked["reason"]}
    return base | {"decision": "add", "usgs": usgs, "state": c.get("state", ""), "category": c["category"], "from": w["from"], "minor_ft": w.get("minor_ft"),
                   "gauges": gauges, "valley": vline, "bbox": bbox, "trees": trees, "span_km": span, "picked": picked, "flood_gauge": flood_gauge}


def build(p, now, rule):
    """Fetch the river's data, run the frozen rule on the radar box around the flooding gauge, and save its map."""
    name = f"auto_{p['lid'].lower()}"
    crs = utm_epsg((p["bbox"][0] + p["bbox"][2]) / 2, (p["bbox"][1] + p["bbox"][3]) / 2)
    text = site_toml(name, crs, p["bbox"], p["gauges"], f"{p['name']}: added automatically by scripts/auto_rivers.py. Dashboard river only; no test.")
    text = re.sub(r"(?m)^line = \[.*\]$", "line = [" + ", ".join(f"[{x:.5f}, {y:.5f}]" for x, y in p["valley"]) + "]", text, count=1)
    (REPO_ROOT / "sites" / f"{name}.toml").write_text(text)
    site = load_site(name)
    start = f"{p['from'] - timedelta(days=30):%Y-%m-%dT%H:%M:%SZ}"
    for g in site.gauges:
        fetch_usgs_stage(g.id, start, f"{now:%Y-%m-%dT%H:%M:%SZ}", site.gauges_dir)
    minor, _ = nws_minor_stage(p["lid"])
    root = data_root() / name
    (root / "nws_flood_levels.json").write_text(json.dumps({"source": "NWS NWPS, minor flood stage (ft of gage height)", "levels": {p["usgs"]: minor} if minor else {}}))
    fetch_3dep(grid_from_lonlat_bbox(site.bbox, site.crs, 10.0, snap=50.0), site.dem_path)
    g, wet = p["flood_gauge"], p["picked"]["wet"]
    case = {"id": f"{name}_{wet.time:%Y%m%d}", "kind": "us", "lon": g.lon, "lat": g.lat, "usgs": p["usgs"]}
    prepared = live.prepare(case, p["picked"], score_it=False)
    res = live.run_rule(prepared, rule)
    flooded = res["pred"] & ~prepared.water
    b = prepared.grid
    np.savez_compressed(root / "auto_pass.npz", flooded=flooded)
    where = f"the 24 km box around {g.name.title().split(',')[0]}"
    return {"name": name, "title": river_title(p["name"], p["state"]), "event": f"{p['from']:%B %Y} flood", "lid": p["lid"], "usgs": p["usgs"],
            "added_utc": f"{now:%Y-%m-%dT%H:%M:%SZ}", "category": p["category"], "trees": round(p["trees"], 3), "span_km": round(p["span_km"], 1),
            "gauges": [x.id for x in p["gauges"]],
            "pass": {"file": f"{name}/auto_pass.npz", "time": f"{wet.time:%Y-%m-%dT%H:%M:%SZ}", "scene": wet.scene.name, "confident": bool(res["confident"]), "where": where,
                     "grid": {"crs": b.crs, "x0": b.x0, "y0": b.y0, "res": b.res, "width": b.width, "height": b.height}}}


def rebuild():
    return subprocess.run([sys.executable, str(REPO_ROOT / "scripts" / "build_dashboard.py")], check=False).returncode == 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max", type=int, default=3)
    a = ap.parse_args()
    now = datetime.now(UTC)
    reg, known, taken, added = registry(), known_gauges(), set(), []
    rule = rule_from(json.loads(V4_RECEIPT.read_text()))
    cands = sorted(live.us_candidates(), key=lambda c: ["major", "moderate", "minor"].index(c["category"]))
    print(f"{len(cands)} NOAA gauges in flood", flush=True)
    for c in cands:
        if len(added) >= a.max:
            break
        try:
            p = plan(c, now, known, taken)
        except Exception as e:  # noqa: BLE001  (public sources fail in many ways; the next gauge goes on)
            log({"lid": c["lid"], "name": c["name"], "decision": "error", "why": f"{type(e).__name__}: {e}"[:300]})
            continue
        if p["decision"] != "add":
            log({k: p[k] for k in ("lid", "name", "decision", "why")})
            continue
        taken |= {g.id.removeprefix("USGS-") for g in p["gauges"]}
        if a.dry_run:
            log({"lid": p["lid"], "name": p["name"], "decision": "would add", "why": f"{len(p['gauges'])} gauges over {p['span_km']:.0f} km, {p['trees']:.0%} under trees"})
            continue
        try:
            entry = build(p, now, rule)
        except Exception as e:  # noqa: BLE001
            log({"lid": p["lid"], "name": p["name"], "decision": "error", "why": f"while building: {type(e).__name__}: {e}"[:300]})
            continue
        reg["rivers"].append(entry)
        added.append(entry["name"])
        log({"lid": p["lid"], "name": p["name"], "decision": "added", "why": f"{len(p['gauges'])} gauges over {p['span_km']:.0f} km, {p['trees']:.0%} under trees"})
    if not added:
        print("No river added.", flush=True)
        return
    REGISTRY.write_text(json.dumps(reg, indent=1) + "\n")
    if rebuild():
        print("ADDED", ", ".join(added), flush=True)
        return
    # The build's checks failed: take the new rivers out again, so the dashboard stays as it was.
    reg["rivers"] = [r for r in reg["rivers"] if r["name"] not in added]
    REGISTRY.write_text(json.dumps(reg, indent=1) + "\n")
    for name in added:
        log({"lid": "", "name": name, "decision": "removed", "why": "the dashboard build's checks failed with it"})
    rebuild()
    raise SystemExit("the dashboard build failed with the new rivers; they were taken out again")


if __name__ == "__main__":
    main()
