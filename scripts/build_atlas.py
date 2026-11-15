"""Builds the dashboard's blind-spot map: where river floodplains sit under trees, worldwide.

Floodplain: Copernicus CEMS GloFAS 100-year flood hazard map v2.1 (3 arc seconds), without permanent water or its flagged spurious depths.
Trees: ESA WorldCover 2021 tree cover and mangroves, read from the 80 m overview of each 10 m tile.
This shows where a flood could be hidden from an optical or C-band map. It doesn't show flooding. Downloads are cached in outputs/atlas.
"""
import io
import json
import math
import re
import sys
import time
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from rasterio.features import rasterize
from rasterio.transform import from_origin

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "outputs" / "atlas"
JRC = "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/CEMS-GLOFAS/flood_hazard/"
WC = "/vsicurl/https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_{}_Map.tif"
NE = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"
UA = {"User-Agent": "hidden-floods-research/0.1"}
OUT = ROOT / "app" / "data" / "atlas"

STEP = 0.025   # degrees per grid cell
NORTH, SOUTH = 85.0, -60.0
ROWS, COLS = round((NORTH - SOUTH) / STEP), round(360 / STEP)
WC_OVERVIEW = 4500
TREE_CLASSES = (10, 95)
PX_KM = 111.32 * 3 / 3600
# Classes for the map, as the share of the ground that is floodplain under trees.
BREAKS = (0.03, 0.08, 0.18, 0.35)
# Floodplain forest's green-teal, dark to light: orange means people on the site (app/style.css colour tokens).
COLORS = ((23, 79, 72), (31, 122, 104), (47, 174, 140), (79, 220, 176), (201, 251, 233))
MIN_ZOOM, MAX_ZOOM = 0, 6


def fetch(url, tries=6, timeout=180):
    for attempt in range(tries):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()
        except urllib.error.HTTPError as e:
            if e.code == 404 or attempt == tries - 1:
                raise
        except OSError:
            if attempt == tries - 1:
                raise
        time.sleep(5 * (attempt + 1))
    raise RuntimeError(url)


def cached(url, path):
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        data = fetch(url)
        temp = path.with_suffix(path.suffix + ".part")
        temp.write_bytes(data)
        temp.replace(path)
    return path


FAILED_LAND_COVER = set()


def read_land_cover(key):
    """Returns None where no tile exists, or when a read keeps failing, which is listed so the caller can leave that hazard tile for the next run."""
    url = WC.format(key)
    for attempt in range(8):
        try:
            with rasterio.open(url) as d:
                return d.read(1, out_shape=(WC_OVERVIEW, WC_OVERVIEW))
        except rasterio.errors.RasterioIOError as e:
            if any(s in str(e) for s in ("404", "does not exist", "No such file", "not recognized")):
                return None
            time.sleep(10 * (attempt + 1))
    FAILED_LAND_COVER.add(key)
    print("land cover failed", key, flush=True)
    return None


def wc_key(lat0, lon0):
    return f"{'N' if lat0 >= 0 else 'S'}{abs(lat0):02d}{'E' if lon0 >= 0 else 'W'}{abs(lon0):03d}"


