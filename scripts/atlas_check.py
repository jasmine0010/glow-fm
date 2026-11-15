"""Does "floodplain under trees" stand in for what Copernicus GFM really says it can't map?

Compares the atlas's rule with GFM's own exclusion masks, on floodplain ground around every river where those masks are saved locally.
Uses the flood-hazard pixel grid (3 arc seconds). Writes research/blind_spot_atlas_check.json.
"""
import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import Resampling, reproject, transform_bounds
from rasterio.windows import Window, from_bounds

from hidden_floods.config import data_root

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "outputs" / "atlas"
WC = "/vsicurl/https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_{}_Map.tif"
# The Choctawhatchee and Yellow share GFM scenes, so they count as one area.
AREAS = {"Satilla, Georgia": ["satilla"], "Choctawhatchee and Yellow, Florida": ["choctawhatchee", "yellow"], "Pearl, Louisiana and Mississippi": ["pearl"], "Tangipahoa, Louisiana": ["tangipahoa"], "Tonle Sap, Cambodia": ["tonle_sap"]}


def wc_key(lat0, lon0):
    return f"{'N' if lat0 >= 0 else 'S'}{abs(lat0):02d}{'E' if lon0 >= 0 else 'W'}{abs(lon0):03d}"


def hazard_files(west, south, east, north):
    """The hazard tiles are named by their north-west corner, in steps of 10 degrees."""
    out = []
    for n in range(int(np.ceil(south / 10) * 10), int(np.ceil(north / 10) * 10) + 1, 10):
        for w in range(int(np.floor(west / 10) * 10), int(np.floor(east / 10) * 10) + 1, 10):
            ns, ew = "N" if n >= 0 else "S", "E" if w >= 0 else "W"
            out += list((WORK / "jrc").glob(f"ID*_{ns}{abs(n)}_{ew}{abs(w)}.tif"))
    return out


def area_check(name, rivers):
    masks = [p for r in rivers for p in sorted((data_root() / r / "ops").glob("*exclusion_mask*.tif"))]
    if not masks:
        masks = [p for r in rivers for p in sorted((data_root() / r).rglob("*exclusion_mask*.tif"))]
    if not masks:
        return None
    boxes = []
    for path in masks:
        with rasterio.open(path) as m:
            boxes.append(transform_bounds(m.crs, "EPSG:4326", *m.bounds))
    west, south = min(b[0] for b in boxes), min(b[1] for b in boxes)
    east, north = max(b[2] for b in boxes), max(b[3] for b in boxes)
    tree_px = other_px = in_tree = in_other = 0
    for src in hazard_files(west, south, east, north):
        with rasterio.open(src) as h:
            win = from_bounds(west, south, east, north, h.transform).round_offsets().round_lengths().intersection(Window(0, 0, h.width, h.height))
            hazard = h.read(1, window=win)
            t = h.window_transform(win)
        flood = (hazard > 0) & (hazard <= 4)
        if not flood.any():
            continue
        # A pixel is covered once any saved scene reaches it, and excluded if any of those scenes excludes it.
        covered, excluded = np.zeros(hazard.shape, bool), np.zeros(hazard.shape, bool)
        for path in masks:
            one = np.full(hazard.shape, 255, np.uint8)
            with rasterio.open(path) as m:
                reproject(rasterio.band(m, 1), one, dst_transform=t, dst_crs="EPSG:4326", dst_nodata=255, resampling=Resampling.nearest)
            covered |= one != 255
            excluded |= one == 1
        rows, cols = np.nonzero(flood & covered)
        if not len(rows):
            continue
        lats, lons = t.f + (rows + 0.5) * t.e, t.c + (cols + 0.5) * t.a
        la3, lo3 = (np.floor(lats / 3) * 3).astype(int), (np.floor(lons / 3) * 3).astype(int)
        tree, known = np.zeros(len(rows), bool), np.zeros(len(rows), bool)
        for a, b in np.unique(np.c_[la3, lo3], axis=0).tolist():
            here = (la3 == a) & (lo3 == b)
            with rasterio.open(WC.format(wc_key(a, b))) as d:
                wc = d.read(1, out_shape=(4500, 4500))
            v = wc[np.clip(((a + 3 - lats[here]) / 3 * 4500).astype(int), 0, 4499), np.clip(((lons[here] - b) / 3 * 4500).astype(int), 0, 4499)]
            tree[here], known[here] = np.isin(v, (10, 95)), v > 0
        e = excluded[rows, cols]
        tree_px += int((known & tree).sum())
        other_px += int((known & ~tree).sum())
        in_tree += int((known & tree & e).sum())
        in_other += int((known & ~tree & e).sum())
    if not tree_px + other_px:
        return None
    return {"area": name, "mask_files": len(masks), "tree_share": round(tree_px / (tree_px + other_px), 3),
            "gfm_excludes_share_under_trees": round(in_tree / max(tree_px, 1), 3), "gfm_excludes_share_elsewhere": round(in_other / max(other_px, 1), 3), "share_of_gfm_exclusion_that_is_trees": round(in_tree / max(in_tree + in_other, 1), 3),
            "tree_px": tree_px, "other_px": other_px, "in_mask_tree": in_tree, "in_mask_other": in_other}


def main():
    sys.stdout.reconfigure(encoding="utf8")
    rows = []
    for name, group in AREAS.items():
        row = area_check(name, group)
        print(name, row, flush=True)
        if row:
            rows.append(row)
    tp, oth, it, io = (sum(r[k] for r in rows) for k in ("tree_px", "other_px", "in_mask_tree", "in_mask_other"))
    out = {"note": "Pixels on 100-year flood-hazard ground, 3 arc seconds. GFM's masks were saved for these flood windows, so the footprints are not a random sample of the world.", "areas": rows,
           "gfm_excludes_share_under_trees": round(it / max(tp, 1), 3), "gfm_excludes_share_elsewhere": round(io / max(oth, 1), 3), "share_of_gfm_exclusion_that_is_trees": round(it / max(it + io, 1), 3), "lowest_area_share_under_trees": min(r["gfm_excludes_share_under_trees"] for r in rows), "highest_area_share_under_trees": max(r["gfm_excludes_share_under_trees"] for r in rows)}
    (ROOT / "research" / "blind_spot_atlas_check.json").write_text(json.dumps(out, indent=1))
    print({k: v for k, v in out.items() if k != "areas"})


if __name__ == "__main__":
    main()
