"""Data for the dashboard page: per-river estimator packs, gauge histories, NISAR layers and case records.

    python scripts/build_dashboard.py

Needs app/data/manifest.json from scripts/build_app.py, which also calls this. Reads no new radar. Each river's corridor is written to
app/data/dashboard/<river>.bin as parallel arrays: Int32 pixel index in the crop, Float32 ground height (m, NAVD88), Float32 distance along
the valley (m), and Uint8 flags (see FLAG in app/estimator.js). scripts/build_roads.py then lays the roads on those pixels, and
scripts/check_estimator.cjs checks the browser estimate against Python.
"""

import json
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
from build_app import (
    COLORS,
    DATA,
    HERO_GFM_DATE,
    corners,
    gauge_name,
    gauge_rows,
    gauges_json,
    overlay,
    to_web,
    web_grid,
)
from build_roads import main as build_roads
from pyproj import Transformer

from hidden_floods.audit import truth_context
from hidden_floods.config import REPO_ROOT, data_root, load_site
from hidden_floods.drivers import DriverInputs, summarize
from hidden_floods.frozen_v4 import RECEIPT as V4_RECEIPT
from hidden_floods.frozen_v4 import rule_from as v4_rule_from
from hidden_floods.grid import Grid
from hidden_floods.io.dem import dem_on_grid
from hidden_floods.io.operational import gfm_mosaic
from hidden_floods.live import decode_pack
from hidden_floods.pipeline import analysis_grid
from hidden_floods.series import yellow_series_site
from hidden_floods.trust import worldcover_class, worldcover_on_grid

OUT = DATA / "dashboard"
FT = 0.3048
CASES = {  # river -> case title, what the record is, GFM date for the static mask
    "satilla": {"title": "Satilla River, GA", "event": "October 2026 flood", "role": "held-out", "gfm": HERO_GFM_DATE},
    "st_johns": {"title": "St. Johns River, FL", "event": "autumn 2026 flood", "role": "sealed", "gfm": None},
    "st_marys": {"title": "St Marys River, GA/FL", "event": "October 2026 flood", "role": "held-out", "gfm": "20261017"},
    "ochlockonee": {"title": "Ochlockonee River, GA/FL", "event": "October 2026 flood", "role": "held-out", "gfm": "20261017"},
    "alapaha": {"title": "Alapaha River, GA", "event": "October 2026 flood", "role": "held-out", "gfm": "20261017"},
    "withlacoochee": {"title": "Withlacoochee River, GA", "event": "October 2026 flood", "role": "held-out", "gfm": "20261017"},
    "yellow": {"title": "Yellow River, FL", "event": "Hurricane Isaias", "role": "development", "gfm": "20261022"},
    "choctawhatchee": {"title": "Choctawhatchee River, FL", "event": "Hurricane Isaias", "role": "development", "gfm": "20261022"},
    "pearl": {"title": "Pearl River, LA/MS", "event": "Tropical Storm Arthur", "role": "development", "gfm": "20260628"},
    "tangipahoa": {"title": "Tangipahoa River, LA", "event": "Tropical Storm Arthur", "role": "development", "gfm": "20260628"},
    "lower_sabine": {"title": "Lower Sabine River, TX/LA", "event": "July 2026 flood", "role": "held-out", "gfm": "20260715"},
    "pine_island": {"title": "Pine Island Bayou, TX", "event": "Tropical Storm Edouard", "role": "held-out", "gfm": "20260906"},
    "village_creek": {"title": "Village Creek, TX", "event": "Tropical Storm Edouard", "role": "held-out", "gfm": "20260906"},
    "neuse": {"title": "Neuse River, NC", "event": "July 2026 flood", "role": "held-out", "gfm": "20260727"},
    "pee_dee": {"title": "Pee Dee River, SC", "event": "July 2026 flood", "role": "held-out", "gfm": "20260727"},
}
# The sealed test's river (scripts/setup_st_johns.py): no frozen run, so its one NISAR pass is Run it yourself's case,
# whose map covers only the 24 km box around one gauge.
LIVE_PASSES = {"st_johns": ("us_astf1_20261031", "the 24 km box around Astor")}
# Rivers whose passes come from their one-time frozen runs (outputs/<river>/<pass>/), not from the development build.
# Rivers added automatically (scripts/auto_rivers.py): not tested, listed after the others.
AUTO_REGISTRY = REPO_ROOT / "sites" / "auto_rivers.json"
AUTO = {r["name"]: r for r in (json.loads(AUTO_REGISTRY.read_text())["rivers"] if AUTO_REGISTRY.exists() else [])}
CASES |= {name: {"title": r["title"], "event": r["event"], "role": "auto", "gfm": None} for name, r in AUTO.items()}
FROM_FROZEN = ("satilla", "st_marys", "ochlockonee", "alapaha", "withlacoochee", "lower_sabine", "pine_island", "village_creek", "neuse", "pee_dee")