def process_tile(name, spurious_name):
    done = WORK / "tiles" / f"{name}.npz"
    if done.exists():
        return name
    src = cached(f"{JRC}RP100/{name}_RP100_depth_reclass.tif", WORK / "jrc" / f"{name}.tif")
    with rasterio.open(src) as d:
        flood = d.read(1)
        t = d.transform
    keep = flood > 0
    if d.nodata is not None:
        keep &= flood != d.nodata
    keep &= flood <= 4
    del flood
    if spurious_name:
        sp = cached(f"{JRC}Spurious_Depths/{spurious_name}", WORK / "spurious" / spurious_name)
        with rasterio.open(sp) as d:
            mask = d.read(1)
            if mask.shape == keep.shape:
                keep &= (mask == 0) | (mask == (d.nodata if d.nodata is not None else 0))
    rows, cols = np.nonzero(keep)
    del keep
    if not len(rows):
        np.savez_compressed(done, cell=np.zeros(0, np.int64), flood=np.zeros(0, np.float32), tree=np.zeros(0, np.float32), missing=0.0)
        return name
    lat = t.f + (rows + 0.5) * t.e
    lon = t.c + (cols + 0.5) * t.a
    inside = (lat < NORTH) & (lat > SOUTH) & (lon >= -180) & (lon < 180)
    lat, lon = lat[inside], lon[inside]
    area = PX_KM ** 2 * np.cos(np.radians(lat))
    tree = np.zeros(len(lat), bool)
    known = np.zeros(len(lat), bool)
    lat3, lon3 = (np.floor(lat / 3) * 3).astype(int), (np.floor(lon / 3) * 3).astype(int)
    for la, lo in np.unique(np.c_[lat3, lon3], axis=0).tolist():
        here = (lat3 == la) & (lon3 == lo)
        wc = read_land_cover(wc_key(la, lo))
        if wc is None:
            if wc_key(la, lo) in FAILED_LAND_COVER:  # not saved, so the next run tries this hazard tile again
                return name
            continue
        i = np.clip(((la + 3 - lat[here]) / 3 * WC_OVERVIEW).astype(int), 0, WC_OVERVIEW - 1)
        j = np.clip(((lon[here] - lo) / 3 * WC_OVERVIEW).astype(int), 0, WC_OVERVIEW - 1)
        v = wc[i, j]
        tree[here] = np.isin(v, TREE_CLASSES)
        known[here] = v > 0
    r = ((NORTH - lat) / STEP).astype(np.int64)
    c = ((lon + 180) / STEP).astype(np.int64)
    cell, inverse = np.unique(r * COLS + c, return_inverse=True)
    np.savez_compressed(done, cell=cell, flood=np.bincount(inverse, area).astype(np.float32), tree=np.bincount(inverse, area * tree).astype(np.float32), missing=float(area[~known].sum()))
    return name


def assemble():
    (WORK / "tiles").mkdir(parents=True, exist_ok=True)
    listing = fetch(f"{JRC}RP100/").decode(errors="replace")
    names = sorted(set(re.findall(r'href="(ID\d+_[NS]\d+_[EW]\d+)_RP100_depth_reclass\.tif"', listing)))
    spur = fetch(f"{JRC}Spurious_Depths/").decode(errors="replace")
    spur_files = {m.group(1): m.group(0) for m in re.finditer(r'(ID\d+)_[^"<>]*\.tif', spur)}
    print(len(names), "flood-hazard tiles;", len(spur_files), "spurious-depth files", flush=True)
    t0, finished = time.time(), 0
    with ThreadPoolExecutor(4) as pool:
        jobs = {pool.submit(process_tile, n, spur_files.get(n.split("_")[0])): n for n in names}
        for job in as_completed(jobs):
            job.result()
            finished += 1
            if finished % 10 == 0:
                print(f"{finished}/{len(names)} tiles, {(time.time() - t0) / 60:.1f} min", flush=True)
    flood, tree = np.zeros((ROWS, COLS), np.float32), np.zeros((ROWS, COLS), np.float32)
    missing = 0.0
    for n in names:
        if not (WORK / "tiles" / f"{n}.npz").exists():
            print("hazard tile left out:", n, flush=True)
            continue
        z = np.load(WORK / "tiles" / f"{n}.npz")
        rr, cc = np.divmod(z["cell"], COLS)
        np.add.at(flood, (rr, cc), z["flood"])
        np.add.at(tree, (rr, cc), z["tree"])
        missing += float(z["missing"])
    return flood, tree, missing, len(names)


