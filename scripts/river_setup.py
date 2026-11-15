"""Shared steps for adding a US river to the dashboard (scripts/setup_st_johns.py, scripts/auto_rivers.py).

A river needs: gauges on one main stem with their heights above NAVD88, the river line as its valley, NWS flood
stages where there are any, land cover, lidar and stage records. These helpers fetch each from public services and
cache it under the data root. None of them reads radar or changes a test.
"""

import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from itertools import pairwise

import numpy as np
import rasterio
from pyproj import Transformer

from hidden_floods.config import data_root
from hidden_floods.fetch import USER_AGENT, USGS_OGC
from hidden_floods.grid import Grid, grid_from_lonlat_bbox
from hidden_floods.io.dem import fetch_3dep
from hidden_floods.trust import worldcover_on_grid

NLDI = "https://api.water.usgs.gov/nldi/linked-data/nwissite"
NWPS = "https://api.water.noaa.gov/nwps/v1/gauges"
WORLDCOVER = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_{}_Map.tif"
STEP_M = 300.0     # spacing of a valley line's points


def get(url, timeout=300, tries=6):
    """A public service's reply; waits and tries again when the service says it's asked too often (HTTP 429)."""
    for k in range(tries):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as exc:
            if exc.code != 429 or k == tries - 1:
                raise
            time.sleep(15 * (k + 1))
    return None


def km(a, b):
    return math.hypot((b[0] - a[0]) * 111.32 * math.cos(math.radians(a[1])), (b[1] - a[1]) * 110.57)


def main_stem(usgs, nav, distance_km):
    """The main stem from a gauge, up (nav="UM") or down ("DM") the river, from USGS river lines, upstream to downstream."""
    g = json.loads(get(f"{NLDI}/{usgs}/navigation/{nav}/flowlines?distance={distance_km}"))
    segs = []
    for f in g.get("features", []):
        geom = f["geometry"]
        parts = geom["coordinates"] if geom["type"] == "MultiLineString" else [geom["coordinates"]]
        segs += [[tuple(p[:2]) for p in part] for part in parts if len(part) > 1]
    if not segs:
        return []
    key = lambda p: (round(p[0], 5), round(p[1], 5))
    starts, ends = {key(s[0]): s for s in segs}, {key(s[-1]) for s in segs}
    head = next((s for s in segs if key(s[0]) not in ends), segs[0])
    line, seen = list(head), {id(head)}
    while key(line[-1]) in starts and id(starts[key(line[-1])]) not in seen:
        nxt = starts[key(line[-1])]
        seen.add(id(nxt))
        line += nxt[1:]
    return line


def stem_gauges(usgs, distance_km):
    """USGS sites on the main stem within distance_km up and down from a gauge, including it."""
    ids = {usgs}
    for nav in ("UM", "DM"):
        try:
            g = json.loads(get(f"{NLDI}/{usgs}/navigation/{nav}/nwissite?distance={distance_km}"))
        except Exception:  # noqa: BLE001, S112  (public sources fail in many ways; the river moves on)
            continue
        ids |= {f["properties"]["identifier"] for f in g.get("features", []) if f["properties"].get("identifier", "").startswith("USGS-")}
    return sorted(ids)


def along(line, p):
    """Index of the line's point nearest p."""
    return min(range(len(line)), key=lambda i: km(line[i], p))


def valley(line, top, bottom, extra_km=3.0):
    """The river line from extra_km above the point top to extra_km below the point bottom, a point every STEP_M."""
    i, j = along(line, top), along(line, bottom)
    up, down = line[:i][::-1], line[j + 1:]
    pad = lambda seq: [p for k, p in enumerate(seq) if sum(km(a, b) for a, b in pairwise(seq[:k + 1])) <= extra_km]
    run = pad(up)[::-1] + line[i:j + 1] + pad(down)
    out, walked = [], 0.0
    for k, p in enumerate(run):
        if k == 0 or walked >= STEP_M / 1000 or k == len(run) - 1:
            out.append(p)
            walked = 0.0
        if k < len(run) - 1:
            walked += km(p, run[k + 1])
    return out


def length_km(line):
    return sum(km(a, b) for a, b in pairwise(line))


