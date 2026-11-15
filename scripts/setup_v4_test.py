"""Set up the v4 frozen test on three new rivers without reading any radar backscatter, flood layer or truth.

Fetches gauges, lidar, GFM reference water (static layer only) and WorldCover. From each scene it reads only the
projection, grid limits and valid-sample mask. It also records the baseline scene list for the freeze.
"""

import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import h5py
import numpy as np
from pyproj import Transformer

sys.path.insert(0, str(Path(__file__).parent))
from setup_edouard import WORLDCOVER, fetch_reference_water, static_checks

from hidden_floods.config import REPO_ROOT, data_root, load_site
from hidden_floods.fetch import download
from hidden_floods.grid import grid_from_lonlat_bbox
from hidden_floods.io.dem import fetch_3dep
from hidden_floods.sitegen import create_site
from hidden_floods.stack import RangeFile, parse, signed_url, track_scenes

RIVERS = {
    "pee_dee": {"gauges": ["02130000", "02130561", "02131000", "02131010", "02131210"], "pair": "098D_jul27", "description": "July 2026 front, Pee Dee River SC. Held-out v4 test.",
                "wet": "NISAR_L2_PR_GCOV_026_098_D_071_4005_DHDH_A_20260727T001045_20260727T001120_P05023_N_F_J_001",
                "dry": "NISAR_L2_PR_GCOV_024_098_D_071_4005_DHDH_A_20260703T001046_20260703T001121_P05023_N_F_J_001", "gfm": ["20260727", "20260725", "20260729"]},
    "neuse": {"gauges": ["02088119", "02089000", "02089500", "02091814"], "pair": "090A_jul26", "description": "July 2026 front, Neuse River NC. Held-out v4 test.",
              "wet": "NISAR_L2_PR_GCOV_026_090_A_019_4005_DHDH_A_20260726T102153_20260726T102230_P05023_N_F_J_001",
              "dry": "NISAR_L2_PR_GCOV_030_090_A_019_4005_DHDH_A_20260912T102151_20260912T102229_P05023_N_F_J_001", "gfm": ["20260727", "20260725", "20260729"]},
    "lower_sabine": {"gauges": ["08026000", "08028500", "08030500"], "pair": "134A_jul17", "description": "Mid-July 2026 rain, lower Sabine River TX/LA. Held-out v4 test.",
                     "wet": "NISAR_L2_PR_GCOV_025_134_A_017_4005_DHDH_A_20260717T113544_20260717T113618_P05023_N_F_J_001",
                     "dry": "NISAR_L2_PR_GCOV_028_134_A_017_4005_DHDH_A_20260822T113542_20260822T113616_P05023_N_F_J_001", "gfm": ["20260717", "20260718", "20260716", "20260715", "20260719"]},
}
SITES_DIR = REPO_ROOT / "sites"
SCENE_LIST = REPO_ROOT / "research" / "v4_test_scenes.json"
FRAME = "science/LSAR/GCOV/grids/frequencyA"


def scene_url(name, bbox):
    p = parse(name)
    t = datetime.fromisoformat(p["time"].replace("Z", ""))
    day0, day1 = (t - timedelta(hours=2)).isoformat() + "Z", (t + timedelta(hours=2)).isoformat() + "Z"
    return next(s for s in track_scenes(bbox, p["track"], p["frame"], day0, day1) if s.name == name)


def open_remote(scene):
    return h5py.File(RangeFile(signed_url(scene.url, data_root() / "stack" / "cookies.txt")), "r")


def epsg_of(scene) -> int:
    with open_remote(scene) as h:
        return int(h[FRAME]["projection"].attrs["epsg_code"])


def add_scenes(name, spec, crs):
    path = SITES_DIR / f"{name}.toml"
    text = path.read_text()
    w, d = parse(spec["wet"]), parse(spec["dry"])
    wk, dk = f"wet_{w['time'][:10].replace('-', '')}", f"dry_{d['time'][:10].replace('-', '')}"
    gcov = f'[gcov]\n"{wk}" = "{spec["wet"]}"\n"{dk}" = "{spec["dry"]}"\n'
    pair = f'[pairs."{spec["pair"]}"]\nwet = "{wk}"\ndry = "{dk}"\nwet_time = "{w["time"]}"\ndry_time = "{d["time"]}"\n\n'
    lines = text.replace("[gcov]\n", gcov, 1).replace("[pairs]\n", pair, 1).split("\n")
    lines = [f'crs = "{crs}"' if ln.startswith("crs = ") else ln for ln in lines]
    path.write_text("\n".join(lines))