def summarize(flood, tree, missing, tiles):
    geo = json.loads(cached(f"{NE}ne_50m_admin_0_countries.geojson", WORK / "ne_countries.geojson").read_text(encoding="utf8"))
    names = [f["properties"]["ADMIN"] for f in geo["features"]]
    shapes = [(f["geometry"], k + 1) for k, f in enumerate(geo["features"]) if f["geometry"]]
    raster = rasterize(shapes, out_shape=(ROWS, COLS), transform=from_origin(-180, NORTH, STEP, STEP), fill=0, dtype="int16")
    fl = np.bincount(raster.ravel(), flood.ravel().astype(np.float64), len(names) + 1)
    tr = np.bincount(raster.ravel(), tree.ravel().astype(np.float64), len(names) + 1)
    countries = [{"name": names[k], "floodplain_km2": round(float(fl[k + 1])), "tree_km2": round(float(tr[k + 1])), "share": round(float(tr[k + 1] / fl[k + 1]), 3)} for k in range(len(names)) if fl[k + 1] > 100]
    countries.sort(key=lambda c: -c["tree_km2"])
    return {"floodplain_km2": round(float(flood.sum(dtype=np.float64))), "tree_km2": round(float(tree.sum(dtype=np.float64))), "share": round(float(tree.sum(dtype=np.float64) / flood.sum(dtype=np.float64)), 3), "no_land_cover_km2": round(missing), "hazard_tiles": tiles, "land_cover_tiles_failed": sorted(FAILED_LAND_COVER), "countries": countries,
            "breaks": BREAKS, "colors": [f"#{c[0]:02x}{c[1]:02x}{c[2]:02x}" for c in COLORS], "max_zoom": MAX_ZOOM, "cell_deg": 0.1}


def lookup_cells(flood, tree):
    folder = OUT / "cells"
    folder.mkdir(parents=True, exist_ok=True)
    f4 = np.add.reduceat(np.add.reduceat(flood.astype(np.float64), np.arange(0, ROWS, 4), 0), np.arange(0, COLS, 4), 1)
    t4 = np.add.reduceat(np.add.reduceat(tree.astype(np.float64), np.arange(0, ROWS, 4), 0), np.arange(0, COLS, 4), 1)
    written = []
    for lat0 in range(-60, 85, 10):
        top = lat0 + 10
        r0 = round((NORTH - top) * 10)
        r1 = round((NORTH - lat0) * 10)
        if r0 < 0:
            continue
        for lon0 in range(-180, 180, 10):
            c0 = round((lon0 + 180) * 10)
            a, b = f4[r0:r1, c0:c0 + 100], t4[r0:r1, c0:c0 + 100]
            if a.sum() < 0.01:
                continue
            data = np.stack([np.round(a * 100), np.round(b * 100)]).clip(0, 65535).astype("<u2")
            (folder / f"{lat0}_{lon0}.bin").write_bytes(data.tobytes())
            written.append(f"{lat0}_{lon0}")
    return written


def mercator_lat(y):
    return math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y))))


def save_tile(z, x, y, density):
    classes = np.digitize(density, BREAKS)
    classes[density < BREAKS[0] * 0.5] = 255  # transparent
    classes = np.where(classes == 255, 0, classes + 1).astype(np.uint8)
    img = Image.fromarray(classes, "P")
    img.putpalette([0, 0, 0, *[v for c in COLORS for v in c]])
    path = OUT / "tiles" / str(z) / str(x) / f"{y}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, optimize=True, transparency=0)


