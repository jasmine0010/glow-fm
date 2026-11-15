"""Set up the overbank test (research/OVERBANK_PROTOCOL.md) without reading any radar backscatter, flood layer or truth.

Uses gauges, lidar, WorldCover, GFM's static reference water, each scene's projection and valid-sample mask, and IMERG rainfall.
Passes are chosen by the rule in SECOND_EVENT_PROTOCOL.md section 2(b). Writes research/overbank_scenes.json and overbank_rain.json.
"""

import json
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
from pyproj import Transformer

sys.path.insert(0, str(Path(__file__).parent))
import rain_imerg
from setup_edouard import WORLDCOVER, fetch_reference_water
from setup_v4_test import FRAME, open_remote

from hidden_floods.config import REPO_ROOT, data_root, load_site
from hidden_floods.fetch import download
from hidden_floods.frozen import reference_water
from hidden_floods.grid import grid_from_lonlat_bbox
from hidden_floods.io.dem import dem_on_grid, fetch_3dep
from hidden_floods.io.gauges import usgs_series
from hidden_floods.pipeline import analysis_grid
from hidden_floods.selfcal import gauge_supported
from hidden_floods.sitegen import create_site
from hidden_floods.stack import parse, track_scenes
from hidden_floods.trust import worldcover_class, worldcover_on_grid
from hidden_floods.truth import ValleyLine, refine_centerline

# Tidal gauges and gauges below a dam are left out, because a straight water surface can't span them.
RIVERS = {
    "satilla": {"gauges": ["02226362", "02226500", "02228000"], "tracks": [("026D", "073"), ("047A", "017"), ("098D", "073")], "left_out": "Woodbine (tidal)"},
    "ochlockonee": {"gauges": ["02327355", "02327500", "02328522", "02329000"], "tracks": [("026D", "073"), ("148A", "017")], "left_out": "Bloxham (below Lake Talquin)"},
    "alapaha": {"gauges": ["02316000", "02317500", "02317620"], "tracks": [("026D", "073"), ("047A", "017"), ("148A", "017")], "left_out": "none"},
    "withlacoochee": {"gauges": ["02317755", "02318500", "02319000", "02319394"], "tracks": [("026D", "073"), ("047A", "017"), ("148A", "017")], "left_out": "none"},
    "st_marys": {"gauges": ["02231000", "02231175"], "tracks": [("098D", "073"), ("047A", "017")], "left_out": "Kingsland (tidal)"},
}
FT = 0.3048
SITES_DIR = REPO_ROOT / "sites"
OUT, RAIN = REPO_ROOT / "research" / "overbank_scenes.json", REPO_ROOT / "research" / "overbank_rain.json"
GFM_DATES = ("20261015", "20261014", "20261016", "20261013", "20261017", "20261019", "20261010", "20261007", "20261003")
MONTHS = {8: "aug", 9: "sep", 10: "oct", 11: "nov"}


def when(s):
    return datetime.fromisoformat(s.replace("Z", ""))


def fetch_tile(tile):
    """Download one WorldCover tile, replacing any copy whose size differs from the server's, such as one left by an interrupted run."""
    url, path = WORLDCOVER.format(tile), data_root() / "worldcover" / f"ESA_WorldCover_10m_2021_v200_{tile}_Map.tif"
    head = subprocess.run(["curl", "-sIL", "--fail", url], check=True, capture_output=True, text=True).stdout
    size = int(re.findall(r"content-length:\s*(\d+)", head, re.IGNORECASE)[-1])
    if path.exists() and path.stat().st_size != size:
        print(f"{tile}: replacing a partial file ({path.stat().st_size} of {size} bytes)", flush=True)
        path.unlink()
    download(url, path)
    if path.stat().st_size != size:
        raise RuntimeError(f"{tile}: got {path.stat().st_size} bytes, expected {size}")


def stages(site, t):
    out = {}
    for g in site.gauges:
        try:
            out[g.id] = float(usgs_series(site.gauges_dir, g).at(t)) * FT
        except ValueError:
            pass
    return out


def scene_meta(site, scene):
    """Projection and valid-sample share over the reach, in the scene's own projection. No backscatter is read."""
    with open_remote(scene) as h:
        g = h[FRAME]
        epsg = int(g["projection"].attrs["epsg_code"])
        to_xy = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True).transform
        line = [to_xy(*p) for p in site.valley_line]
        xs, ys = g["xCoordinates"][:], g["yCoordinates"][:]
        terms = all(t in g for t in ("HHHH", "HVHV"))
        x0, x1 = min(p[0] for p in line) - 4000, max(p[0] for p in line) + 4000
        y0, y1 = min(p[1] for p in line) - 4000, max(p[1] for p in line) + 4000
        c0, c1, r0, r1 = np.searchsorted(xs, x0), np.searchsorted(xs, x1), np.searchsorted(-ys, -y1), np.searchsorted(-ys, -y0)
        mask = g["mask"][r0:r1:25, c0:c1:25] if c1 > c0 and r1 > r0 else np.array([0])
        valid = float(((mask > 0) & (mask < 255)).mean())
    return epsg, terms, valid