def datum_from_readings(usgs, days=30):
    """NAVD88 datum (ft) of a gauge that publishes both gage height (00065) and water elevation above NAVD88 (63160):
    the median difference of paired readings over the last `days`, which must agree to within 0.05 ft. None if it
    doesn't publish both."""
    now = datetime.now(UTC)
    span = f"{now - timedelta(days=days):%Y-%m-%dT%H:%M:%SZ}/{now:%Y-%m-%dT%H:%M:%SZ}"
    q = lambda p: {f["properties"]["time"]: f["properties"]["value"] for f in json.loads(get(
        f"{USGS_OGC}/continuous/items?" + urllib.parse.urlencode({"f": "json", "monitoring_location_id": usgs, "parameter_code": p, "time": span, "limit": 10000})))["features"]}
    stage, elev = q("00065"), q("63160")
    diffs = sorted(float(elev[t]) - float(stage[t]) for t in stage.keys() & elev.keys() if stage[t] is not None and elev[t] is not None)
    if len(diffs) < 100 or diffs[-1] - diffs[0] > 0.05:
        return None
    return round(diffs[len(diffs) // 2], 3)


def nws_minor_stage(lid):
    """An NWS gauge's minor flood stage (ft of gage height) and its USGS site, or (None, None)."""
    d = json.loads(get(f"{NWPS}/{lid}"))
    stage = (((d.get("flood") or {}).get("categories") or {}).get("minor") or {}).get("stage")
    return (float(stage) if stage is not None and stage > 0 else None), d.get("usgsId")


def nws_gauges():
    """Every NWS gauge (lid, name, place), asked for once a week and kept under the data root: NWPS turns away many
    small area searches in a row, but answers one request for the whole list."""
    path = data_root() / "nws_gauges.json"
    if not path.exists() or time.time() - path.stat().st_mtime > 7 * 86400:
        gauges = json.loads(get(NWPS, timeout=300))["gauges"]
        path.write_text(json.dumps([{k: g.get(k) for k in ("lid", "name", "latitude", "longitude")} for g in gauges]))
    return json.loads(path.read_text())


def nws_gauge(usgs, lon, lat, r_km=5.0, tries=5):
    """The NWS gauge (its NWPS record) that reports for a USGS site, among the `tries` NWS gauges nearest it within
    r_km, or None."""
    near = sorted((km((lon, lat), (g["longitude"], g["latitude"])), g["lid"]) for g in nws_gauges() if g["longitude"] is not None)
    for dist, lid in near[:tries]:
        if dist > r_km:
            break
        time.sleep(1.0)
        d = json.loads(get(f"{NWPS}/{lid}"))
        if d.get("usgsId") == usgs.removeprefix("USGS-"):
            return d
    return None


def usgs_latest_stage(usgs):
    """A USGS site's latest gage height (ft), or None."""
    f = json.loads(get(f"{USGS_OGC}/latest-continuous/items?" + urllib.parse.urlencode(
        {"f": "json", "monitoring_location_id": usgs, "parameter_code": "00065"})))["features"]
    return float(f[0]["properties"]["value"]) if f and f[0]["properties"]["value"] is not None else None


def nws_level(gauge):
    """A site gauge's NWS minor flood stage in ft of its own gage height, with how it was read.

    NWS lists some gauges' levels as water elevations rather than gage height: those whose name ends "(in NAVD88)",
    and others whose readings sit a datum above USGS's gage height. Their level is turned into gage height with the
    gauge's own NAVD88 datum from the site file (datum_ft + navd88_offset_ft), which is how the dashboard turns gage
    height back into water height, so the level lands on the same water surface NWS gives. A gauge whose readings
    match neither way is left without a level, as is one NWS gives no flood stage."""
    d = nws_gauge(gauge.id, gauge.lon, gauge.lat)
    if d is None:
        return {"lid": None, "stage_ft": None, "how": "no NWS gauge reports for this USGS site"}
    minor = (((d.get("flood") or {}).get("categories") or {}).get("minor") or {}).get("stage")
    out = {"lid": d["lid"], "nws_name": d["name"], "nws_minor": minor, "stage_ft": None}
    if minor is None or minor <= 0:
        return out | {"how": "NWS gives no minor flood stage"}
    obs = ((d.get("status") or {}).get("observed") or {}).get("primary")
    obs = None if obs is None or obs <= -999 else float(obs)
    gh = usgs_latest_stage(gauge.id)
    datum = gauge.datum_ft + gauge.navd88_offset_ft
    out |= {"nws_reading_ft": obs, "usgs_gage_height_ft": gh, "datum_navd88_ft": round(datum, 3)}
    if "(in NAVD88)" in d["name"]:
        return out | {"stage_ft": round(minor - datum, 2), "how": "NWS lists it as NAVD88 elevation; the gauge's datum is taken off"}
    if obs is None or gh is None or abs(obs - gh) <= 0.5:
        return out | {"stage_ft": float(minor), "how": "NWS lists it in gage height"}
    if abs(obs - gh - datum) <= 1.0:
        return out | {"stage_ft": round(minor - datum, 2), "how": "NWS readings sit the gauge's NAVD88 datum above its gage height; the datum is taken off"}
    return out | {"how": "NWS readings match neither the gage height nor the gage height plus datum; left without a level"}


def save_nws_levels(name):
    """Every gauge's NWS minor flood stage (ft of gage height) for a river, saved to <data root>/<river>/nws_flood_levels.json,
    which scripts/build_dashboard.py reads ahead of the older research records."""
    from hidden_floods.config import load_site
    site = load_site(name)
    gauges = {}
    for g in site.gauges:
        gauges[g.id.removeprefix("USGS-")] = nws_level(g)
        print(name, g.id, gauges[g.id.removeprefix("USGS-")], flush=True)
    levels = {gid: v["stage_ft"] for gid, v in gauges.items() if v["stage_ft"] is not None}
    (data_root() / name / "nws_flood_levels.json").write_text(json.dumps(
        {"source": "NWS NWPS, minor flood stage, in ft of gage height (scripts/river_setup.py save_nws_levels)", "levels": levels, "gauges": gauges}, indent=1))
    return levels


def worldcover_tiles(bbox):
    """Download the ESA WorldCover tiles covering bbox (west, south, east, north) into the data root, once each."""
    w, s, e, n = bbox
    got = []
    for la in range(int(math.floor(s / 3) * 3), int(math.floor(n / 3) * 3) + 1, 3):
        for lo in range(int(math.floor(w / 3) * 3), int(math.floor(e / 3) * 3) + 1, 3):
            tile = f"{'N' if la >= 0 else 'S'}{abs(la):02d}{'E' if lo >= 0 else 'W'}{abs(lo):03d}"
            out = data_root() / "worldcover" / f"ESA_WorldCover_10m_2021_v200_{tile}_Map.tif"
            if not out.exists():
                out.write_bytes(get(WORLDCOVER.format(tile), timeout=1800))
            got.append(out)
    return got


def corridor_lidar(site, line, km=8.0, tile_km=10.0):
    """USGS 3DEP lidar (bare earth, 10 m) for the river's corridor only, mosaicked into site.dem_path.

    The site's box is cut into tile_km tiles, and only the tiles within km of the river line (lon, lat points) are
    fetched, each with the frozen hidden_floods.io.dem.fetch_3dep. A winding river's box is mostly far from the river,
    and small requests ride out 3DEP's timeouts. Each tile is kept under <river>/dem/tiles/, so an interrupted run picks
    up where it stopped. Pixels in tiles left out are NaN, well outside the analysis corridor."""
    out = os.fspath(site.dem_path)
    if os.path.exists(out):
        return out
    grid = grid_from_lonlat_bbox(site.bbox, site.crs, 10.0, snap=50.0)
    to_xy = Transformer.from_crs(4326, site.crs, always_xy=True).transform
    pts = [to_xy(*p) for p in line]
    dense = np.array([(a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1]))
                      for a, b in pairwise(pts) for f in np.linspace(0, 1, max(2, int(math.hypot(b[0] - a[0], b[1] - a[1]) // 100) + 1))])
    step = round(tile_km * 1000 / grid.res)
    tiles_dir = data_root() / site.name / "dem" / "tiles"
    tiles_dir.mkdir(parents=True, exist_ok=True)
    wanted = []
    for r0 in range(0, grid.height, step):
        for c0 in range(0, grid.width, step):
            h, w = min(step, grid.height - r0), min(step, grid.width - c0)
            x0, y1 = grid.x0 + c0 * grid.res, grid.y0 - r0 * grid.res
            # distance from each line point to the tile's rectangle
            dx = np.maximum(np.maximum(x0 - dense[:, 0], dense[:, 0] - (x0 + w * grid.res)), 0)
            dy = np.maximum(np.maximum((y1 - h * grid.res) - dense[:, 1], dense[:, 1] - y1), 0)
            if np.hypot(dx, dy).min() <= km * 1000:
                wanted.append((r0, c0, Grid(grid.crs, x0, y1, grid.res, w, h)))
    print(f"lidar: {len(wanted)} of {-(-grid.height // step) * -(-grid.width // step)} tiles of {tile_km:g} km lie within {km:g} km of the river", flush=True)
    for k, (r0, c0, tile) in enumerate(wanted, 1):
        path = tiles_dir / f"r{r0:05d}_c{c0:05d}.tif"
        if path.exists():
            continue
        part = path.with_suffix(".part.tif")
        fetch_3dep(tile, part, tile_px=500, retries=12)
        os.replace(part, path)
        print(f"lidar tile {k}/{len(wanted)} {path.name}", flush=True)
    dem = np.full(grid.shape, np.nan, np.float32)
    for r0, c0, tile in wanted:
        with rasterio.open(tiles_dir / f"r{r0:05d}_c{c0:05d}.tif") as src:
            dem[r0:r0 + tile.height, c0:c0 + tile.width] = src.read(1)
    part = out + ".part.tif"
    with rasterio.open(part, "w", driver="GTiff", height=grid.height, width=grid.width, count=1, dtype="float32", crs=grid.crs,
                       transform=grid.transform, nodata=np.nan, compress="deflate", tiled=True, blockxsize=512, blockysize=512, BIGTIFF="IF_SAFER") as dst:
        dst.write(dem, 1)
    os.replace(part, out)
    return out


def worldcover_water_mask(site, name="GFM_WORLDCOVER2021_reference_water_mask.tif"):
    """Permanent water from ESA WorldCover 2021 (class 80) for a river with no GFM reference-water layer, written into
    its operational folder in the GFM reference-water mask's encoding (1 water, 0 land), on a 20 m grid over its box.

    The frozen hidden_floods.audit.truth_context reads every GFM_*_reference_water_mask.tif there as the river's
    permanent water, so lakes the river runs through aren't counted as flood. The file name says where it came from:
    it is WorldCover's water, not a GFM product, and gfm_mosaic (which reads GFM_<date>T*) never picks it up."""
    out = site.operational_dir / name
    if out.exists():
        return out
    worldcover_tiles(site.bbox)
    grid = grid_from_lonlat_bbox(site.bbox, site.crs, 20.0)
    water = (worldcover_on_grid(data_root() / "worldcover", grid) == 80).astype(np.uint8)
    out.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(out, "w", driver="GTiff", height=grid.height, width=grid.width, count=1, dtype="uint8", crs=grid.crs,
                       transform=grid.transform, nodata=255, compress="deflate") as dst:
        dst.write(water, 1)
    (site.operational_dir / "WORLDCOVER_WATER_README.txt").write_text(
        f"{name} is ESA WorldCover 2021 permanent water (class 80), not a GFM product. This river has no GFM reference-water\n"
        "layer, so scripts/river_setup.worldcover_water_mask wrote it in that layer's encoding (1 water, 0 land).\n")
    return out


def gfm_near(name, date, days=3):
    """Copernicus GFM scenes (flood extent, exclusion mask, reference water) over a river's box on its case date
    (YYYYMMDD) from the public EODC catalogue (the frozen hidden_floods.fetch.fetch_gfm), saved in its operational
    folder. With no Sentinel-1 flood map that day, the nearest day within `days` that has one. Returns the date used,
    or None. scripts/build_dashboard.py makes the same choice from what's saved, and names the date on the card."""
    from hidden_floods.config import load_site
    from hidden_floods.fetch import fetch_gfm
    site = load_site(name)
    for k in sorted(range(-days, days + 1), key=abs):
        d = f"{datetime.strptime(date, '%Y%m%d') + timedelta(days=k):%Y%m%d}"
        files = fetch_gfm(site.bbox, d, site.operational_dir)
        if any(f.name.endswith("_ensemble_flood_extent.tif") for f in files):
            print(name, "GFM", d, f"({len(files)} files)", flush=True)
            return d
    print(name, "GFM: no scene within", days, "days of", date, flush=True)
    return None


if __name__ == "__main__":
    # python scripts/river_setup.py nws-levels <river> [<river> ...]
    # python scripts/river_setup.py gfm <river>:<YYYYMMDD> [<river>:<YYYYMMDD> ...]
    if sys.argv[1:2] == ["nws-levels"]:
        for river in sys.argv[2:]:
            save_nws_levels(river)
    elif sys.argv[1:2] == ["gfm"]:
        for arg in sys.argv[2:]:
            gfm_near(*arg.split(":"))