def map_tiles(flood, tree):
    lat_rows = NORTH - (np.arange(ROWS) + 0.5) * STEP
    cell_km2 = (STEP * 111.32) ** 2 * np.cos(np.radians(lat_rows))
    density = tree / cell_km2[:, None].astype(np.float32)
    z = MAX_ZOOM
    n = 2 ** z
    size = 256
    edges = np.array([mercator_lat((k + 0.5) / (n * size)) for k in range(n * size)])
    rows_for_y = np.clip(((NORTH - edges) / STEP).astype(int), -1, ROWS)
    valid_y = (edges < NORTH) & (edges > SOUTH)
    level = {}
    for x in range(n):
        cols = (((x + (np.arange(size) + 0.5) / size) / n) * COLS).astype(int)
        for y in range(n):
            ys = np.arange(y * size, (y + 1) * size)
            if not valid_y[ys].any():
                continue
            rr = rows_for_y[ys]
            tile = np.zeros((size, size), np.float32)
            ok = valid_y[ys]
            tile[ok] = density[rr[ok]][:, cols]
            if tile.max() >= BREAKS[0] * 0.5:
                level[(x, y)] = tile
    print("zoom", z, len(level), "tiles", flush=True)
    for (x, y), tile in level.items():
        save_tile(z, x, y, tile)
    # Lower zooms blend the mean with the maximum, so narrow forested valleys stay visible on a world view.
    while z > MIN_ZOOM:
        parents = {}
        for (x, y), tile in level.items():
            px, py = x // 2, y // 2
            parent = parents.setdefault((px, py), np.zeros((size, size), np.float32))
            blocks = tile.reshape(size // 2, 2, size // 2, 2)
            small = 0.5 * blocks.mean((1, 3)) + 0.5 * blocks.max((1, 3))
            oy, ox = (y % 2) * size // 2, (x % 2) * size // 2
            parent[oy:oy + size // 2, ox:ox + size // 2] = small
        z -= 1
        level = {k: v for k, v in parents.items() if v.max() >= BREAKS[0] * 0.5}
        print("zoom", z, len(level), "tiles", flush=True)
        for (x, y), tile in level.items():
            save_tile(z, x, y, tile)


def gazetteer():
    """Places for the search box: towns and cities, countries and named rivers."""
    raw = cached("https://download.geonames.org/export/dump/cities5000.zip", WORK / "cities5000.zip")
    with zipfile.ZipFile(raw) as z:
        text = z.read("cities5000.txt").decode("utf8")
    codes = cached("https://download.geonames.org/export/dump/countryInfo.txt", WORK / "countryInfo.txt").read_text(encoding="utf8")
    country = {line.split("\t")[0]: line.split("\t")[4] for line in codes.splitlines() if line and not line.startswith("#")}
    admin = cached("https://download.geonames.org/export/dump/admin1CodesASCII.txt", WORK / "admin1.txt").read_text(encoding="utf8")
    states = {line.split("\t")[0]: line.split("\t")[1] for line in admin.splitlines() if line}
    rows = []
    for line in io.StringIO(text):
        p = line.rstrip("\n").split("\t")
        region = states.get(f"{p[8]}.{p[10]}", "")
        where = ", ".join(x for x in (region if p[8] in ("US", "CA", "AU", "BR", "IN", "MX", "CN") else "", country.get(p[8], p[8])) if x)
        rows.append([p[1], where, round(float(p[4]), 3), round(float(p[5]), 3), int(p[14] or 0)])
    rows.sort(key=lambda r: -r[4])
    places = [r[:4] for r in rows]
    rivers = json.loads(cached(f"{NE}ne_10m_rivers_lake_centerlines.geojson", WORK / "ne_rivers.geojson").read_text(encoding="utf8"))
    points = {}
    for f in rivers["features"]:
        name, geom = f["properties"].get("name"), f["geometry"]
        if not name or not geom or f["properties"].get("featurecla") != "River":
            continue
        lines = geom["coordinates"] if geom["type"] == "MultiLineString" else [geom["coordinates"]]
        points.setdefault(name, []).extend(pt for line in lines for pt in line)
    river_rows = []
    for name, pts in points.items():
        pts = np.array(pts)[:, :2]
        mid = pts[np.argmin(((pts - pts.mean(0)) ** 2).sum(1))]
        river_rows.append([f"{name} River" if "river" not in name.lower() else name, "river", round(float(mid[1]), 3), round(float(mid[0]), 3)])
    (OUT / "places.json").write_text(json.dumps({"places": places, "rivers": river_rows}, ensure_ascii=False, separators=(",", ":")), encoding="utf8")
    return len(places), len(river_rows)


# A town counts as high risk when most of the floodplain within 25 km is under trees, and there's a lot of it.
HIGH_SHARE, HIGH_TREE_KM2, MODERATE_SHARE, MODERATE_TREE_KM2, MIN_FLOODPLAIN_KM2 = 0.5, 100, 0.2, 25, 2
EXAMPLES = (("Iquitos", "PE"), ("Port Harcourt", "NG"), ("Belém", "BR"), ("Pekanbaru", "ID"), ("Mbandaka", "CD"), ("Waycross", "US"))


def risk_level(floodplain, tree):
    if floodplain < MIN_FLOODPLAIN_KM2:
        return "none"
    share = tree / floodplain
    if share >= HIGH_SHARE and tree >= HIGH_TREE_KM2:
        return "high"
    if share >= MODERATE_SHARE and tree >= MODERATE_TREE_KM2:
        return "moderate"
    return "lower"


PEOPLE_MERGE_KM = 10


def count_people(towns):
    """People living in the high blind-spot towns. GeoNames lists city districts (PPLX) and near-duplicate places,
    so districts are skipped and any town within PEOPLE_MERGE_KM of a larger counted town is treated as part of it.
    This is the population of the towns, not of their floodplains, and it doesn't say anyone floods."""
    kept = []
    for pop, lat, lon in sorted(towns, reverse=True):
        near = False
        for _, klat, klon in kept:
            dx = (lon - klon) * 111.32 * math.cos(math.radians((lat + klat) / 2))
            if dx * dx + ((lat - klat) * 111.32) ** 2 < PEOPLE_MERGE_KM ** 2:
                near = True
                break
        if not near:
            kept.append((pop, lat, lon))
    return {"total": sum(k[0] for k in kept), "places": len(kept), "merge_km": PEOPLE_MERGE_KM}


def town_counts():
    """How many towns of 5,000+ people meet the place check's rule. It says what ground is nearby, not that a town floods."""
    summary = json.loads((OUT / "summary.json").read_text())
    rows, cols = 1400, 3600
    flood, tree = np.zeros((rows, cols), np.float32), np.zeros((rows, cols), np.float32)
    for name in summary["cell_files"]:
        lat0, lon0 = map(int, name.split("_"))
        data = np.frombuffer((OUT / "cells" / f"{name}.bin").read_bytes(), "<u2").reshape(2, 100, 100) / 100
        r0, c0 = (80 - (lat0 + 10)) * 10, (lon0 + 180) * 10
        flood[r0:r0 + 100, c0:c0 + 100], tree[r0:r0 + 100, c0:c0 + 100] = data[0], data[1]

    def around(lat, lon):
        r, c = int((80 - lat) * 10), int((lon + 180) * 10)
        span = min(30, math.ceil(25 / (11.132 * max(0.1, math.cos(math.radians(lat))))))
        f = t = 0.0
        for rr in range(max(0, r - 3), min(rows, r + 4)):
            lat_c = 80 - (rr + 0.5) / 10
            for cc in range(c - span, c + span + 1):
                dx = (((cc % cols) + 0.5) / 10 - 180 - lon) * 111.32 * math.cos(math.radians((lat + lat_c) / 2))
                dy = (lat_c - lat) * 111.32
                if dx * dx + dy * dy <= 625:
                    f += flood[rr, cc % cols]
                    t += tree[rr, cc % cols]
        return float(f), float(t)

    with zipfile.ZipFile(WORK / "cities5000.zip") as z:
        text = z.read("cities5000.txt").decode("utf8")
    codes = (WORK / "countryInfo.txt").read_text(encoding="utf8")
    country = {line.split("\t")[0]: line.split("\t")[4] for line in codes.splitlines() if line and not line.startswith("#")}
    levels, by_country, largest, examples, points, people = {"high": 0, "moderate": 0, "lower": 0, "none": 0}, {}, [], {}, [], []
    for line in io.StringIO(text):
        p = line.rstrip("\n").split("\t")
        pop, lat, lon = int(p[14] or 0), float(p[4]), float(p[5])
        if pop < 5000 or not -60 < lat < 80:
            continue
        f, t = around(lat, lon)
        level = risk_level(f, t)
        levels[level] += 1
        if level == "high":
            by_country[p[8]] = by_country.get(p[8], 0) + 1
            largest.append((pop, p[1], p[8]))
            if p[7] != "PPLX":
                people.append((pop, lat, lon))
            points.append([p[1], country.get(p[8], p[8]), round(lat, 3), round(lon, 3)])
        if (p[1], p[8]) in EXAMPLES:
            examples[(p[1], p[8])] = {"name": p[1], "where": country.get(p[8], p[8]), "lat": round(lat, 3), "lon": round(lon, 3), "level": level}
    summary["towns"] = {"checked": sum(levels.values()), **levels, "rule": {"high_share": HIGH_SHARE, "high_tree_km2": HIGH_TREE_KM2, "moderate_share": MODERATE_SHARE, "moderate_tree_km2": MODERATE_TREE_KM2, "min_floodplain_km2": MIN_FLOODPLAIN_KM2},
                        "top_countries": [[country.get(k, k), v] for k, v in sorted(by_country.items(), key=lambda kv: -kv[1])[:10]], "largest": [f"{name}, {country.get(code, code)}" for _, name, code in sorted(largest, reverse=True)[:20]],
                        "examples": [examples[e] for e in EXAMPLES if e in examples], "people": count_people(people)}
    (OUT / "summary.json").write_text(json.dumps(summary, separators=(",", ":")))
    (OUT / "towns.json").write_text(json.dumps(points, ensure_ascii=False, separators=(",", ":")), encoding="utf8")
    print({k: v for k, v in summary["towns"].items() if k != "rule"}, flush=True)


def finalize():
    """Adds what the page needs last: the list of tiles, each country's main extent and the check against GFM's own mask."""
    summary = json.loads((OUT / "summary.json").read_text())
    tiles = OUT / "tiles"
    (OUT / "tiles.json").write_text(json.dumps(sorted(p.relative_to(tiles).with_suffix("").as_posix() for p in tiles.rglob("*.png")), separators=(",", ":")))
    geo = json.loads((WORK / "ne_countries.geojson").read_text(encoding="utf8"))
    boxes = {}
    for f in geo["features"]:
        g = f["geometry"]
        if not g:
            continue
        parts = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        pts = np.array(max(parts, key=lambda part: len(part[0]))[0])[:, :2]
        boxes[f["properties"]["ADMIN"]] = [*pts.min(0).round(2).tolist(), *pts.max(0).round(2).tolist()]
    for c in summary["countries"]:
        c["bbox"] = boxes.get(c["name"])
    check = ROOT / "research" / "blind_spot_atlas_check.json"
    if check.exists():
        summary["check"] = json.loads(check.read_text())
    (OUT / "summary.json").write_text(json.dumps(summary, separators=(",", ":")))


def main():
    sys.stdout.reconfigure(encoding="utf8")
    WORK.mkdir(parents=True, exist_ok=True)
    flood, tree, missing, tiles = assemble()
    print("floodplain km2", round(float(flood.sum(dtype=np.float64))), "under trees", round(float(tree.sum(dtype=np.float64))), "no land cover", round(missing), flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    summary = summarize(flood, tree, missing, tiles)
    print({k: v for k, v in summary.items() if k != "countries"}, summary["countries"][:12], flush=True)
    summary["cell_files"] = lookup_cells(flood, tree)
    (WORK / "summary_base.json").write_text(json.dumps(summary))
    extra = {}
    check = ROOT / "research" / "blind_spot_atlas_check.json"
    if check.exists():
        extra["check"] = json.loads(check.read_text())
    (OUT / "summary.json").write_text(json.dumps({**summary, **extra}))
    map_tiles(flood, tree)
    print("places, rivers", gazetteer(), flush=True)
    town_counts()
    finalize()
    total = sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file())
    print(f"atlas data: {total / 1e6:.1f} MB, {sum(1 for _ in OUT.rglob('*.png'))} map tiles", flush=True)


if __name__ == "__main__":
    main()
