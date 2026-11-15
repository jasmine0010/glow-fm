"""C-band (Sentinel-1) against L-band (NISAR) on the same flooded forest, by the rules in research/C_BAND_PROTOCOL.md.

    python scripts/c_band_check.py              # the measurement, the map layer and research/c_band_results.json

Sentinel-1 comes from Microsoft Planetary Computer's open sentinel-1-rtc collection (CC-BY-4.0, anonymous token). Only the
Pearl box is read, over HTTP ranges, and the result on the project grid is cached in <data root>/pearl/s1_rtc/, outside the
repository. The protocol first named NASA's ASF copy, which needs a further licence on the account; see the protocol.

The --download path for ASF's OPERA RTC-S1 files is kept for anyone whose account has that licence. It is not used here.
"""

import argparse
import json
import urllib.parse
import urllib.request

import numpy as np
import rasterio
from rasterio.warp import Resampling, reproject, transform_bounds
from rasterio.windows import from_bounds
from build_app import DATA, change_image, corners, to_web, web_grid
from fetch_stacks import LOCAL, scenes_for

from hidden_floods.audit import truth_context
from hidden_floods.config import REPO_ROOT, data_root, load_site
from hidden_floods.detect import to_db
from hidden_floods.drivers import BIN_EDGES_M, MIN_BIN_PX, _median, response_curve
from hidden_floods.fetch import CMR, download, get_json
from hidden_floods.grid import warp_to_grid
from hidden_floods.io.dem import dem_on_grid
from hidden_floods.io.nisar import read_gcov
from hidden_floods.pipeline import analysis_grid
from hidden_floods.selfcal import smooth_nan
from hidden_floods.stack import read_scene
from hidden_floods.trust import worldcover_class, worldcover_on_grid
from hidden_floods.v3 import LC_TREE
from hidden_floods.v4 import median_baseline

SITE, NISAR_PAIR = "pearl", "105A_jul03"
BOX = "-89.85,30.4,-89.6,30.9"
DATES = {"before": "2026-06-16", "flood": "2026-07-05"}
BURSTS = ("T165-352437-IW2", "T165-352438-IW2", "T165-352439-IW2", "T165-352440-IW2")
FIXED_NISAR = {"hh_contrast_db": 1.12, "hv_contrast_db": 0.22}   # from app/data/manifest.json, quoted in the protocol
OUT = data_root() / SITE / "s1_rtc"
PC_STAC = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
PC_TOKEN = "https://planetarycomputer.microsoft.com/api/sas/v1/token/sentinel-1-rtc"
PC_SCENES = {"before": "S1A_IW_GRDH_1SDV_20260616T000216", "flood": "S1D_IW_GRDH_1SDV_20260705T000135"}   # fixed in the protocol


def granules(day):
    q = urllib.parse.urlencode({"short_name": "OPERA_L2_RTC-S1_V1", "bounding_box": BOX, "temporal": f"{day}T00:00:00Z,{day}T23:59:59Z", "page_size": 50})
    out = []
    for it in get_json(f"{CMR}?{q}")["items"]:
        for u in it["umm"].get("RelatedUrls", []):
            url = u["URL"]
            if url.startswith("https") and url.endswith(("_VV.tif", "_VH.tif")) and any(b in url for b in BURSTS):
                out.append(url)
    return sorted(set(out))


def fetch_all():
    for key, day in DATES.items():
        urls = granules(day)
        if len(urls) != 2 * len(BURSTS):
            raise SystemExit(f"{day}: expected {2 * len(BURSTS)} files, CMR lists {len(urls)}")
        for url in urls:
            path = download(url, OUT / day / url.rsplit("/", 1)[1], netrc=True)
            print(key, path.name, f"{path.stat().st_size / 1e6:.1f} MB", flush=True)


