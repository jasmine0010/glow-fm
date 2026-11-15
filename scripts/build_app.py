"""Build the static web app's data: map overlays (Web Mercator PNGs), hydrographs, metrics.

    python scripts/build_app.py

Everything is written to app/data/ so the app runs from any static host (GitHub Pages) with no server. Only layers a page
reads are written: every pass's NISAR map (the dashboard); the radar change, river's answer and not-mapped layers on the
Yellow River timeline (the story page); the river's answer on the C-band panel's Pearl pass; and one official-map mask
per river (the dashboard).
The NISAR flood layer is frozen method v4. The explorer rivers helped build it, so their scores are development numbers,
and the app says so. The first screen uses the Satilla, a held-out river, built from the one-time run's saved layers.
Value 255 in R means no data.
"""

import json
import shutil
from datetime import datetime, timedelta

import numpy as np
from fetch_stacks import LOCAL, scenes_for
from PIL import Image
from rasterio.warp import Resampling, reproject

from hidden_floods.audit import scene_time, truth_context
from hidden_floods.config import REPO_ROOT, data_root, load_site
from hidden_floods.detect import pair_features
from hidden_floods.drivers import DriverInputs, summarize
from hidden_floods.frozen_v2 import RECEIPT_V2
from hidden_floods.frozen_v3 import RECEIPT_V3, settings_from
from hidden_floods.frozen_v4 import RECEIPT as RECEIPT_V4
from hidden_floods.frozen_v4 import rule_from
from hidden_floods.grid import Grid, grid_from_lonlat_bbox
from hidden_floods.io.dem import dem_on_grid
from hidden_floods.io.gauges import usgs_series
from hidden_floods.io.nisar import read_gcov
from hidden_floods.io.operational import gfm_mosaic
from hidden_floods.metrics import block_bootstrap, block_ids, score
from hidden_floods.pipeline import analysis_grid
from hidden_floods.selfcal import SelfCalRule, height_above_river, smooth_nan
from hidden_floods.series import FROZEN_FRAME, yellow_series_site
from hidden_floods.stack import read_scene
from hidden_floods.trust import LANDCOVER, TIMING, evaluate_pair, timing_class
from hidden_floods.v3 import score_v3
from hidden_floods.v4 import median_baseline

APP = REPO_ROOT / "app"
DATA = APP / "data"
SITES = {
    "choctawhatchee": {"title": "Choctawhatchee River, FL (Hurricane Isaias)", "role": "v4 development river",
                       "pairs": {"076A_oct17": "Oct 17, 2026 (crest at Bruce)", "127D_oct21": "Oct 21, 2026 (receding)"}},
    "pearl": {"title": "Pearl River, LA/MS (Tropical Storm Arthur)", "role": "v4 development river (held out for v1)",
              "pairs": {"105A_jul03": "Jul 3, 2026 (near crest upstream)", "156D_jun25": "Jun 25, 2026"}},
    "tangipahoa": {"title": "Tangipahoa River, LA (Tropical Storm Arthur)", "role": "v4 development river (held out for v2)",
                   "pairs": {"105A_jun21": "Jun 21, 2026 (falling limb)", "156D_jun25": "Jun 25, 2026 (late)"}},
    "yellow": {"title": "Yellow River, FL (Hurricane Isaias)", "role": "v4 development river (held out for v3)",
               "pairs": {"055D_oct04": "Oct 4, 2026", "076A_oct05": "Oct 5, 2026", "127D_oct09": "Oct 9, 2026",
                         "055D_oct16": "Oct 16, 2026 (v3 frozen test)", "076A_oct17": "Oct 17, 2026", "127D_oct21": "Oct 21, 2026"}},
}
GFM_DATES = {"choctawhatchee": ["20261010", "20261022", "20261027"],
             "pearl": ["20260617", "20260622", "20260624", "20260628", "20260705"],
             "tangipahoa": ["20260621", "20260628"], "yellow": ["20261010", "20261022"]}
