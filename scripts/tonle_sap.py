"""Tonle Sap seasonal case, following research/TONLE_SAP_CASE.md: python scripts/tonle_sap.py

Unvalidated: there are no gauges or lidar here, and nothing is scored. Writes research/tonle_sap_results.json and map layers to outputs/tonle_sap/ (kept off the site).
Records the hash of the rules file, and refuses to run again once results exist.
"""

import hashlib
import json
import re
import subprocess
import sys
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).parent))
from fetch_global_dem import BASE, tile_name
from setup_edouard import WORLDCOVER, fetch_reference_water

from hidden_floods.config import REPO_ROOT, data_root, load_site
from hidden_floods.fetch import CMR, STAC, download, fetch_gfm, get_json
from hidden_floods.frozen import reference_water
from hidden_floods.frozen_no_lidar import DEM_DIR
from hidden_floods.frozen_v4 import RECEIPT as RECEIPT_V4
from hidden_floods.frozen_v4 import rule_from
from hidden_floods.grid import grid_from_lonlat_bbox, warp_to_grid
from hidden_floods.io.operational import gfm_mosaic
from hidden_floods.pipeline import analysis_grid
from hidden_floods.selfcal import height_above_river, smooth_nan
from hidden_floods.stack import Scene, read_scene
from hidden_floods.stamps import stamp
from hidden_floods.trust import worldcover_class, worldcover_on_grid
from hidden_floods.truth import ValleyLine
from hidden_floods.v3 import LC_TREE
from hidden_floods.v4 import median_baseline

DATES = ("20260619", "20260701", "20260713", "20260725", "20260818", "20260830", "20260911", "20260923", "20261005", "20261017")
RULES = REPO_ROOT / "research" / "TONLE_SAP_CASE.md"
RESULTS = REPO_ROOT / "research" / "tonle_sap_results.json"
OUT = REPO_ROOT / "outputs" / "tonle_sap"   # map layers stay local; the site doesn't show this case
AUDIT = data_root() / "tonle_sap" / "ops_audit"
AREA = 0.36           # hectares per 60 m pixel
NEAR_M, MID_M, FAR_M, BRIGHT_DB = 15000.0, 30000.0, 30000.0, 2.0
PATTERN = re.compile(r"GCOV_\d+_083_A_008_2005_DHDH_[A-Z]_(\d{8})T(\d{6})_.*_(\d+)$")


def scenes():
    """Latest version of each listed scene, oldest first."""
    site = load_site("tonle_sap")
    best = {}
    q = urllib.parse.urlencode({"short_name": "NISAR_L2_GCOV_PROVISIONAL_V1", "bounding_box": ",".join(map(str, site.bbox)), "page_size": 200, "sort_key": "start_date"})
    for it in get_json(f"{CMR}?{q}")["items"]:
        name = it["umm"]["GranuleUR"]
        m = PATTERN.search(name)
        if not m or m[1] not in DATES:
            continue
        url = next(u["URL"] for u in it["umm"]["RelatedUrls"] if u.get("Type") == "GET DATA" and u["URL"].startswith("https") and u["URL"].endswith(".h5"))
        if m[1] not in best or m[3] > best[m[1]][0]:
            t = f"{m[1][:4]}-{m[1][4:6]}-{m[1][6:]}T{m[2][:2]}:{m[2][2:4]}:{m[2][4:]}Z"
            best[m[1]] = (m[3], Scene(name, "083A", "008", t, url))
    missing = [d for d in DATES if d not in best]
    if missing:
        raise SystemExit(f"scenes missing from the catalog: {missing}")
    return [best[d][1] for d in DATES]


def fetch_static(site):
    for tile in ("N12E102",):
        path = data_root() / "worldcover" / f"ESA_WorldCover_10m_2021_v200_{tile}_Map.tif"
        url = WORLDCOVER.format(tile)
        size = int(re.findall(r"content-length:\s*(\d+)", subprocess.run(["curl", "-sIL", "--fail", url], check=True, capture_output=True, text=True).stdout, re.IGNORECASE)[-1])
        if path.exists() and path.stat().st_size != size:
            path.unlink()
        download(url, path)
    names = []
    for lat in (12, 13):
        for lon in (103, 104):
            name = tile_name(lat, lon)
            download(f"{BASE}/{name}/{name}.tif", DEM_DIR / f"{name}.tif")
            names.append(name)
    for d in ("20260818", "20260819", "20260820", "20260817"):
        if fetch_reference_water(site, d):
            print("reference water from", d, flush=True)
            break
    return names