def scene_checks(site, scene):
    """Projection, grid limits, gauges inside, valid-sample mask over the reach. No backscatter is read."""
    to_xy = Transformer.from_crs("EPSG:4326", site.crs, always_xy=True).transform
    gxy = [to_xy(g.lon, g.lat) for g in site.gauges]
    line = [to_xy(*p) for p in site.valley_line]
    with open_remote(scene) as h:
        g = h[FRAME]
        xs, ys = g["xCoordinates"][:], g["yCoordinates"][:]
        epsg = int(g["projection"].attrs["epsg_code"])
        terms = [t for t in ("HHHH", "HVHV") if t in g]
        inside = [bool(xs[0] <= x <= xs[-1] and ys[-1] <= y <= ys[0]) for x, y in gxy]
        x0, x1 = min(p[0] for p in line) - 4000, max(p[0] for p in line) + 4000
        y0, y1 = min(p[1] for p in line) - 4000, max(p[1] for p in line) + 4000
        c0, c1, r0, r1 = np.searchsorted(xs, x0), np.searchsorted(xs, x1), np.searchsorted(-ys, -y1), np.searchsorted(-ys, -y0)
        mask = g["mask"][r0:r1:25, c0:c1:25] if c1 > c0 and r1 > r0 else np.array([0])
        valid = float(((mask > 0) & (mask < 255)).mean())
    ok = epsg == int(site.crs.split(":")[1]) and all(inside) and len(terms) == 2 and valid >= 0.9
    print(f"  {scene.time[:10]}: epsg {epsg} terms {terms} gauges inside {inside} valid-mask share over reach box {valid:.3f} -> {'PASS' if ok else 'FAIL'}", flush=True)
    return ok


def main():
    for tile in ("N33W081", "N33W078"):
        download(WORLDCOVER.format(tile), data_root() / "worldcover" / f"ESA_WorldCover_10m_2021_v200_{tile}_Map.tif")
    print("worldcover ready", flush=True)
    listing = {}
    for name, spec in RIVERS.items():
        path = SITES_DIR / f"{name}.toml"
        wet_time = datetime.fromisoformat(parse(spec["wet"])["time"].replace("Z", ""))
        if not path.exists():
            site = create_site(name, spec["gauges"], "2026-05-15T00:00:00Z", "2026-11-01T00:00:00Z", spec["description"], fetch_dem=False)
            epsg = epsg_of(scene_url(spec["wet"], site.bbox))
            add_scenes(name, spec, f"EPSG:{epsg}")
        site = load_site(name)
        if not site.dem_path.exists():
            for attempt in range(5):                # the 3DEP service returns 502 at times, so retry the whole fetch
                try:
                    fetch_3dep(grid_from_lonlat_bbox(site.bbox, site.crs, 10.0, snap=50.0), site.dem_path, tile_px=500, retries=8)
                    break
                except OSError as e:
                    print(f"  3DEP attempt {attempt + 1} failed: {e!r}", flush=True)
                    if attempt == 4:
                        raise
                    time.sleep(120)
        print(f"{name}: crs {site.crs} gauges {[(g.name, g.id, g.datum_ft, g.navd88_offset_ft) for g in site.gauges]}", flush=True)
        files = 0
        for d in spec["gfm"]:
            files += fetch_reference_water(site, d)
            if files:
                print(f"  reference water from {d}: {files} files", flush=True)
                break
        p = parse(spec["wet"])
        start, end = (wet_time - timedelta(days=60)).isoformat() + "Z", (wet_time + timedelta(days=60)).isoformat() + "Z"
        scenes = track_scenes(site.bbox, p["track"], p["frame"], start, end)
        names = {s.name for s in scenes}
        print(f"  {len(scenes)} scenes {[s.time[:10] for s in scenes]}; wet listed {spec['wet'] in names}; dry listed {spec['dry'] in names}", flush=True)
        listing[name] = {"pair": spec["pair"], "wet": spec["wet"], "dry": spec["dry"], "scenes": [{"name": s.name, "track": s.track, "frame": s.frame, "time": s.time, "url": s.url} for s in scenes]}
        static_checks(site)
        for s in scenes:
            if s.name in (spec["wet"], spec["dry"]):
                scene_checks(site, s)
    SCENE_LIST.write_text(json.dumps(listing, indent=1))
    print("V4 SETUP DONE", flush=True)


if __name__ == "__main__":
    main()