COLORS = {"nisar": (214, 58, 214), "gfm": (40, 110, 255), "excl": (90, 90, 90), "truth": (0, 200, 220),
          "dswx": (0, 160, 120), "not_mapped": (235, 235, 235)}
FT_TO_M = 0.3048
HERO_RIVER, HERO_PASS, HERO_GFM_DATE = "satilla", "047A_oct15", "20261024"


def web_grid(site) -> Grid:
    return grid_from_lonlat_bbox(site.bbox, "EPSG:3857", 50.0)


def to_web(arr, src: Grid, dst: Grid, categorical: bool, fill):
    out = np.full(dst.shape, fill, dtype=arr.dtype)
    reproject(arr, out, src_transform=src.transform, src_crs=src.crs, dst_transform=dst.transform, dst_crs=dst.crs,
              resampling=Resampling.nearest if categorical else Resampling.bilinear, src_nodata=fill, dst_nodata=fill)
    return out


def corners(g: Grid):
    w, n = g.to_lonlat(g.x0, g.y0)
    e, s = g.to_lonlat(g.x0 + g.width * g.res, g.y0 - g.height * g.res)
    return [[w, n], [e, n], [e, s], [w, s]]


def overlay(mask, rgb, alpha, path):
    img = np.zeros(mask.shape + (4,), np.uint8)
    img[mask, :3] = rgb
    img[mask, 3] = alpha
    Image.fromarray(img, "RGBA").save(path, optimize=True)


def pick_gfm_date(site, when, grid, corridor):
    """Covered GFM date nearest the NISAR pass (coverage of the corridor >= 90%)."""
    t = datetime.fromisoformat(when)
    best = None
    for d in GFM_DATES[site.name]:
        try:
            ts = scene_time(site.operational_dir, d)
        except FileNotFoundError:
            continue
        m = gfm_mosaic(site.operational_dir, d, grid)
        if m.covered[corridor].mean() < 0.9:
            continue
        dt = abs((datetime.fromisoformat(ts) - t).total_seconds())
        if best is None or dt < best[0]:
            best = (dt, d, ts, m)
    return best


def finite(x):
    """JSON has no NaN: a browser would refuse the whole manifest."""
    return float(x) if np.isfinite(x) else None


def gauge_name(name: str) -> str:
    return name.title().replace(" Nr ", " near ").replace(" At ", " at ").replace(", Fla.", ", FL") if name.isupper() else name


def change_image(change, wg, path):
    """Raw radar change: fades in from +1 dB to full strength at +4 dB."""
    strength = np.clip((np.nan_to_num(change, nan=-99.0) - 1.0) / 3.0, 0.0, 1.0)
    img = np.zeros(wg.shape + (4,), np.uint8)
    for k, (lo, hi) in enumerate(((214, 255), (58, 190), (214, 255))):
        img[..., k] = np.round(lo + (hi - lo) * strength).astype(np.uint8)
    img[..., 3] = np.round(235 * strength).astype(np.uint8)
    Image.fromarray(img, "RGBA").save(path, optimize=True)


def gauge_rows(site, pair):
    rows = []
    for g in site.gauges:
        s = usgs_series(site.gauges_dir, g)
        wet = s.at(pair.wet_time)
        try:
            dry = s.at(pair.dry_time)
        except ValueError:                       # dry reference outside this gauge's saved record
            dry = None
        t = np.datetime64(pair.wet_time.replace("Z", ""), "s")
        m = (s.times >= t - np.timedelta64(10, "D")) & (s.times <= t + np.timedelta64(3, "D"))
        crest = str(s.times[m][int(np.argmax(s.stage_ft[m]))])[:16]
        rows.append({"name": gauge_name(g.name), "rise_m": None if dry is None else round((wet - dry) * FT_TO_M, 2), "crest": crest,
                     "timing": TIMING[timing_class(s, pair.wet_time)]})
    return rows