def fetch_water_record(site, t):
    """The nearest GFM date within 3 days that covers at least 90% of the box."""
    grid = analysis_grid(site)
    for off in (0, 1, -1, 2, -2, 3, -3):
        d = (t + timedelta(days=off)).strftime("%Y%m%d")
        day = f"{d[:4]}-{d[4:6]}-{d[6:]}"
        q = urllib.parse.urlencode({"collections": "GFM", "bbox": ",".join(map(str, site.bbox)), "limit": 1, "datetime": f"{day}T00:00:00Z/{day}T23:59:59Z"})
        if not get_json(f"{STAC}?{q}").get("features"):
            continue
        fetch_gfm(site.bbox, d, AUDIT)
        m = gfm_mosaic(AUDIT, d, grid)
        if m.covered.mean() >= 0.9:
            return d, m
    return None, None


def change_png(change, path):
    """The raw radar change on a Web Mercator grid: fades in from +1 dB to full strength at +4 dB."""
    strength = np.clip((np.nan_to_num(change, nan=-99.0) - 1.0) / 3.0, 0.0, 1.0)
    img = np.zeros(change.shape + (4,), np.uint8)
    for k, (lo, hi) in enumerate(((214, 255), (58, 190), (214, 255))):
        img[..., k] = np.round(lo + (hi - lo) * strength).astype(np.uint8)
    img[..., 3] = np.round(235 * strength).astype(np.uint8)
    Image.fromarray(img, "RGBA").save(path, optimize=True)


