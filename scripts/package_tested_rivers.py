"""Tested rivers for Run it yourself: the held-out passes that were tested with method v4, packed so the browser can
rerun the published test.

    python scripts/package_tested_rivers.py

For each pass below, this rebuilds the published test's inputs exactly as ``frozen_v4.evaluate_v4`` built them (the
same site grid, cached scenes, median baseline, heights, land cover, gauge timing and gauge-and-lidar estimate), checks
that method v4 on them gives the same map as the stored frozen layers and the same score as the published metrics, and
writes app/data/live/tested_<river>_<pass>/ (case.json and pack.bin.gz, in the live cases' format) plus
app/data/live/tested.json, the list the page adds to its own.

It only reads: nothing in outputs/ or research/ is written, no frozen run is repeated, and the published score shown is
the frozen one. Pine Island and Village Creek are left out because their held-out tests used method v3, which the browser
doesn't run; passes the test judged to have too little flooding are left out because they have no score to reproduce.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import numpy as np

from hidden_floods.audit import truth_context
from hidden_floods.config import REPO_ROOT, data_root, load_site
from hidden_floods.frozen_v4 import RECEIPT, rule_from
from hidden_floods.io.dem import dem_on_grid
from hidden_floods.io.gauges import usgs_series
from hidden_floods.live import Prepared, corners_lonlat, decode_pack, write_pack
from hidden_floods.metrics import score
from hidden_floods.pipeline import analysis_grid
from hidden_floods.selfcal import height_above_river
from hidden_floods.stack import Scene, read_scene
from hidden_floods.trust import timing_class, worldcover_class, worldcover_on_grid
from hidden_floods.v4 import median_baseline

LIVE = REPO_ROOT / "app" / "data" / "live"
RIVERS = json.loads((REPO_ROOT / "app" / "data" / "dashboard" / "rivers.json").read_text(encoding="utf-8"))["rivers"]

# The held-out v4 passes with a score: the October overbank test and the July first v4 test (research/V4_PROTOCOL.md,
# research/OVERBANK_PROTOCOL.md).
OVERBANK = json.loads((REPO_ROOT / "research" / "overbank_scenes.json").read_text())
V4_TEST = json.loads((REPO_ROOT / "research" / "v4_test_scenes.json").read_text())
PASSES = [("satilla", "047A_oct15", "overbank"), ("satilla", "098D_oct19", "overbank"), ("st_marys", "098D_oct07", "overbank"),
          ("ochlockonee", "026D_oct14", "overbank"), ("pee_dee", "098D_jul27", "v4"), ("neuse", "090A_jul26", "v4"),
          ("lower_sabine", "134A_jul17", "v4")]
TEST_NAME = {"overbank": "method 4, October", "v4": "method 4, July"}


def scenes_for(river: str, pair: str, which: str) -> list[Scene]:
    listing = OVERBANK[river]["passes"][pair]["scenes"] if which == "overbank" else V4_TEST[river]["scenes"]
    return [Scene(**s) for s in listing]


def package(river: str, pair_name: str, which: str) -> dict:
    site = load_site(river)
    pair = site.pairs[pair_name]
    out = REPO_ROOT / "outputs" / river / pair_name
    metrics = json.loads((out / "frozen_v4_metrics.json").read_text())
    stored = np.load(out / "frozen_v4_layers.npz")
    rule = rule_from(json.loads(RECEIPT.read_text()))

    # The published test's inputs, step for step (frozen_v4.evaluate_v4).
    grid = analysis_grid(site)
    dem = dem_on_grid(site.dem_path, grid)
    ctx = truth_context(site, pair.wet_time, dem=dem, grid=grid)
    t = ctx.truth
    scenes = scenes_for(river, pair_name, which)
    by_name = {s.name: s for s in scenes}
    wet = read_scene(site, grid, by_name[Path(site.gcov[pair.wet]).name])
    base_scenes = sorted((s for s in scenes if s.time[:10] != pair.wet_time[:10]), key=lambda s: s.time)
    stack = [read_scene(site, grid, s) for s in base_scenes]
    base = {"hh": median_baseline(np.stack([x["hh"] for x in stack])), "hv": median_baseline(np.stack([x["hv"] for x in stack]))}
    hand = height_above_river(dem, t.distance_m, t.chainage_m)
    lc = worldcover_class(worldcover_on_grid(data_root() / "worldcover", grid))
    classes = np.array([timing_class(usgs_series(site.gauges_dir, g), pair.wet_time) for g in site.gauges], np.uint8)
    timing = classes[np.argmin(np.abs(t.chainage_m[..., None] - np.asarray(ctx.gauge_chainage_m)), axis=-1)]
    region = ctx.supported & ~ctx.permanent_water

    # The same map and score as published, or nothing is written.
    v4 = rule.apply(wet["hh"] - base["hh"], wet["hv"] - base["hv"], lc, timing, hand, t.distance_m)
    if not np.array_equal(v4["pred"], stored["pred"]) or not np.array_equal(region, stored["region"]):
        raise RuntimeError(f"{river}/{pair_name}: rebuilt inputs don't give the stored frozen map")
    s = score(v4["pred"], t.wet, t.dry, region & v4["mapped"])
    published = metrics["primary_v4"]
    if abs((s.csi or 0) - (published["scores"]["csi"] or 0)) > 1e-9:
        raise RuntimeError(f"{river}/{pair_name}: score {s.csi} isn't the published {published['scores']['csi']}")

    case_id = f"tested_{river}_{pair_name}"
    folder = LIVE / case_id
    p = Prepared(case_id, "us", grid, wet, base, stack[-1], hand.astype(np.float32), t.distance_m.astype(np.float32), lc, timing,
                 ctx.permanent_water, {"wet": t.wet, "dry": t.dry, "region": region})
    layout = write_pack(p, folder)
    # Python's run on the rounded arrays the browser reads, for checking the browser's run (scripts/check_live_method.cjs).
    d = decode_pack(folder, layout)
    ref = rule.apply(d["wet_hh"] - d["median_hh"], d["wet_hv"] - d["median_hv"], d["landcover"], d["timing"], d["hand"], d["dist"])
    raw = (folder / "pack.bin").read_bytes()
    (folder / "pack.bin.gz").write_bytes(gzip.compress(raw, 9))
    (folder / "pack.bin").unlink()

    river_info = next(r for r in RIVERS if r["id"] == river)
    place = river_info["title"]
    g0 = site.gauges[0]
    area = grid.pixel_area_ha
    rec = {
        "id": case_id, "kind": "us", "tested": "held-out", "site": river, "pair": pair_name,
        "name": place, "place": place, "category": "tested",
        "lat": g0.lat, "lon": g0.lon,
        "wet": {"time": pair.wet_time, "name": Path(site.gcov[pair.wet]).name},
        "baseline": [{"time": x.time, "name": x.name} for x in base_scenes],
        "corners": corners_lonlat(grid), "pixel_ha": area, "layout": layout,
        "inputs": {"epsg": grid.crs, "heights": "3DEP lidar (bare earth)", "river": "the river's centre line, as in the published test",
                   "gauges": [{"usgs": g.id.replace("USGS-", ""), "name": g.name} for g in site.gauges],
                   "test": TEST_NAME[which], "protocol": "research/OVERBANK_PROTOCOL.md" if which == "overbank" else "research/V4_PROTOCOL.md"},
        "rule": {"type": "v4", "baseline": "median", "signal": "adaptive", "flood_check_db": None, "confidence_db": rule.confidence_db,
                 "wet_scene_db": rule.wet_scene_db, "smooth_px": rule.smooth_px, "hand_max_m": rule.hand_max_m, "valley_m": rule.valley_m,
                 "min_threshold_db": rule.min_threshold_db, "landcover": list(rule.landcover), "abstain_timing": list(rule.abstain_timing)},
        "frozen_run": {"threshold_db": metrics["v4_threshold_db"], "used_hh_minus_hv": metrics["used_hh_minus_hv"], "confident": metrics["confident"],
                       "low_minus_high_db": metrics["low_minus_high_db"], "flagged_ha": float(v4["pred"].sum() * area), "mapped_ha": float(v4["mapped"].sum() * area)},
        "reference_run": {"threshold_db": ref["threshold_db"], "flagged_px": int(ref["pred"].sum()), "flagged_land_px": int((ref["pred"] & ~d["water"].astype(bool)).sum()),
                          "used_hh_minus_hv": bool(ref["used_hh_minus_hv"]), "confident": bool(ref["confident"]), "low_minus_high_db": ref["low_minus_high_db"]},
        "score": {"scores": published["scores"], "ci95": published["ci95"]},
    }
    (folder / "case.json").write_text(json.dumps(rec, indent=1, default=float), encoding="utf-8")
    print(f"{case_id}: {layout['width']}x{layout['height']}, score {published['scores']['csi']:.3f}, pack {(folder / 'pack.bin.gz').stat().st_size / 1e6:.1f} MB", flush=True)
    return {"id": case_id, "kind": "us", "tested": "held-out", "place": place, "name": place, "category": "tested", "wet": pair.wet_time,
            "scored": True, "lat": g0.lat, "lon": g0.lon, "pack": "gz", "site": river}


def write_roads(river: str, pair_name: str) -> None:
    """roads.bin in the live cases' format (scripts/build_live_roads.py), from the OpenStreetMap ways already saved for the
    river's dashboard roads (scripts/build_roads.py), so no network is needed."""
    from build_roads import MAJOR, SKIP, osm_path   # scripts/ is on the path when this runs as a script

    osm = json.loads(osm_path(river).read_text(encoding="utf-8"))
    lines, major = [], []
    for el in osm.get("elements", []):
        tags = el.get("tags", {})
        hw = tags.get("highway", "")
        if el.get("type") != "way" or "geometry" not in el or not hw or hw in SKIP or tags.get("bridge") not in (None, "no"):
            continue
        lines.append([[p["lon"], p["lat"]] for p in el["geometry"]])
        major.append(hw in MAJOR)
    with open(LIVE / f"tested_{river}_{pair_name}" / "roads.bin", "wb") as f:
        f.write(np.int32(len(lines)).tobytes())
        f.write(np.cumsum([0] + [len(ln) for ln in lines]).astype(np.int32).tobytes())
        f.write(np.array(major, np.uint8).tobytes())
        f.write(bytes(-len(lines) % 4))
        f.write(np.array([pt for ln in lines for pt in ln], np.float32).tobytes())
    print(f"tested_{river}_{pair_name}: {len(lines):,} roads", flush=True)


if __name__ == "__main__":
    import sys

    if "--roads-only" not in sys.argv:
        cases = [package(*p) for p in PASSES]
        (LIVE / "tested.json").write_text(json.dumps({"about": "Held-out tested rivers, packed by scripts/package_tested_rivers.py", "cases": cases}, indent=1), encoding="utf-8")
        print(f"TESTED RIVERS PACKED ({len(cases)})")
    for river, pair_name, _ in PASSES:
        write_roads(river, pair_name)