def baseline_changes(site, grid, pair, hh_wet, hv_wet):
    """HH and HV change (dB) from the per-pixel median of other same-track scenes within 60 days."""
    scenes = [s for s in scenes_for(site, pair) if s.time[:10] != pair.wet_time[:10]]
    stack = [read_scene(site, grid, s, LOCAL) for s in scenes]
    return (hh_wet - median_baseline(np.stack([x["hh"] for x in stack])), hv_wet - median_baseline(np.stack([x["hv"] for x in stack])),
            [s.time[:10] for s in scenes])


BANDS_PAIR = ("pearl", "105A_jul03")   # the C-band panel's pass (scripts/c_band_check.py): it shows this pass's river's answer


def build_pair(site, pair_name, label, rule, v3_rule, v4_rule, out_dir, write_excl):
    ev = evaluate_pair(site, pair_name, rule, data_root() / "worldcover", SITES[site.name]["role"])
    pair = site.pairs[pair_name]
    f = pair_features(read_gcov(site.gcov_path(pair.dry), ev.grid), read_gcov(site.gcov_path(pair.wet), ev.grid))
    t = ev.ctx.truth
    corridor = t.corridor
    hand = height_above_river(dem_on_grid(site.dem_path, ev.grid), t.distance_m, t.chainage_m)
    v3_pred, v3_mapped, _ = v3_rule.apply(f, ev.landcover, ev.timing, hand, t.distance_m)
    d_hh, d_hv, baseline_dates = baseline_changes(site, ev.grid, pair, f.hh_wet, f.hv_wet)
    v4 = v4_rule.apply(d_hh, d_hv, ev.landcover, ev.timing, hand, t.distance_m)
    pred, mapped, thr = v4["pred"], v4["mapped"], v4["threshold_db"]
    reg = ev.ctx.supported & ~ev.ctx.permanent_water
    v4_score = score_v3(pred, mapped, t.wet, t.dry, reg)
    v3_csi = score_v3(v3_pred, v3_mapped, t.wet, t.dry, reg).csi
    g = pick_gfm_date(site, pair.wet_time, ev.grid, corridor)
    wg = web_grid(site)
    U8 = lambda a: a.astype(np.uint8)
    nisar = to_web(U8(pred & corridor), ev.grid, wg, True, 0) == 1
    not_mapped = to_web(U8(~mapped & corridor), ev.grid, wg, True, 0) == 1
    truth = to_web(U8(t.wet & ~ev.ctx.permanent_water), ev.grid, wg, True, 0) == 1
    timeline = site.name == "yellow"   # the story page's timeline shows radar change, the river's answer and unmapped ground
    want_truth = timeline or (site.name, pair_name) == BANDS_PAIR
    layers = {"nisar": "nisar.png"}
    if timeline:
        layers["dhh"] = "dhh.png"
        if not_mapped.any():
            layers["not_mapped"] = "not_mapped.png"
    if want_truth:
        layers["truth"] = "truth.png"
    meta = {"id": pair_name, "label": label, "time": pair.wet_time, "dry_time": pair.dry_time,
            "threshold_db": round(thr, 2), "frozen": site.name == "yellow" and pair_name == FROZEN_FRAME, "baseline_dates": baseline_dates,
            "confident": v4["confident"], "low_minus_high_db": finite(v4["low_minus_high_db"]) if v4["low_minus_high_db"] is not None else None,
            "used_hh_minus_hv": v4["used_hh_minus_hv"], "v3_csi": finite(v3_csi)}
    out_dir.mkdir(parents=True, exist_ok=True)
    overlay(nisar, COLORS["nisar"], 210, out_dir / "nisar.png")
    if timeline:
        if not_mapped.any():
            overlay(not_mapped, COLORS["not_mapped"], 70, out_dir / "not_mapped.png")
        # The raw radar signal, smoothed, on the timeline's colour scale.
        change_image(to_web(smooth_nan(d_hh, 3).astype(np.float32), ev.grid, wg, False, np.float32(np.nan)), wg, out_dir / "dhh.png")
    if want_truth:
        overlay(truth, COLORS["truth"], 150, out_dir / "truth.png")
    if g:
        _, d, ts, m = g
        if write_excl:   # the dashboard shows one official-map mask per river: the first pass that has one
            overlay(to_web(U8(m.excluded & corridor), ev.grid, wg, True, 0) == 1, COLORS["excl"], 110, out_dir / "gfm_excl.png")
            layers["gfm_excl"] = "gfm_excl.png"
        meta["gfm_date"], meta["gfm_time"] = d, ts
    a = ev.grid.pixel_area_ha
    scorable = bool((t.wet & reg & mapped).any())
    meta["score"] = {"csi": finite(v4_score.csi), "recall": finite(v4_score.recall), "precision": finite(v4_score.precision),
                     "coverage": finite(v4_score.coverage), "scorable": scorable}
    gauges = gauge_rows(site, pair)
    rises = [r["rise_m"] for r in gauges if r["rise_m"] is not None]
    valid = np.isfinite(d_hh) & np.isfinite(d_hv)
    meta["drivers"] = summarize(DriverInputs(pred, t.wet, t.dry, np.where(corridor, t.depth_m, np.nan), d_hh, d_hv,
                                             ev.landcover, hand, t.distance_m, valid, reg & corridor, thr,
                                             max(rises) if rises else None, signal=d_hh - d_hv if v4["used_hh_minus_hv"] else d_hh))
    scored = reg & mapped
    static = np.isin(ev.landcover, (0, 1, 2)) & (hand < 2.0)    # research/STATIC_BASELINE.md: same map on every date
    sw, sd = (static & t.wet & scored).sum(), (static & t.dry & scored).sum()
    sfn = (~static & t.wet & scored).sum()
    static_csi = float(sw / (sw + sfn + sd)) if sw + sfn + sd else None
    ci = block_bootstrap(pred, t.wet, t.dry, block_ids(t.chainage_m, 2000.0), scored, n_boot=2000, seed=0)["csi"] if scorable else None
    meta["frame"] = {"pair": pair_name, "time": pair.wet_time, "frozen": meta["frozen"], "confident": v4["confident"], "low_minus_high_db": meta["low_minus_high_db"],
                     "timing": [r["timing"] for r in gauges], "stage_rise_m": [r["rise_m"] for r in gauges], "flagged_ha": meta["drivers"]["flagged_ha"], "static_ha": float((static & reg & corridor).sum() * a), "static_csi": static_csi,
                     "confirmed_ha": float((t.wet & reg).sum() * a), "flagged_on_dry_ha": float((pred & t.dry & scored).sum() * a),
                     "csi": finite(v4_score.csi) if scorable else None, "csi_ci95": list(ci) if ci else None}
    meta["drivers"]["gauges"] = gauges
    meta["stats"] = {"nisar_flooded_ha": float((pred & corridor).sum() * a),
                     "truth_wet_ha": float((t.wet & reg).sum() * a),
                     "median_incidence_deg": float(np.nanmedian(ev.incidence[corridor]))}
    meta["layers"] = layers
    return meta, wg