def main():
    if RESULTS.exists():
        raise SystemExit(f"{RESULTS} exists; this case runs once")
    rules_sha = hashlib.sha256(RULES.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    site = load_site("tonle_sap")
    grid = analysis_grid(site)
    tiles = fetch_static(site)
    print("static data ready", flush=True)

    water = reference_water(site.operational_dir, grid)
    labels, n = ndimage.label(water)
    lake = labels == (1 + int(np.argmax(ndimage.sum(water, labels, range(1, n + 1)))))
    dist = ndimage.distance_transform_edt(~lake) * site.resolution_m
    X, Y = grid.meshgrid()
    _, chain = ValleyLine.from_lonlat(grid, site.valley_line).project(X, Y)
    dem = np.full(grid.shape, np.nan, np.float32)
    for name in tiles:
        w = warp_to_grid(DEM_DIR / f"{name}.tif", grid, categorical=False, nodata=np.nan, dtype=np.float32)
        dem = np.where(np.isfinite(dem), dem, w)
    hand = height_above_river(dem, dist, chain)
    lc = worldcover_class(worldcover_on_grid(data_root() / "worldcover", grid))
    print("lake ha", float(lake.sum() * AREA), "land cover shares", {k: round(float((lc[~lake] == v).mean()), 3) for k, v in (("tree", 1), ("wetland", 2), ("open", 3), ("other", 0))}, flush=True)

    listed = scenes()
    data = []
    for s in listed:
        data.append(read_scene(site, grid, s))
        print("read", s.time[:10], flush=True)
    hh_base, hv_base = median_baseline(np.stack([x["hh"] for x in data[:3]])), median_baseline(np.stack([x["hv"] for x in data[:3]]))

    rule = rule_from(json.loads(RECEIPT_V4.read_text()))
    timing = np.zeros(grid.shape, np.uint8)
    land = ~lake
    tree = land & (lc == LC_TREE)
    near, mid, far = tree & (dist < NEAR_M), tree & (dist < MID_M), tree & (dist >= FAR_M)
    med = lambda a, m: float(np.nanmedian(a[m])) if np.isfinite(a[m]).any() else None

    from build_app import corners, overlay, to_web  # imported late, because it reads several frozen modules

    wg = grid_from_lonlat_bbox(site.bbox, "EPSG:3857", 60.0)
    OUT.mkdir(parents=True, exist_ok=True)
    frames = []
    for s, x in zip(listed[3:], data[3:], strict=True):
        d_hh, d_hv = x["hh"] - hh_base, x["hv"] - hv_base
        v4 = rule.apply(d_hh, d_hv, lc, timing, hand, dist)
        smooth = smooth_nan(d_hh, 3)
        day = s.time[:10]
        when = datetime.fromisoformat(s.time.replace("Z", ""))
        gfm_date, gfm = fetch_water_record(site, when)
        frame = {"date": day, "time": s.time, "mapped_ha": float((v4["pred"] & land).sum() * AREA), "threshold_db": v4["threshold_db"], "confident": v4["confident"], "used_hh_minus_hv": v4["used_hh_minus_hv"], "low_minus_high_db": v4["low_minus_high_db"],
                 "near_tree_hh_db": med(d_hh, near), "near_tree_hv_db": med(d_hv, near), "far_tree_hh_db": med(d_hh, far), "far_tree_hv_db": med(d_hv, far), "bright_tree_ha": float((smooth[mid] > BRIGHT_DB).sum() * AREA),
                 "dark_land_ha": float((smooth[land] < -3.0).sum() * AREA), "valid_share": float(np.isfinite(d_hh).mean()), "gfm_date": gfm_date,
                 "gfm_water_ha": float((gfm.flood & land).sum() * AREA) if gfm is not None else None, "bright_in_gfm_mask": float(gfm.excluded[mid & (smooth > BRIGHT_DB)].mean()) if gfm is not None and (mid & (smooth > BRIGHT_DB)).any() else None}
        frames.append(frame)
        print(json.dumps(frame), flush=True)
        folder = OUT / day
        folder.mkdir(exist_ok=True)
        overlay(to_web(v4["pred"].astype(np.uint8), grid, wg, True, 0) == 1, (214, 58, 214), 225, folder / "nisar.png")
        change_png(to_web(smooth.astype(np.float32), grid, wg, False, np.float32(np.nan)), folder / "dhh.png")
    overlay(to_web(lake.astype(np.uint8), grid, wg, True, 0) == 1, (40, 110, 255), 90, OUT / "lake.png")

    near_hh = [f["near_tree_hh_db"] for f in frames]
    peak = int(np.argmax(near_hh))
    p = frames[peak]
    pairs = [(f["bright_tree_ha"], f["gfm_water_ha"]) for f in frames if f["gfm_water_ha"] is not None]
    rank = lambda a: np.argsort(np.argsort(a))
    rho = float(np.corrcoef(rank([x[0] for x in pairs]), rank([x[1] for x in pairs]))[0, 1]) if len(pairs) >= 5 else None
    predictions = {
        "1_peak_on_or_after_sep11": {"peak_date": p["date"], "peak_db": p["near_tree_hh_db"], "holds": p["date"] >= "2026-09-11"},
        "2_hh_exceeds_hv_by_1db": {"difference_db": p["near_tree_hh_db"] - p["near_tree_hv_db"], "holds": p["near_tree_hh_db"] - p["near_tree_hv_db"] >= 1.0},
        "3_far_forest_under_1db": {"largest_abs_db": max(abs(f["far_tree_hh_db"]) for f in frames), "holds": all(abs(f["far_tree_hh_db"]) < 1.0 for f in frames)},
        "4_rises_with_gfm_water": {"usable_dates": len(pairs), "rank_correlation": rho, "holds": None if rho is None else rho >= 0.6},
    }
    result = {"rules": "research/TONLE_SAP_CASE.md", "rules_sha256": rules_sha, **stamp("started_utc"), "unvalidated": True, "baseline_dates": [s.time[:10] for s in listed[:3]], "lake_ha": float(lake.sum() * AREA), "corners": corners(wg),
              "land_cover_shares": {k: float((lc[land] == v).mean()) for k, v in (("tree", 1), ("wetland", 2), ("open", 3), ("other", 0))}, "frames": frames, "predictions": predictions}
    RESULTS.write_text(json.dumps(result, indent=1, default=float))
    print(json.dumps(predictions, indent=1), flush=True)
    print("TONLE SAP DONE", flush=True)


if __name__ == "__main__":
    main()