def select_track(site, track, frame):
    """Rule 2(b): wet is the pass with the highest mean stage above its dry value; dry is the lowest mean stage within 60 days."""
    scenes = track_scenes(site.bbox, track, frame, "2026-08-01T00:00:00Z", "2026-11-05T00:00:00Z")
    st = {s.time: stages(site, s.time) for s in scenes}
    best = None
    for s in scenes:
        ids = list(st[s.time])
        pool = [x for x in scenes if x.time != s.time and abs(when(x.time) - when(s.time)) <= timedelta(days=60) and all(i in st[x.time] for i in ids)]
        if len(ids) < 2 or not pool:
            continue
        dry = min(pool, key=lambda x: np.mean([st[x.time][i] for i in ids]))
        rises = {i: round(st[s.time][i] - st[dry.time][i], 2) for i in ids}
        mean = float(np.mean(list(rises.values())))
        if max(rises.values()) > 1.0 and (best is None or mean > best["mean_rise_m"]):
            best = {"wet": s, "dry": dry, "rises_m": rises, "mean_rise_m": round(mean, 2)}
    return best


def fetch_dem(name):
    site = load_site(name)
    if site.dem_path.exists():
        return
    for attempt in range(6):                     # the 3DEP service returns 502 at times, so retry the whole fetch
        try:
            fetch_3dep(grid_from_lonlat_bbox(site.bbox, site.crs, 10.0, snap=50.0), site.dem_path, tile_px=500, retries=8)
            print(f"{name}: lidar ready", flush=True)
            return
        except OSError as e:
            print(f"{name}: 3DEP attempt {attempt + 1} failed: {e!r}", flush=True)
            if attempt == 5:
                raise
            time.sleep(120)


def static_shares(site):
    """Land cover in the gauge-supported corridor. Lidar, land cover and reference water only."""
    grid = analysis_grid(site)
    dem = dem_on_grid(site.dem_path, grid)
    perm = reference_water(site.operational_dir, grid)
    coarse = ValleyLine.from_lonlat(grid, site.valley_line)
    dist0, _ = coarse.project(*grid.meshgrid())
    line = refine_centerline(coarse, perm & (dist0 < site.corridor_m), grid)
    dist, chain = line.project(*grid.meshgrid())
    gxy = [grid.to_xy(g.lon, g.lat) for g in site.gauges]
    _, g_chain = line.project(*map(np.array, zip(*gxy, strict=True)))
    lc = worldcover_class(worldcover_on_grid(data_root() / "worldcover", grid))
    corridor = (dist < site.corridor_m) & gauge_supported(chain, g_chain, 10000.0) & (chain >= g_chain.min()) & (chain <= g_chain.max())
    shares = {k: round(float((lc[corridor] == v).mean()), 3) for k, v in (("tree", 1), ("wetland", 2), ("other", 0), ("open", 3))}
    return {"corridor_ha": float(corridor.sum() * 0.25), "dem_nan_share": round(float(np.isnan(dem[corridor]).mean()), 3), "reference_water_ha": float((perm & corridor).sum() * 0.25), "land_cover": shares, "forest_share": round(shares["tree"] + shares["wetland"], 3)}


def imerg_rain(site, t):
    """IMERG totals over the study box before one pass, using the same reads and rule as research/RAINFALL.md."""
    end = when(t)
    i0, j0 = rain_imerg.cell(site.bbox[0], site.bbox[1])
    i1, j1 = rain_imerg.cell(site.bbox[2], site.bbox[3])
    names = {s: n for s, n in rain_imerg.list_granules(end - timedelta(hours=73), end).items() if end - timedelta(hours=72) <= s < end}
    clon, clat = -180 + 0.05 + 0.1 * (i0 + np.arange(i1 - i0 + 1)), -90 + 0.05 + 0.1 * (j0 + np.arange(j1 - j0 + 1))
    mask = np.outer((clon >= site.bbox[0]) & (clon <= site.bbox[2]), (clat >= site.bbox[1]) & (clat <= site.bbox[3]))

    def one(name):
        for attempt in range(4):
            try:
                a = np.array(rain_imerg.read_box(name, i0, i1, j0, j1), float)
                return np.nanmean(np.where(a < -9000, np.nan, a)[mask])
            except (RuntimeError, ValueError, OSError):
                if attempt == 3:
                    raise
                time.sleep(5)

    with ThreadPoolExecutor(6) as pool:
        box = dict(zip(names, pool.map(one, names.values()), strict=True))
    h24, h72 = rain_imerg.totals(box, end, 24), rain_imerg.totals(box, end, 72)
    return {"rain_24h_mm": h24, "rain_72h_mm": h72, "half_hours": len(box), "rainy": rain_imerg.rainy(h24, h72)}