def gauges_json(site, times):
    t0 = min(datetime.fromisoformat(x.replace("Z", "")) for x in times) - timedelta(days=12)
    t1 = max(datetime.fromisoformat(x.replace("Z", "")) for x in times) + timedelta(days=12)
    out = []
    for g in site.gauges:
        s = usgs_series(site.gauges_dir, g)
        m = (s.times >= np.datetime64(t0)) & (s.times <= np.datetime64(t1))
        tt, vv = s.times[m][::4], s.stage_ft[m][::4]  # hourly
        out.append({"name": gauge_name(g.name), "id": g.id, "times": [str(x)[:16] for x in tt], "stage_ft": [round(float(v), 2) for v in vv]})
    return out


def add_rain(manifest):
    """IMERG rainfall before each pass, and the rain status from research/RAINFALL.md, on each pass's drivers panel."""
    rows = {(r["river"], r["pair"]): r for r in json.loads((REPO_ROOT / "research" / "rainfall_imerg.json").read_text())["passes"]}
    for s in manifest["sites"]:
        for p in s["pairs"]:
            r = rows[(s["id"], p["id"])]
            p["drivers"]["status"]["ponding"] = r["status"]
            p["drivers"]["rain"] = {k: r[k] for k in ("rain_24h_mm", "rain_72h_mm", "high_ground_db", "usgs_gauges")}