# Frozen passes with enough estimated flooding to judge, including the failures. Human notes repeat what the protocols recorded before each run.
HELD_OUT = {
    "satilla": {"title": "Satilla River, GA", "test": "latest test", "passes": {"047A_oct15": "Oct 15, 2026", "098D_oct19": "Oct 19, 2026"}, "human": None},
    "ochlockonee": {"title": "Ochlockonee River, GA/FL", "test": "latest test", "passes": {"026D_oct14": "Oct 14, 2026"}, "human": "Lake Talquin's dam sits on this river. Its lower gauge was left out because a straight water surface can't span the dam. How much the dam shaped this flood wasn't checked."},
    "st_marys": {"title": "St Marys River, GA/FL", "test": "latest test", "passes": {"098D_oct07": "Oct 7, 2026"}, "human": None},
    "pee_dee": {"title": "Pee Dee River, SC", "test": "first v4 test", "passes": {"098D_jul27": "Jul 27, 2026"}, "human": "Dams upstream affect this river's flow. How much they shaped this rise wasn't checked."},
    "neuse": {"title": "Neuse River, NC", "test": "first v4 test", "passes": {"090A_jul26": "Jul 26, 2026"}, "human": "Farmland makes up much of this valley: 36% of the corridor is crop, grass or shrub, which the method never maps. Dams and levees weren't checked."},
    "lower_sabine": {"title": "Lower Sabine River, TX/LA", "test": "first v4 test", "passes": {"134A_jul17": "Jul 17, 2026"}, "human": "Toledo Bend reservoir sits upstream and affects flow. How much it shaped this rise wasn't checked."},
}
DEFAULT_HUMAN = "Not checked here. Dam releases and levees could shift when and where water spreads."
RAINY_24H, RAINY_72H, BRIGHT_DB = 5.0, 25.0, 0.5


def rain_status(rainy, brightened):
    """The rule in research/RAINFALL.md."""
    return "Likely contributor" if rainy and brightened else "Possible" if rainy or brightened else "Little sign"


def held_out_drivers():
    """Physical drivers on every judged v4 frozen pass, from the saved layers of each one-time run. Reads no radar."""
    research = REPO_ROOT / "research"
    imerg = {(r["river"], r["pair"]): r for r in json.loads((research / "rainfall_imerg.json").read_text())["passes"]}
    overbank_rain = json.loads((research / "overbank_rain.json").read_text())
    out = []
    for river, spec in HELD_OUT.items():
        site = load_site(river)
        pairs = []
        for pair_name, label in spec["passes"].items():
            pair = site.pairs[pair_name]
            folder = REPO_ROOT / "outputs" / river / pair_name
            z = np.load(folder / "frozen_v4_layers.npz")
            run = json.loads((folder / "frozen_v4_metrics.json").read_text())
            t = truth_context(site, pair.wet_time).truth
            d_hh, d_hv = z["d_hh"], z["d_hv"]
            gauges = gauge_rows(site, pair)
            rises = [g["rise_m"] for g in gauges if g["rise_m"] is not None]
            drivers = summarize(DriverInputs(z["pred"], z["wet"], z["dry"], z["depth"], d_hh, d_hv, z["landcover"], z["hand"], t.distance_m, np.isfinite(d_hh) & np.isfinite(d_hv), z["region"] & t.corridor,
                                             run["v4_threshold_db"], max(rises) if rises else None, signal=d_hh - d_hv if run["used_hh_minus_hv"] else d_hh))
            high = run["high_ground_db"]
            brightened = high is not None and high > BRIGHT_DB
            if (river, pair_name) in imerg:
                r = imerg[(river, pair_name)]
                rain = {"rain_24h_mm": r["rain_24h_mm"], "rain_72h_mm": r["rain_72h_mm"], "usgs_gauges": r["usgs_gauges"]}
                drivers["status"]["ponding"] = r["status"]
            else:
                r = overbank_rain[river][pair_name]
                rain = {"rain_24h_mm": r["rain_24h_mm"], "rain_72h_mm": r["rain_72h_mm"], "usgs_gauges": []}
                drivers["status"]["ponding"] = rain_status(r["rainy"], brightened)
            drivers["rain"] = {**rain, "high_ground_db": high}
            drivers["gauges"] = gauges
            drivers["human_note"] = spec["human"] or DEFAULT_HUMAN
            if spec["human"]:
                drivers["status"]["human"] = "Possible"
            pairs.append({"id": pair_name, "label": f"{label} ({spec['test']})", "time": pair.wet_time, "dry_time": pair.dry_time, "csi": run["primary_v4"]["scores"]["csi"], "used_hh_minus_hv": run["used_hh_minus_hv"], "drivers": drivers})
        (OUT / f"{river}_gauges.json").write_text(json.dumps(gauges_json(site, [p["time"] for p in pairs])))
        out.append({"id": river, "title": f"{spec['title']} (held out)", "gauges": f"dashboard/{river}_gauges.json", "pairs": pairs})
        print("drivers", river, [(p["id"], p["drivers"]["status"]) for p in pairs], flush=True)
    (OUT / "heldout.json").write_text(json.dumps({"rivers": out}, default=float))


