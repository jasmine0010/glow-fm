"""Post-hoc: what is the Tonle Sap signal doing, if not what research/TONLE_SAP_CASE.md predicted? Writes research/tonle_sap_posthoc.json.

Comes after the run and changes none of its predictions. Two questions the numbers suggested:
1. Does land that darkens by more than 3 dB sit where GFM independently maps water, more often than chance? Darkening wasn't a prediction.
2. Does the change move outward from the lake over time, as a rising flood would?
Uses scenes already cached and the GFM layers already fetched, and reads no new radar.
"""

import json
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).parent))
from build_app import corners, overlay, to_web
from fetch_global_dem import tile_name
from tonle_sap import AREA, AUDIT, OUT, change_png, scenes

from hidden_floods.config import REPO_ROOT, data_root, load_site
from hidden_floods.frozen import reference_water
from hidden_floods.frozen_no_lidar import DEM_DIR
from hidden_floods.frozen_v4 import RECEIPT as RECEIPT_V4
from hidden_floods.frozen_v4 import rule_from
from hidden_floods.grid import grid_from_lonlat_bbox, warp_to_grid
from hidden_floods.io.operational import gfm_mosaic
from hidden_floods.pipeline import analysis_grid
from hidden_floods.selfcal import height_above_river, smooth_nan
from hidden_floods.stack import read_scene
from hidden_floods.trust import worldcover_class, worldcover_on_grid
from hidden_floods.truth import ValleyLine
from hidden_floods.v4 import median_baseline

BANDS_KM = ((0, 5), (5, 10), (10, 15), (15, 20), (20, 30), (30, 50), (50, 200))
DARK_DB = -3.0
site = load_site("tonle_sap")
grid = analysis_grid(site)
wg = grid_from_lonlat_bbox(site.bbox, "EPSG:3857", 60.0)
OUT.mkdir(parents=True, exist_ok=True)
rule = rule_from(json.loads(RECEIPT_V4.read_text()))
timing = np.zeros(grid.shape, np.uint8)
frames ={f["date"]: f for f in json.loads((REPO_ROOT / "research" / "tonle_sap_results.json").read_text())["frames"]}
water = reference_water(site.operational_dir, grid)
labels, n = ndimage.label(water)
lake = labels == (1 + int(np.argmax(ndimage.sum(water, labels, range(1, n + 1)))))
dist_m = ndimage.distance_transform_edt(~lake) * site.resolution_m
dist = dist_m / 1000.0
lc = worldcover_class(worldcover_on_grid(data_root() / "worldcover", grid))
dem = np.full(grid.shape, np.nan, np.float32)
for lat in (12, 13):
    for lon in (103, 104):
        w = warp_to_grid(DEM_DIR / f"{tile_name(lat, lon)}.tif", grid, categorical=False, nodata=np.nan, dtype=np.float32)
        dem = np.where(np.isfinite(dem), dem, w)
_, chain = ValleyLine.from_lonlat(grid, site.valley_line).project(*grid.meshgrid())
hand = height_above_river(dem, dist_m, chain)
overlay(to_web(lake.astype(np.uint8), grid, wg, True, 0) == 1, (40, 110, 255), 90, OUT / "lake.png")
land = ~lake
listed = scenes()
data = [read_scene(site, grid, s) for s in listed]
hh_base, hv_base = median_baseline(np.stack([x["hh"] for x in data[:3]])), median_baseline(np.stack([x["hv"] for x in data[:3]]))
med = lambda a, m: float(np.nanmedian(a[m])) if m.any() and np.isfinite(a[m]).any() else None
rows = []
for s, x in zip(listed[3:], data[3:], strict=True):
    day = s.time[:10]
    hh, hv = smooth_nan(x["hh"] - hh_base, 3), smooth_nan(x["hv"] - hv_base, 3)
    dark = land & (hh < DARK_DB)
    row = {"date": day, "dark_ha": float(dark.sum() * AREA), "bands": []}
    folder = OUT / day
    folder.mkdir(parents=True, exist_ok=True)
    overlay(to_web(dark.astype(np.uint8), grid, wg, True, 0) == 1, (40, 110, 255), 200, folder / "dark.png")
    change_png(to_web(hh.astype(np.float32), grid, wg, False, np.float32(np.nan)), folder / "dhh.png")
    v4 = rule.apply(x["hh"] - hh_base, x["hv"] - hv_base, lc, timing, hand, dist_m)
    overlay(to_web(v4["pred"].astype(np.uint8), grid, wg, True, 0) == 1, (214, 58, 214), 225, folder / "nisar.png")
    for lo, hi in BANDS_KM:
        b = land & (dist >= lo) & (dist < hi)
        t = b & (lc == 1)
        row["bands"].append({"km": [lo, hi], "land_ha": float(b.sum() * AREA), "dark_share": float((dark & b).sum() / max(b.sum(), 1)), "tree_hh_db": med(hh, t), "tree_hv_db": med(hv, t), "open_land_hh_db": med(hh, b & (lc == 3))})
    d = frames[day]["gfm_date"]
    if d:
        gfm = gfm_mosaic(AUDIT, d, grid)
        ok = land & gfm.covered
        wet = gfm.flood & ok
        # A base rate from land near the lake, so distance alone can't produce agreement.
        near_dry = ok & ~gfm.flood & (dist < 30)
        row["gfm"] = {"date": d, "water_ha": float(wet.sum() * AREA), "water_that_is_dark": float((dark & wet).sum() / max(wet.sum(), 1)), "other_near_land_that_is_dark": float((dark & near_dry).sum() / max(near_dry.sum(), 1)), "other_land_that_is_dark": float((dark & ok & ~gfm.flood).sum() / max((ok & ~gfm.flood).sum(), 1)),
                      "dark_that_is_gfm_water": float((dark & wet).sum() / max((dark & ok).sum(), 1)), "dark_outside_gfm_water_in_mask": float((dark & ok & ~gfm.flood & gfm.excluded).sum() / max((dark & ok & ~gfm.flood).sum(), 1))}
    rows.append(row)
    print(day, "dark", round(row["dark_ha"]), [round(b["dark_share"], 2) for b in row["bands"]], "tree HH", [None if b["tree_hh_db"] is None else round(b["tree_hh_db"], 1) for b in row["bands"]], "gfm", {k: round(v, 2) if isinstance(v, float) else v for k, v in row.get("gfm", {}).items()}, flush=True)
(REPO_ROOT / "research" / "tonle_sap_posthoc.json").write_text(json.dumps({"note": "Post-hoc. Doesn't change the fixed predictions.", "bands_km": BANDS_KM, "corners": corners(wg), "frames": rows}, indent=1, default=float))
print("POSTHOC DONE", flush=True)