def build_hero():
    """First-screen layers for the held-out Satilla pass, from the one-time run's saved layers and the GFM scene in research/SATILLA_AUDIT.md. Reads no radar."""
    site = load_site(HERO_RIVER)
    grid, wg = analysis_grid(site), web_grid(site)
    pair = site.pairs[HERO_PASS]
    ctx = truth_context(site, pair.wet_time)
    z = np.load(REPO_ROOT / "outputs" / HERO_RIVER / HERO_PASS / "frozen_v4_layers.npz")
    frozen = json.loads((REPO_ROOT / "research" / f"overbank_{HERO_RIVER}_{HERO_PASS}_frozen_metrics.json").read_text())
    check = score(z["pred"], z["wet"], z["dry"], z["region"] & z["mapped"]).csi
    if abs(check - frozen["v4_csi"]) > 1e-9:
        raise SystemExit(f"first-screen layers score {check}, frozen {frozen['v4_csi']}")
    corridor = ctx.truth.corridor
    gfm = gfm_mosaic(data_root() / HERO_RIVER / "ops_audit", HERO_GFM_DATE, grid)
    out = DATA / HERO_RIVER / HERO_PASS
    out.mkdir(parents=True, exist_ok=True)
    U8 = lambda a: a.astype(np.uint8)
    web = lambda a: to_web(U8(a), grid, wg, True, 0) == 1
    overlay(web(z["pred"] & corridor), COLORS["nisar"], 225, out / "nisar.png")
    overlay(web(z["wet"] & ~ctx.permanent_water), COLORS["truth"], 200, out / "truth.png")
    overlay(web(gfm.flood & gfm.covered & corridor), COLORS["gfm"], 235, out / "gfm.png")
    overlay(web(gfm.excluded & gfm.covered & corridor), COLORS["excl"], 170, out / "gfm_excl.png")
    overlay(web(~gfm.covered & corridor), (232, 214, 170), 110, out / "gfm_none.png")
    lons, lats = zip(*site.valley_line)
    return {"site": HERO_RIVER, "pass": HERO_PASS, "corners": corners(wg), "bounds": [min(lons) - 0.04, min(lats) - 0.08, max(lons) + 0.04, max(lats) + 0.08],
            "gauges": [{"name": gauge_name(g.name), "lon": g.lon, "lat": g.lat} for g in site.gauges], "time": pair.wet_time,
            "layers": {"nisar": "nisar.png", "truth": "truth.png", "gfm": "gfm.png", "gfm_excl": "gfm_excl.png", "gfm_none": "gfm_none.png"}}


def build_satilla_layers(pairs):
    """NISAR map layers for the dashboard's Satilla passes, from the one-time run's saved layers."""
    site = load_site(HERO_RIVER)
    grid, wg = analysis_grid(site), web_grid(site)
    for pair in pairs:
        out = DATA / HERO_RIVER / pair
        out.mkdir(parents=True, exist_ok=True)
        z = np.load(REPO_ROOT / "outputs" / HERO_RIVER / pair / "frozen_v4_layers.npz")
        corridor = truth_context(site, site.pairs[pair].wet_time).truth.corridor
        overlay(to_web((z["pred"] & corridor).astype(np.uint8), grid, wg, True, 0) == 1, COLORS["nisar"], 225, out / "nisar.png")


OVERBANK_PASSES = (("satilla", "047A_oct15"), ("satilla", "098D_oct19"), ("alapaha", "047A_oct15"), ("alapaha", "148A_oct22"), ("ochlockonee", "026D_oct14"),
                   ("withlacoochee", "047A_oct15"), ("withlacoochee", "148A_oct10"), ("st_marys", "098D_oct07"), ("st_marys", "047A_oct15"))