def flood_levels():
    """NWS flood level in feet of gauge stage, by gauge ID, since the dashboard compares stage.

    First the levels recorded with each pass, then the NWS minor flood stages each river saved
    (<data root>/<river>/nws_flood_levels.json, from scripts/river_setup.py save_nws_levels), which already turn levels NWS
    lists as elevations into gage height with the gauge's own datum. Last the overbank screen's levels."""
    out = {}
    for row in json.loads((REPO_ROOT / "research" / "flood_stage_by_pass.json").read_text()):
        for g in row["gauges"]:
            if g.get("flood_stage_ft"):
                out[g["id"]] = g["flood_stage_ft"]
    for path in sorted(data_root().glob("*/nws_flood_levels.json")):
        for gid, ft in json.loads(path.read_text())["levels"].items():
            out.setdefault(gid, float(ft))
    screen = json.loads((REPO_ROOT / "research" / "overbank_screen.json").read_text())
    for basin in screen.values():
        for g in basin["gauges"]:
            flood, datum = g.get("flood_m"), float(g.get("datum_ft") or 0) * FT
            if not flood or flood <= 0:
                continue
            # Some levels were recorded as heights above sea level rather than gauge readings: above a datum over 1 m they
            # can't be a reading, so the gauge's datum is taken off, in whichever datum (NAVD88 or NGVD29) USGS lists it.
            # Below 1 m the screen can't tell the two apart; those gauges' levels come from the NWS files above.
            if datum > 1 and flood > datum:
                flood -= datum
            out.setdefault(g["id"], flood / FT)
    return out


def gfm_on_or_near(ops, date, grid, corridor, days=3):
    """The GFM date for a river's static mask, and that date's mosaic: its case date if GFM saved scenes that day; if
    not, the nearest date within `days` whose scenes cover at least 90% of the corridor, as scripts/build_app.py
    pick_gfm_date does (failing that, the nearest with any scene). (None, empty mosaic) if there's none."""
    has = lambda d: any(Path(ops).glob(f"GFM_{d}T*_ensemble_flood_extent.tif"))
    if has(date):
        return date, gfm_mosaic(ops, date, grid)
    near = []
    for k in sorted(range(-days, days + 1), key=abs):
        d = f"{datetime.strptime(date, '%Y%m%d') + timedelta(days=k):%Y%m%d}"
        if k and has(d):
            near.append((d, gfm_mosaic(ops, d, grid)))
    for d, m in near:
        if m.covered[corridor].mean() >= 0.9:
            return d, m
    return near[0] if near else (None, gfm_mosaic(ops, date, grid))


