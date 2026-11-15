"""Set up the Tropical Storm Edouard test without reading radar, flood layers or truth.

Creates the two site files, fetches gauges, lidar, GFM reference water (static layer only), WorldCover and the scenes,
then runs metadata and mask checks. It never opens a backscatter layer, a GFM flood layer or a DSWx layer.
"""

import urllib.parse
from pathlib import Path

import h5py
import numpy as np
from pyproj import Transformer

from hidden_floods.config import data_root, load_site
from hidden_floods.fetch import CMR, STAC, download, get_json
from hidden_floods.frozen import reference_water
from hidden_floods.io.dem import dem_on_grid
from hidden_floods.pipeline import analysis_grid
from hidden_floods.selfcal import gauge_supported, height_above_river
from hidden_floods.sitegen import create_site
from hidden_floods.trust import worldcover_class, worldcover_on_grid
from hidden_floods.truth import ValleyLine, refine_centerline

SCENES = {
    "134A_20260822": "NISAR_L2_PR_GCOV_028_134_A_017_4005_DHDH_A_20260822T113542_20260822T113616_P05023_N_F_J_001",
    "134A_20260903": "NISAR_L2_PR_GCOV_029_134_A_017_4005_DHDH_A_20260903T113542_20260903T113616_P05023_N_F_J_001",
    "012D_20260709": "NISAR_L2_PR_GCOV_025_012_D_073_4005_DHDH_A_20260709T010150_20260709T010225_P05023_N_F_J_001",
    "012D_20260826": "NISAR_L2_PR_GCOV_029_012_D_073_4005_DHDH_A_20260826T010148_20260826T010222_P05023_N_F_J_001",
    "012D_20260907": "NISAR_L2_PR_GCOV_030_012_D_073_4005_DHDH_A_20260907T010148_20260907T010222_P05023_N_F_J_001",
}
TIMES = {"134A_20260822": "2026-08-22T11:35:42Z", "134A_20260903": "2026-09-03T11:35:42Z",
         "012D_20260709": "2026-07-09T01:01:50Z", "012D_20260826": "2026-08-26T01:01:48Z", "012D_20260907": "2026-09-07T01:01:48Z"}
SITES = {
    "village_creek": {"gauges": ["08041300", "08041500"], "description": "Tropical Storm Edouard, Village Creek TX. Held-out v3 test.",
                      "pairs": {"134A_sep03": ("134A_20260903", "134A_20260822"), "012D_sep07": ("012D_20260907", "012D_20260826")}},
    "pine_island": {"gauges": ["08041700", "08041749"], "description": "Tropical Storm Edouard, Pine Island Bayou TX. Held-out v3 test.",
                    "pairs": {"012D_sep07": ("012D_20260907", "012D_20260709"), "134A_sep03": ("134A_20260903", "134A_20260822")}},
}
WORLDCOVER = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_{}_Map.tif"
REPO_SITES = Path(__file__).resolve().parents[1] / "sites"


def add_scenes_to_toml(name, spec):
    path = REPO_SITES / f"{name}.toml"
    text = path.read_text()
    used = sorted({k for pair in spec["pairs"].values() for k in pair})
    gcov = "[gcov]\n" + "".join(f'"{k}" = "../edouard/{SCENES[k]}"\n' for k in used)
    pairs = "".join(f'[pairs."{p}"]\nwet = "{w}"\ndry = "{d}"\nwet_time = "{TIMES[w]}"\ndry_time = "{TIMES[d]}"\n\n'
                    for p, (w, d) in spec["pairs"].items())
    path.write_text(text.replace("[gcov]\n", gcov, 1).replace("[pairs]\n", pairs, 1))


def fetch_reference_water(site, date="20260906"):
    """Only the static reference-water asset. The flood-extent asset of the same item is never downloaded."""
    day = f"{date[:4]}-{date[4:6]}-{date[6:]}"
    q = urllib.parse.urlencode({"collections": "GFM", "bbox": ",".join(map(str, site.bbox)), "limit": 100,
                                "datetime": f"{day}T00:00:00Z/{day}T23:59:59Z"})
    n = 0
    for f in get_json(f"{STAC}?{q}").get("features", []):
        stamp = f["properties"]["datetime"][:19].replace("-", "").replace(":", "")
        if "reference_water_mask" in f["assets"]:
            download(f["assets"]["reference_water_mask"]["href"], Path(site.operational_dir) / f"GFM_{stamp}_reference_water_mask.tif")
            n += 1
    return n


def fetch_scenes():
    for key, n in SCENES.items():
        q = urllib.parse.urlencode({"short_name": "NISAR_L2_GCOV_PROVISIONAL_V1", "granule_ur": n})
        item = get_json(f"{CMR}?{q}")["items"][0]
        url = next(u["URL"] for u in item["umm"]["RelatedUrls"]
                   if u.get("Type") == "GET DATA" and u["URL"].endswith(".h5") and u["URL"].startswith("https"))
        p = download(url, data_root() / "edouard" / f"{n}.h5", netrc=True)
        print(f"scene {key}: {p.stat().st_size / 1e9:.1f} GB", flush=True)