def metrics_json():
    root = REPO_ROOT / "outputs"
    audit = json.loads((root / "audit" / "blind_spot.json").read_text())
    yellow = root / "audit" / "yellow" / "audit.json"
    if yellow.exists():
        audit += json.loads(yellow.read_text())
    rows = []
    base = {(b["site"], b["date"]): b for b in json.loads((REPO_ROOT / "research" / "audit_base_rate.json").read_text())}
    stage = {(s["river"], s["pair"]): s["stage"] for s in json.loads((REPO_ROOT / "research" / "flood_stage_by_pass.json").read_text())}
    for r in audit:
        gm = r["gfm"]
        if not gm.get("truth_wet_ha"):
            continue
        b = base.get((r["site"], r["date"]))
        rows.append({"site": r["site"], "date": r["date"], "truth_wet_ha": gm["truth_wet_ha"], "gfm_on_wet_ha": b and b["gfm_on_wet_ha"],
                     "corridor_share_in_mask": b and b["corridor_share_in_mask"], "dry_share_in_mask": b and b["dry_share_in_mask"], "wet_share_in_mask": b and b["wet_share_in_mask"],
                     "wet_outside_mask_ha": b and b["wet_outside_mask_ha"], "gfm_outside_mask_ha": b and b["gfm_on_wet_outside_mask_ha"], "tree_share": b and b["land_cover_wet"]["tree"],
                     "gfm_share": gm.get("share_mapped"), "gfm_excluded_share": gm.get("share_inside_exclusion_mask"),
                     "dswx_share": r.get("dswx_s1", {}).get("share_mapped"),
                     "roads_km": r.get("exposure_unmapped_by_gfm", {}).get("road_km")})
    held = []
    for site, pair, f, key, label in (
            ("pearl", "105A_jul03", "frozen_metrics.json", None, "v1, fixed 2 dB (frozen)"),
            ("pearl", "156D_jun25", "frozen_metrics.json", None, "v1, fixed 2 dB (frozen)"),
            ("tangipahoa", "105A_jun21", "frozen_v2_metrics.json", "primary_v2_gauge_supported", "v2, self-calibrating (frozen)"),
            ("tangipahoa", "156D_jun25", "frozen_v2_metrics.json", "primary_v2_gauge_supported", "v2, self-calibrating (frozen)")):
        d = json.loads((root / site / pair / f).read_text())
        b = d[key] if key else d
        held.append({"site": site, "pair": pair, "method": label, "csi": b["scores"]["csi"], "ci95": b["ci95"]["csi"],
                     "recall": b["scores"]["recall"], "precision": b["scores"]["precision"], "estimated_ha": b["scores"]["tp_ha"] + b["scores"]["fn_ha"]})
    research = REPO_ROOT / "research"
    block = lambda b: {"csi": b["scores"]["csi"], "ci95": b["ci95"]["csi"], "recall": b["scores"]["recall"], "precision": b["scores"]["precision"]}
    v3 = json.loads((research / "v3_yellow_055D_frozen_metrics.json").read_text())
    held.append({"site": v3["site"], "pair": v3["pair"], "method": "v3, Otsu threshold (frozen)", "confirmed_ha": v3["truth_ha"]["wet_primary"], **block(v3["primary_v3_mapped_area"])})
    for river, pair in (("village_creek", "134A_sep03"), ("pine_island", "012D_sep07"), ("village_creek", "012D_sep07"), ("pine_island", "134A_sep03")):
        d = json.loads((research / f"edouard_{river}_{pair}_frozen_metrics.json").read_text())
        held.append({"site": river, "pair": pair, "method": "v3, Otsu threshold (frozen)", "confirmed_ha": d["truth_ha"]["wet_primary"], **block(d["primary_v3_mapped_area"])})
    for river, pair in (("pee_dee", "098D_jul27"), ("neuse", "090A_jul26"), ("lower_sabine", "134A_jul17")):
        d = json.loads((research / f"v4_{river}_{pair}_frozen_metrics.json").read_text())
        held.append({"site": river, "pair": pair, "method": "v4, median baseline (frozen)", "confirmed_ha": d["truth_ha"]["wet_primary"],
                     "label": "high" if d["confident"] else "low", **block(d["primary_v4"])})
    overbank = []
    flood_level = json.loads((research / "overbank_gauges.json").read_text())
    for river, pair in OVERBANK_PASSES:     # protocol order; unjudgeable passes carry no scores, because recall is undefined at 0 ha
        d = json.loads((research / f"overbank_{river}_{pair}_frozen_metrics.json").read_text())
        gauges = flood_level[river][pair]
        above = sum(g["above"] and abs(g["margin_m"]) >= 0.05 for g in gauges)   # protocol section 2: a 0.04 m margin is inside the datum uncertainty
        stage[(river, pair)] = f"{above} of {len(gauges)} gauges above"
        held.append({"site": river, "pair": pair, "method": "v4, overbank test (frozen)", "confirmed_ha": d["truth_ha"]["wet_primary"], "label": "high" if d["confident"] else "low",
                     **(block(d["primary_v4"]) if d["judgeable"] else {})})
        overbank.append({"site": river, "pair": pair, "judgeable": d["judgeable"], "csi": d["v4_csi"], "lidar_csi": d["lidar_2m_same_pixels"]["scores"]["csi"], "signal": d["trust_signal"], "signal_right": d["signal_right"],
                         "high": d["confident"], "lidar_interval": d["v4_minus_lidar_csi"]["ci95"], "lidar_difference": d["v4_minus_lidar_csi"]["difference"], "estimated_ha": d["truth_ha"]["wet_primary"], "rainy": d["rain"]["rainy"],
                         "upland_warned": d["upland_warning"]["warned"], "v3_csi": d["baseline_v3_same_pixels"]["scores"]["csi"], "recall": d["primary_v4"]["scores"]["recall"] if d["judgeable"] else None, "above_flood": above, "gauges": len(gauges)})
    hidden = json.loads((research / "hidden_gauge.json").read_text())
    satilla = json.loads((research / "satilla_audit.json").read_text())
    dev = []
    for pair in ("076A_oct17", "127D_oct21"):
        d = json.loads((root / "choctawhatchee" / pair / "metrics.json").read_text())
        dev.append({"site": "choctawhatchee", "pair": pair, "method": "v1 (development, lower reach)",
                    "csi": d["test"]["csi"], "ci95": d["test_ci95"]["csi"], "recall": d["test"]["recall"],
                    "precision": d["test"]["precision"]})
    for r in held + dev:
        r["stage"] = stage.get((r["site"], r["pair"]))
    gaps, tonle = research_extras(research)
    return {"audit": rows, "held_out": held, "overbank": overbank, "development": dev, "hidden_gauge": {**hidden["all"], **gaps}, "tonle_sap": tonle, "satilla_audit": next(r for r in satilla["dates"] if r["date"] == HERO_GFM_DATE)}