def pc_items():
    body = json.dumps({"collections": ["sentinel-1-rtc"], "bbox": [float(x) for x in BOX.split(",")], "limit": 20,
                       "datetime": f"{DATES['before']}T00:00:00Z/{DATES['flood']}T23:59:59Z"}).encode()
    req = urllib.request.Request(PC_STAC, data=body, headers={"Content-Type": "application/json", "User-Agent": "hidden-floods-research/0.1"})
    with urllib.request.urlopen(req, timeout=120) as r:
        feats = json.load(r)["features"]
    token = get_json(PC_TOKEN)["token"]
    out = {}
    for key, scene in PC_SCENES.items():
        f = next(x for x in feats if x["id"].startswith(scene))
        out[key] = {pol: f"{f['assets'][pol.lower()]['href']}?{token}" for pol in ("VV", "VH")}
    return out


def read_box(url, grid):
    """Linear gamma-0 for the grid's box only, area-averaged onto the grid. Zero and negative values are no data."""
    left, top = grid.x0, grid.y0
    right, bottom = left + grid.width * grid.res, top - grid.height * grid.res
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif,.tiff", GDAL_HTTP_MAX_RETRY="4", GDAL_HTTP_RETRY_DELAY="3"):
        with rasterio.open(url) as src:
            b = transform_bounds(grid.crs, src.crs, left, bottom, right, top, densify_pts=21)
            win = from_bounds(*b, transform=src.transform).round_offsets().round_lengths()
            arr = src.read(1, window=win, boundless=True, fill_value=0).astype(np.float32)
            arr[~(arr > 0)] = np.nan
            out = np.full(grid.shape, np.nan, np.float32)
            reproject(arr, out, src_transform=src.window_transform(win), src_crs=src.crs, dst_transform=grid.transform, dst_crs=grid.crs,
                      resampling=Resampling.average, src_nodata=np.nan, dst_nodata=np.nan)
    return out