def static_checks(site):
    """Channel seeds and upland reference: lidar, land cover and reference water only."""
    grid = analysis_grid(site)
    dem = dem_on_grid(site.dem_path, grid)
    perm = reference_water(site.operational_dir, grid)
    coarse = ValleyLine.from_lonlat(grid, site.valley_line)
    dist0, _ = coarse.project(*grid.meshgrid())
    line = refine_centerline(coarse, perm & (dist0 < site.corridor_m), grid)
    dist, chain = line.project(*grid.meshgrid())
    gxy = [grid.to_xy(g.lon, g.lat) for g in site.gauges]
    _, g_chain = line.project(*map(np.array, zip(*gxy, strict=True)))
    hand = height_above_river(dem, dist, chain)
    lc = worldcover_class(worldcover_on_grid(data_root() / "worldcover", grid))
    supported = gauge_supported(chain, g_chain, 10000.0)
    corridor = (dist < site.corridor_m) & supported & (chain >= g_chain.min()) & (chain <= g_chain.max())
    print(f"{site.name}: crs {site.crs} bbox {site.bbox} grid {grid.shape}", flush=True)
    print(f"  reach {abs(g_chain[1] - g_chain[0]) / 1000:.1f} km; corridor {corridor.sum() * 0.25:,.0f} ha; dem nan share {np.isnan(dem[corridor]).mean():.3f}", flush=True)
    print(f"  reference water in corridor {(perm & corridor).sum() * 0.25:,.0f} ha ({(perm & corridor).sum()} px)", flush=True)
    upland = (lc == 1) & (hand > 12.0) & (dist < 15000.0)
    print(f"  upland reference px {upland.sum()} (need 500)", flush=True)
    shares = {k: round(float((lc[corridor] == v).mean()), 3) for k, v in (("tree", 1), ("wetland", 2), ("other", 0), ("open", 3))}
    print(f"  corridor land cover {shares}", flush=True)


def scene_checks(site):
    """Projection, grid limits, gauges inside, and the valid-sample mask over the corridor. No backscatter is read."""
    to_xy = Transformer.from_crs("EPSG:4326", site.crs, always_xy=True).transform
    gxy = [to_xy(g.lon, g.lat) for g in site.gauges]
    line = [to_xy(*p) for p in site.valley_line]
    for k in site.gcov:
        with h5py.File(site.gcov_path(k), "r") as h:
            g = h["science/LSAR/GCOV/grids/frequencyA"]
            xs, ys = g["xCoordinates"][:], g["yCoordinates"][:]
            epsg = int(g["projection"].attrs["epsg_code"])
            terms = [t for t in ("HHHH", "HVHV") if t in g]
            inside = [xs[0] <= x <= xs[-1] and ys[-1] <= y <= ys[0] for x, y in gxy]
            x0, x1 = min(p[0] for p in line) - 4000, max(p[0] for p in line) + 4000
            y0, y1 = min(p[1] for p in line) - 4000, max(p[1] for p in line) + 4000
            c0, c1 = np.searchsorted(xs, x0), np.searchsorted(xs, x1)
            r0, r1 = np.searchsorted(-ys, -y1), np.searchsorted(-ys, -y0)
            mask = g["mask"][r0:r1:5, c0:c1:5] if c1 > c0 and r1 > r0 else np.array([0])
            valid = float(((mask > 0) & (mask < 255)).mean())
        ok = epsg == int(site.crs.split(":")[1]) and all(inside) and len(terms) == 2 and valid >= 0.9
        print(f"  {k}: epsg {epsg} terms {terms} gauges inside {inside} valid-mask share over reach box {valid:.3f} -> {'PASS' if ok else 'FAIL'}", flush=True)


def main():
    for name, spec in SITES.items():
        if not (REPO_SITES / f"{name}.toml").exists():
            create_site(name, spec["gauges"], "2026-06-25T00:00:00Z", "2026-10-01T00:00:00Z", spec["description"])
            add_scenes_to_toml(name, spec)
        site = load_site(name)
        print(f"{name}: gauges {[(g.name, g.id, g.datum_ft, g.navd88_offset_ft) for g in site.gauges]}", flush=True)
        print(f"  reference-water files: {fetch_reference_water(site)}", flush=True)
        south, west = site.bbox[1], site.bbox[0]
        print(f"  needs WorldCover tile {'N27' if south < 30 else 'N30'}W096 (west {west})", flush=True)
    for tile in ("N30W096", "N27W096"):
        download(WORLDCOVER.format(tile), data_root() / "worldcover" / f"ESA_WorldCover_10m_2021_v200_{tile}_Map.tif")
    fetch_scenes()
    for name in SITES:
        site = load_site(name)
        static_checks(site)
        scene_checks(site)
    print("SETUP DONE", flush=True)


if __name__ == "__main__":
    main()