def main():
    for tile in ("N30W084", "N30W087"):
        fetch_tile(tile)
    listing = {}
    for name, spec in RIVERS.items():
        path = SITES_DIR / f"{name}.toml"
        if not path.exists():
            create_site(name, spec["gauges"], "2026-05-15T00:00:00Z", "2026-11-05T00:00:00Z", f"Isaias-period rise, {name}. Held-out overbank test.", fetch_dem=False)
        site = load_site(name)
        picks = []
        for track, frame in spec["tracks"]:
            b = select_track(site, track, frame)
            if b is None:
                print(f"{name} {track}/{frame}: no qualifying pass", flush=True)
                continue
            picks.append({"track": track, "frame": frame, **b})
        picks.sort(key=lambda p: -p["mean_rise_m"])
        crs = None
        passes = {}
        for p in picks:
            wet, dry = p["wet"], p["dry"]
            epsg, terms, valid_w = scene_meta(site, wet)
            if crs and f"EPSG:{epsg}" != crs:      # the site's projection comes from its first pass that qualifies
                print(f"{name} {p['track']}: projection EPSG:{epsg} differs from the primary {crs}, so the frozen reader can't use it", flush=True)
                continue
            _, terms_d, valid_d = scene_meta(site, dry)
            t = when(wet.time)
            pair = f"{p['track']}_{MONTHS[t.month]}{t.day:02d}"
            ok = terms and terms_d and min(valid_w, valid_d) >= 0.6
            print(f"{name} {pair}: EPSG:{epsg} wet {wet.time} dry {dry.time} rises {p['rises_m']} mean {p['mean_rise_m']} valid {valid_w:.2f}/{valid_d:.2f} {'PASS' if ok else 'FAIL'}", flush=True)
            if ok:
                crs = crs or f"EPSG:{epsg}"
                passes[pair] = {"track": p["track"], "frame": p["frame"], "wet": wet.name, "dry": dry.name, "wet_time": wet.time, "dry_time": dry.time, "rises_m": p["rises_m"], "mean_rise_m": p["mean_rise_m"], "valid_share": [round(valid_w, 3), round(valid_d, 3)]}
        if not passes:
            print(f"{name}: dropped, no qualifying pass", flush=True)
            continue
        text = path.read_text()
        if "[pairs." not in text:
            keys = {}
            for v in passes.values():
                for role in ("wet", "dry"):
                    keys[v[role]] = f"{role}_{v['track']}_{parse(v[role])['time'][:10].replace('-', '')}"
            gcov = "[gcov]\n" + "".join(f'"{k}" = "{n}"\n' for n, k in keys.items())
            pairs = "".join(f'[pairs."{pn}"]\nwet = "{keys[v["wet"]]}"\ndry = "{keys[v["dry"]]}"\nwet_time = "{v["wet_time"]}"\ndry_time = "{v["dry_time"]}"\n\n' for pn, v in passes.items())
            lines = text.replace("[gcov]\n", gcov, 1).replace("[pairs]\n", pairs, 1).split("\n")
            path.write_text("\n".join(f'crs = "{crs}"' if ln.startswith("crs = ") else ln for ln in lines))
        listing[name] = {"left_out_gauges": spec["left_out"], "crs": crs, "passes": passes}
    print("sites written; fetching lidar", flush=True)
    with ThreadPoolExecutor(3) as pool:
        list(pool.map(fetch_dem, listing))
    rain = {}
    rain_imerg.CACHE.mkdir(parents=True, exist_ok=True)
    first = next(iter(listing.values()))["passes"]
    first_time = when(next(iter(first.values()))["wet_time"])
    rain_imerg.curl(rain_imerg.OPENDAP + next(iter(rain_imerg.list_granules(first_time - timedelta(hours=1), first_time).values())) + ".dmr", seed=True)
    try:
        for name, info in listing.items():
            site = load_site(name)
            got = 0
            for d in GFM_DATES:
                got = fetch_reference_water(site, d)
                if got:
                    print(f"{name}: reference water from {d}, {got} files", flush=True)
                    break
            info["reference_water_files"] = got
            info["static"] = static_shares(site) if got else None
            print(f"{name}: {info['static']}", flush=True)
            start, end = "2026-05-15T00:00:00Z", "2026-11-05T00:00:00Z"
            for pair, v in info["passes"].items():
                tw = when(v["wet_time"])
                lo, hi = (tw - timedelta(days=60)).isoformat() + "Z", (tw + timedelta(days=60)).isoformat() + "Z"
                scenes = track_scenes(site.bbox, v["track"], v["frame"], max(lo, start), min(hi, end))
                v["scenes"] = [{"name": s.name, "track": s.track, "frame": s.frame, "time": s.time, "url": s.url} for s in scenes]
                rain.setdefault(name, {})[pair] = imerg_rain(site, v["wet_time"])
                print(f"{name} {pair}: {len(scenes)} baseline-window scenes; rain {rain[name][pair]}", flush=True)
    finally:
        rain_imerg.JAR.unlink(missing_ok=True)
    OUT.write_text(json.dumps(listing, indent=1))
    RAIN.write_text(json.dumps(rain, indent=1))
    print("OVERBANK SETUP DONE", flush=True)


if __name__ == "__main__":
    main()