def box_pass(name, flooded, box, time, scene, confident, where, score_type, **extra):
    """One NISAR pass whose map covers only a box (a Run it yourself case, or an automatically added river), drawn on
    the river's map. It carries "box", so the dashboard doesn't compare its area with the river's estimate. No score."""
    track = scene.split("_GCOV_")[1].split("_")
    pair = f"{track[1]}{track[2]}_{datetime.fromisoformat(time):%b%d}".lower()
    (DATA / name / pair).mkdir(parents=True, exist_ok=True)
    overlay(to_web(flooded.astype(np.uint8), box, web_grid(load_site(name)), True, 0) == 1, COLORS["nisar"], 225, DATA / name / pair / "nisar.png")
    return {"id": pair, "time": time, "layer": f"{name}/{pair}/nisar.png", "score": None, "score_type": score_type, "confident": bool(confident),
            "rainy": None, "lidar_score": None, "flagged_ha": float(flooded.sum() * box.res * box.res / 1e4), "static_ha": None, "box": where, **extra}


def live_case_pass(name, case_id, where):
    """A river's NISAR pass from a Run it yourself case: the frozen v4 rule rerun on the case's stored arrays, exactly as
    its reference run (scripts/live_cases.py). This river has no frozen test yet."""
    folder = DATA / "live" / case_id
    rec = json.loads((folder / "case.json").read_text())
    d = decode_pack(folder, rec["layout"])
    res = v4_rule_from(json.loads(V4_RECEIPT.read_text())).apply(d["wet_hh"] - d["median_hh"], d["wet_hv"] - d["median_hv"], d["landcover"], d["timing"], d["hand"], d["dist"])
    epsg, w, h = rec["inputs"]["epsg"], rec["layout"]["width"], rec["layout"]["height"]
    x0, y0 = Transformer.from_crs(4326, epsg, always_xy=True).transform(*rec["corners"][0])
    res_m = (rec["pixel_ha"] * 1e4) ** 0.5
    box = Grid(crs=epsg, x0=round(x0 / res_m) * res_m, y0=round(y0 / res_m) * res_m, res=res_m, width=w, height=h)
    return [box_pass(name, res["pred"] & (d["water"] == 0), box, rec["wet"]["time"], rec["wet"]["name"], res["confident"], where, "live", case=case_id)]


def auto_pass(entry):
    """An automatically added river's pass (scripts/auto_rivers.py), from the map it saved."""
    p = entry["pass"]
    flooded = np.load(data_root() / p["file"])["flooded"]
    return [box_pass(entry["name"], flooded, Grid(**p["grid"]), p["time"], p["scene"], p["confident"], p["where"], "auto")]


def frozen_passes(name, metrics, rain):
    """A held-out river's passes, each from its one-time run's saved layers (outputs/<river>/<pass>/frozen_*_layers.npz),
    with its NISAR map layer. The score, trust light and rain flag are the ones recorded by that run. Reads no radar."""
    site = load_site(name)
    grid, wg = analysis_grid(site), web_grid(site)
    dem = dem_on_grid(site.dem_path, grid)
    overbank = {r["pair"]: r for r in metrics["overbank"] if r["site"] == name}
    held = {r["pair"]: r for r in metrics["held_out"] if r["site"] == name}
    out = []
    for pair in sorted(set(overbank) | set(held)):
        folder = REPO_ROOT / "outputs" / name / pair
        z = np.load(folder / ("frozen_v4_layers.npz" if (folder / "frozen_v4_layers.npz").exists() else "frozen_edouard_layers.npz"))
        corridor = truth_context(site, site.pairs[pair].wet_time, dem=dem, grid=grid).truth.corridor
        region = z["region"] & corridor
        lidar = np.isin(z["landcover"], (0, 1, 2)) & (z["hand"] < 2.0)
        (DATA / name / pair).mkdir(parents=True, exist_ok=True)
        overlay(to_web((z["pred"] & corridor).astype(np.uint8), grid, wg, True, 0) == 1, COLORS["nisar"], 225, DATA / name / pair / "nisar.png")
        p = {"id": pair, "time": site.pairs[pair].wet_time, "layer": f"{name}/{pair}/nisar.png", "score_type": "frozen",
             "flagged_ha": float((z["pred"] & region).sum() * grid.pixel_area_ha), "static_ha": float((lidar & region).sum() * grid.pixel_area_ha)}
        if pair in overbank:       # the latest test: its own judgeability, trust light, rain flag and lidar-only score
            r = overbank[pair]
            p.update(score=r["csi"] if r["judgeable"] else None, confident=r["high"], rainy=r["rainy"], lidar_score=r["lidar_csi"] if r["judgeable"] else None)
        else:                      # earlier tests: the trust light came with method v4, so a v3 run has none
            p.update(score=held[pair]["csi"], rainy=rain.get((name, pair)), lidar_score=None)
            v4 = folder / "frozen_v4_metrics.json"
            if v4.exists():
                p["confident"] = json.loads(v4.read_text())["confident"]
        out.append(p)
    return out