def change_db(grid):
    """dB(flood) minus dB(before) for VV and VH, cached on the grid after the first read."""
    cache = OUT / "pc_change_on_grid.npz"
    if cache.exists():
        z = np.load(cache)
        return z["vv"], z["vh"]
    items = pc_items()
    out = {}
    for pol in ("VV", "VH"):
        a, b = (read_box(items[k][pol], grid) for k in ("flood", "before"))
        out[pol.lower()] = 10 * np.log10(a) - 10 * np.log10(b)
        print(pol, "read", flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(cache, **out)
    return out["vv"], out["vh"]


def mosaic_db(day, pol, grid):
    """Area-averaged gamma-0 on the grid, bursts filled in order, then dB. Linear values are averaged, as power should be."""
    out = np.full(grid.shape, np.nan, np.float32)
    files = sorted((OUT / day).glob(f"*_{pol}.tif"))
    if len(files) != len(BURSTS):
        raise SystemExit(f"{day} {pol}: {len(files)} files, run with --download first")
    for f in files:
        w = warp_to_grid(f, grid, categorical=False, nodata=np.nan)
        w = np.where(w > 0, w, np.nan)
        out = np.where(np.isnan(out), w, out)
    return 10 * np.log10(out)


def contrast(change, tree_region, depth):
    above = tree_region & (depth >= -3.0) & (depth < -1.0)
    below = tree_region & (depth >= 0.5) & (depth < 2.0)
    a, b = _median(change, above), _median(change, below)
    n_a, n_b = int((above & np.isfinite(change)).sum()), int((below & np.isfinite(change)).sum())
    ok = a is not None and b is not None and n_a >= MIN_BIN_PX and n_b >= MIN_BIN_PX
    return {"above_db": a, "below_db": b, "contrast_db": (b - a) if ok else None, "above_ha": n_a * 0.25, "below_ha": n_b * 0.25}


def corridor_bounds(corridor, grid, wg, fallback):
    """The whole river corridor's lon/lat box, so both maps frame every reach and nothing else."""
    web = to_web(corridor.astype(np.uint8), grid, wg, True, 0) == 1
    if not web.any():
        return fallback
    rows, cols = np.nonzero(web)
    (w, n), (e, _), _, (_, s_) = corners(wg)
    merc = lambda lat: np.log(np.tan(np.pi / 4 + np.radians(lat) / 2))
    yN, yS = merc(n), merc(s_)
    lat = lambda r: float(np.degrees(2 * np.arctan(np.exp(yN - r / web.shape[0] * (yN - yS))) - np.pi / 2))
    lon = lambda c: float(w + c / web.shape[1] * (e - w))
    return [lon(cols.min()), lat(rows.max() + 1), lon(cols.max() + 1), lat(rows.min())]


def reading(best):
    if best is None:
        return "No reading"
    if best < 0.5:
        return "C-band shows little of it"
    if best < FIXED_NISAR["hh_contrast_db"]:
        return "C-band shows it, but less"
    return "C-band shows it as well or better"


def measure():
    site = load_site(SITE)
    grid = analysis_grid(site)
    dem = dem_on_grid(site.dem_path, grid)
    ctx = truth_context(site, f"{DATES['flood']}T00:01:51Z", dem=dem, grid=grid)
    t = ctx.truth
    lc = worldcover_class(worldcover_on_grid(data_root() / "worldcover", grid))
    vv, vh = change_db(grid)
    depth = np.where(t.corridor, t.depth_m, np.nan)
    valid = np.isfinite(vv) & np.isfinite(vh)
    tree_region = valid & (lc == LC_TREE) & ctx.supported & ~ctx.permanent_water & t.corridor & np.isfinite(depth)
    c_vv, c_vh = contrast(vv, tree_region, depth), contrast(vh, tree_region, depth)
    best = max((c["contrast_db"] for c in (c_vv, c_vh) if c["contrast_db"] is not None), default=None)
    manifest = json.loads((DATA / "manifest.json").read_text())
    nisar = next(p for s in manifest["sites"] if s["id"] == SITE for p in s["pairs"] if p["id"] == NISAR_PAIR)["drivers"]
    nc = nisar["contrast"]
    result = {
        "protocol": "research/C_BAND_PROTOCOL.md",
        "c_band": {"dates": DATES, "source": "Microsoft Planetary Computer sentinel-1-rtc (Catalyst RTC), scenes " + ", ".join(PC_SCENES.values()), "vv": c_vv, "vh": c_vh, "best_contrast_db": best,
                   "curve": [{"water_above_ground_m": r["water_above_ground_m"], "vv_db": r["hh_db"], "vh_db": r["hv_db"], "ha": r["ha"]}
                             for r in response_curve(depth, vv, vh, tree_region, BIN_EDGES_M)]},
        "l_band": {"pair": NISAR_PAIR, "hh_contrast_db": nc["hh_below_water_db"] - nc["hh_above_water_db"], "hv_contrast_db": nc["hv_below_water_db"] - nc["hv_above_water_db"],
                   "fixed_in_protocol": FIXED_NISAR, "curve": nisar["curve"]},
        "estimate_wet_tree_ha": float((tree_region & t.wet).sum() * 0.25),
        "reading": reading(best),
    }
    (REPO_ROOT / "research" / "c_band_results.json").write_text(json.dumps(result, indent=1))
    # Pictures for the site, one per band, on the shared change scale (fades in from +1 dB). Each is drawn relative to its own
    # dry forest (the "above" group of the contrast), so a scene-wide offset such as Sentinel-1A against 1D calibration
    # doesn't hide or exaggerate either band. That is the same reference the frozen contrast uses.
    pair = site.pairs[NISAR_PAIR]
    wet = read_gcov(site.gcov_path(pair.wet), grid)
    # The baseline is pinned to the scenes the published build used. The catalog query behind scenes_for once came back
    # short during development of this script, which moved the median, so a different list stops the run.
    published = next(p for s in manifest["sites"] if s["id"] == SITE for p in s["pairs"] if p["id"] == NISAR_PAIR)["baseline_dates"]
    scenes = [x for x in scenes_for(site, pair) if x.time[:10] in published]
    if sorted(x.time[:10] for x in scenes) != sorted(published):
        raise SystemExit(f"NISAR baseline scenes {[x.time[:10] for x in scenes]} differ from the published {published}; run again")
    d_hh = to_db(wet["HHHH"]) - median_baseline(np.stack([read_scene(site, grid, x, LOCAL)["hh"] for x in scenes]))
    ctx3 = truth_context(site, pair.wet_time, dem=dem, grid=grid)
    depth3 = np.where(ctx3.truth.corridor, ctx3.truth.depth_m, np.nan)
    tree3 = np.isfinite(d_hh) & (lc == LC_TREE) & ctx3.supported & ~ctx3.permanent_water & ctx3.truth.corridor & np.isfinite(depth3)
    l_check = contrast(d_hh, tree3, depth3)
    # The recomputed NISAR contrast must match the published one, or the picture isn't the measured map.
    if abs(l_check["contrast_db"] - result["l_band"]["hh_contrast_db"]) > 0.01:
        raise SystemExit(f"NISAR contrast recomputed {l_check['contrast_db']}, published {result['l_band']['hh_contrast_db']}")
    wg = web_grid(site)
    out = DATA / SITE / NISAR_PAIR
    corridor = t.corridor | ctx3.truth.corridor
    for name, change, ref in (("cband.png", vv, c_vv["above_db"]), ("lband.png", d_hh, l_check["above_db"])):
        rel = np.where(corridor, smooth_nan(change - ref, 3), np.nan).astype(np.float32)
        change_image(to_web(rel, grid, wg, False, np.float32(np.nan)), wg, out / name)
    shown = lambda change, ref: float(((smooth_nan(change - ref, 3) > 1.0) & corridor & (lc == LC_TREE)).sum() * 0.25)
    result["pictures"] = {"reference": "each band's median change on dry forest, 1-3 m above the water",
                          "cband_ha_over_1db": shown(vv, c_vv["above_db"]), "lband_ha_over_1db": shown(d_hh, l_check["above_db"])}
    (REPO_ROOT / "research" / "c_band_results.json").write_text(json.dumps(result, indent=1))
    print("pictures", result["pictures"])
    # What the story page's "two radars" panel reads.
    metrics = json.loads((DATA / "metrics.json").read_text())
    gfm = next(r for r in metrics["audit"] if r["site"] == SITE and r["date"] == DATES["flood"].replace("-", ""))
    site_entry = next(x for x in manifest["sites"] if x["id"] == SITE)
    bands = {"site": SITE, "pass": NISAR_PAIR, "corners": corners(wg), "bounds": corridor_bounds(corridor, grid, wg, site_entry["bounds"]),
             "layers": {"cband": "cband.png", "lband": "lband.png", "truth": "truth.png"},
             "cband": {"date": DATES["flood"], "contrast_db": best, "vv_db": c_vv["contrast_db"], "vh_db": c_vh["contrast_db"]},
             "lband": {"time": pair.wet_time, "contrast_db": result["l_band"]["hh_contrast_db"]},
             "flooded_forest_ha": c_vv["below_ha"], "gfm": {"date": gfm["date"], "estimated_ha": gfm["truth_wet_ha"], "mapped_ha": gfm["gfm_on_wet_ha"]},
             "reading": result["reading"]}
    (DATA / "story").mkdir(parents=True, exist_ok=True)
    (DATA / "story" / "bands.json").write_text(json.dumps(bands, separators=(",", ":")))
    print(json.dumps({k: result[k] for k in ("reading", "estimate_wet_tree_ha")}, indent=1))
    print("C-band VV", c_vv, "\nC-band VH", c_vh, "\nL-band HH contrast", round(result["l_band"]["hh_contrast_db"], 3))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--download", action="store_true")
    args = ap.parse_args()
    fetch_all() if args.download else measure()