def unusable_passes(name):
    """Passes that were run but have no valid radar on the labelled ground, so they can't be scored or shown."""
    out = []
    for f in sorted((REPO_ROOT / "outputs" / name).glob("*/frozen_v3_metrics.json")):
        d = json.loads(f.read_text())
        if d.get("valid_share_of_labelled") == 0:
            out.append({"pair": d["pair"], "valid_share": 0.0, "why": "no valid radar over this reach"})
    return out


def research_extras(research):
    """Numbers the evidence page quotes from research files: the gauge spacing in the hidden-gauge check and the Tonle Sap predictions."""
    hidden = json.loads((research / "hidden_gauge.json").read_text())
    gaps = [c["neighbour_gap_km"] for c in hidden["cases"]]
    preds = json.loads((research / "tonle_sap_results.json").read_text())["predictions"]
    return {"gap_km": [min(gaps), max(gaps)]}, {"predictions": len(preds), "held": sum(bool(v["holds"]) for v in preds.values())}


def main():
    if DATA.exists():
        shutil.rmtree(DATA)
    DATA.mkdir(parents=True)
    rule = SelfCalRule(**{k: v for k, v in json.loads(RECEIPT_V2.read_text())["v2_rule"].items() if k != "type"})
    v3_rule = settings_from(json.loads(RECEIPT_V3.read_text())).rule
    v4_rule = rule_from(json.loads(RECEIPT_V4.read_text()))
    manifest = {"sites": [], "legend": {"landcover": LANDCOVER, "timing": TIMING}}
    for name, spec in SITES.items():
        site = yellow_series_site() if name == "yellow" else load_site(name)
        entry = {"id": name, "title": spec["title"], "role": spec["role"], "pairs": []}
        excl_done = False
        for pair_name, label in spec["pairs"].items():
            meta, wg = build_pair(site, pair_name, label, rule, v3_rule, v4_rule, DATA / name / pair_name, write_excl=not excl_done)
            excl_done = excl_done or "gfm_excl" in meta["layers"]
            entry["pairs"].append(meta)
            entry["corners"] = corners(wg)
            print(f"{name} {pair_name}: {meta['stats']} gfm {meta.get('gfm_date')}")
        entry["gauges"] = f"{name}/gauges.json"
        (DATA / name / "gauges.json").write_text(json.dumps(gauges_json(site, [p["time"] for p in entry["pairs"]])))
        lons = [c[0] for c in entry["corners"]]
        lats = [c[1] for c in entry["corners"]]
        entry["bounds"] = [min(lons), min(lats), max(lons), max(lats)]
        entry["gauge_points"] = [{"name": gauge_name(g.name), "lon": g.lon, "lat": g.lat} for g in site.gauges]
        if name == "yellow":
            entry["timeline"] = [p["frame"] for p in entry["pairs"]]
            entry["unusable"] = unusable_passes(name)
        manifest["sites"].append(entry)
    add_rain(manifest)
    manifest["hero"] = build_hero()
    (DATA / "manifest.json").write_text(json.dumps(manifest, indent=1, allow_nan=False))
    metrics = metrics_json()
    (DATA / "metrics.json").write_text(json.dumps(metrics, indent=1, default=float))
    # The maps must reproduce the recorded numbers exactly, or the app and the evidence disagree.
    yellow = next(p for s in manifest["sites"] if s["id"] == "yellow" for p in s["pairs"] if p["frozen"])
    frozen = next(r for r in metrics["held_out"] if r["site"] == "yellow")
    if abs(yellow["v3_csi"] - frozen["csi"]) > 1e-9:
        raise SystemExit(f"v3 on this pass scored {yellow['v3_csi']}, frozen {frozen['csi']}")
    dev = json.loads((REPO_ROOT / "outputs" / "explore" / "dev_v4.json").read_text())["grid"]["median / adaptive / check None"]
    for s in manifest["sites"]:
        for p in s["pairs"]:
            k = f"{s['id']} {p['id']}"
            if k in dev and p["score"]["scorable"] and abs(p["score"]["csi"] - dev[k]["csi"]) > 1e-9:
                raise SystemExit(f"{k}: app CSI {p['score']['csi']} differs from development {dev[k]['csi']}")
    import build_dashboard  # imported here because it reuses this module's helpers

    build_dashboard.main()
    import build_atlas  # the worldwide blind-spot map, from its cache in outputs/atlas

    build_atlas.main()
    import build_hero_photo  # the Sentinel-2 photo behind the story page's lens, from its cache in outputs/hero_photo

    build_hero_photo.main()
    import build_story_charts  # the story page's chart data, from saved layers and cached river levels

    build_story_charts.main()
    import c_band_check  # the C-band against L-band panel; Sentinel-1 comes from its cache in <data root>/pearl/s1_rtc

    c_band_check.measure()
    import build_lantern  # the journey's globe: floodplain-forest points, town lights and coastlines, from the atlas

    build_lantern.main()
    import build_figures  # the scientific figures' data, summarised from saved results and the frozen runs' layers

    build_figures.main()
    total = sum(p.stat().st_size for p in DATA.rglob("*") if p.is_file())
    print(f"app data: {total / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