def build_river(name, passes, times, levels):
    case = CASES[name]
    site = yellow_series_site() if name == "yellow" else load_site(name)
    grid = analysis_grid(site)
    dem = dem_on_grid(site.dem_path, grid)
    ctx = truth_context(site, times[0], dem=dem, grid=grid)
    t = ctx.truth
    corridor = t.corridor
    rows, cols = np.nonzero(corridor)
    r0, r1, c0, c1 = rows.min(), rows.max() + 1, cols.min(), cols.max() + 1
    crop_rows, crop_cols = int(r1 - r0), int(c1 - c0)
    lc = worldcover_class(worldcover_on_grid(data_root() / "worldcover", grid))
    ops = data_root() / name / "ops_audit" if name == "satilla" else site.operational_dir
    gfm_date, gfm = gfm_on_or_near(ops, case["gfm"], grid, corridor) if case["gfm"] else (None, gfm_mosaic(ops, "00000000", grid))
    flags = (ctx.permanent_water.astype(np.uint8) | (ctx.supported.astype(np.uint8) << 1) | (lc.astype(np.uint8) << 2)
             | (gfm.excluded.astype(np.uint8) << 4) | (gfm.covered.astype(np.uint8) << 5))
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / f"{name}.bin", "wb") as f:
        f.write(((rows - r0) * crop_cols + (cols - c0)).astype(np.int32).tobytes())
        f.write(dem[corridor].astype(np.float32).tobytes())
        f.write(t.chainage_m[corridor].astype(np.float32).tobytes())
        f.write(flags[corridor].astype(np.uint8).tobytes())
    x0, y0, res = grid.x0 + c0 * grid.res, grid.y0 - r0 * grid.res, grid.res
    lonlat = lambda x, y: [float(v) for v in grid.to_lonlat(x, y)]
    quad = [lonlat(x0, y0), lonlat(x0 + crop_cols * res, y0), lonlat(x0 + crop_cols * res, y0 - crop_rows * res), lonlat(x0, y0 - crop_rows * res)]

    chain, ground = t.chainage_m[corridor] / 1000.0, dem[corridor]
    profile = []
    for k in np.arange(np.floor(chain.min()), chain.max(), 2.0):
        m = (chain >= k) & (chain < k + 2)
        if m.sum() > 20:
            profile.append({"km": float(k + 1), "low_m": round(float(np.percentile(ground[m], 5)), 2), "typical_m": round(float(np.percentile(ground[m], 50)), 2)})

    gauges = []
    for g, gc in zip(site.gauges, ctx.gauge_chainage_m, strict=True):
        gid = g.id.replace("USGS-", "")
        gauges.append({"id": gid, "name": gauge_name(g.name), "lon": g.lon, "lat": g.lat, "chain_m": float(gc), "datum_ft": float(g.datum_ft), "navd88_offset_ft": float(g.navd88_offset_ft), "flood_ft": levels.get(gid)})
    checks = []
    for when in times:
        c = truth_context(site, when, dem=dem, grid=grid)
        checks.append({"time": when, "wse_m": [c.gauge_wse_m[g.name] for g in site.gauges], "estimated_ha": float((c.truth.wet & c.supported & ~c.permanent_water).sum() * grid.pixel_area_ha)})
    wg = web_grid(site)
    lons, lats = zip(*site.valley_line)
    (OUT / f"{name}_gauges.json").write_text(json.dumps(gauges_json(site, times)))
    entry = {"id": name, **{k: case[k] for k in ("title", "event", "role")}, "gfm_date": gfm_date, "bounds": [min(lons) - 0.04, min(lats) - 0.08, max(lons) + 0.04, max(lats) + 0.08], "corners": corners(wg), "gauges": gauges, "profile": profile, "passes": passes, "checks": checks,
             "grid": {"rows": crop_rows, "cols": crop_cols, "pixels": int(corridor.sum()), "quad": quad, "pixel_ha": grid.pixel_area_ha, "margin_m": site.margin_m}}
    print(name, entry["grid"]["pixels"], "pixels", [g["flood_ft"] for g in gauges], "GFM", gfm_date, f"covers {gfm.covered[corridor].mean():.0%}", flush=True)
    return entry


def main():
    manifest = json.loads((DATA / "manifest.json").read_text())
    metrics = json.loads((DATA / "metrics.json").read_text())
    levels = flood_levels()
    # The trust light (app/shared.js) needs the frozen rain flag: research/RAINFALL.md, as fixed in OVERBANK_PROTOCOL.md section 4.
    rain = {(r["river"], r["pair"]): r["rainy"] for r in json.loads((REPO_ROOT / "research" / "rainfall_imerg.json").read_text())["passes"]}
    rivers = []
    for name in CASES:
        if name in AUTO:
            passes, gfm_layer = auto_pass(AUTO[name]), None
        elif name in LIVE_PASSES:
            passes, gfm_layer = live_case_pass(name, *LIVE_PASSES[name]), None
        elif name in FROM_FROZEN:
            passes = frozen_passes(name, metrics, rain)
            gfm_layer = f"satilla/{manifest['hero']['pass']}/gfm_excl.png" if name == "satilla" else None
        else:
            s = next(x for x in manifest["sites"] if x["id"] == name)
            passes = [{"id": p["id"], "time": p["time"], "layer": f"{name}/{p['id']}/{p['layers']['nisar']}", "score": p["score"]["csi"] if p["score"]["scorable"] else None, "score_type": "development", "confident": p["confident"],
                       "rainy": rain[(name, p["id"])], "lidar_score": p["frame"]["static_csi"], "flagged_ha": p["frame"]["flagged_ha"], "static_ha": p["frame"]["static_ha"]} for p in s["pairs"]]
            gfm_layer = next((f"{name}/{p['id']}/{p['layers']['gfm_excl']}" for p in s["pairs"] if "gfm_excl" in p["layers"]), None)
        passes.sort(key=lambda p: p["time"])
        entry = build_river(name, passes, [p["time"] for p in passes], levels)
        entry["gfm_layer"] = gfm_layer
        rivers.append(entry)
    held = {}
    for r in metrics["held_out"]:      # each river's first listed pass is its primary one
        held.setdefault(r["site"], r)
    audit = {}
    for r in metrics["audit"]:
        if r["truth_wet_ha"] >= 100 and (r["site"] not in audit or r["truth_wet_ha"] > audit[r["site"]]["estimated_ha"]):
            audit[r["site"]] = {"date": r["date"], "estimated_ha": r["truth_wet_ha"], "gfm_ha": r["gfm_on_wet_ha"], "mask_share": r["wet_share_in_mask"], "tree_share": r["tree_share"]}
    a = metrics["satilla_audit"]
    audit["satilla"] = {"date": a["date"], "estimated_ha": a["estimated_ha"], "gfm_ha": a["gfm_on_wet_ha"], "mask_share": a["wet_share_in_mask"], "tree_share": a["tree_share"]}
    for r in rivers:
        r["audit"] = audit.get(r["id"])
        h = held.get(r["id"])
        r["frozen"] = {"method": h["method"], "pair": h["pair"], "csi": h.get("csi")} if h else None
    (OUT / "rivers.json").write_text(json.dumps({"rivers": rivers}, allow_nan=False))
    build_roads()   # the road files follow the .bin pixel order, so they're rebuilt with it
    held_out_drivers()
    run = subprocess.run(["node", str(REPO_ROOT / "scripts" / "check_estimator.cjs")], check=False, capture_output=True, text=True)
    print(run.stdout, run.stderr, flush=True)
    if run.returncode:
        raise SystemExit("the browser estimate differs from the Python estimate")
    print("DASHBOARD DATA DONE", round(sum(p.stat().st_size for p in OUT.iterdir()) / 1e6, 1), "MB", flush=True)


if __name__ == "__main__":
    main()
