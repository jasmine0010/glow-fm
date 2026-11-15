"""Roads for the dashboard: the drivable road on each river's estimate corridor, as short pieces, one per pixel crossed.

    python scripts/build_roads.py      (also run by scripts/build_dashboard.py, since it follows the .bin pixel order)

Reads the OpenStreetMap ways saved for each dashboard river's blind-spot audit (<data root>/<river>/ops*/osm.json, from
hidden_floods.fetch.fetch_osm) and app/data/dashboard/<river>.bin from scripts/build_dashboard.py, and writes
app/data/dashboard/<river>_roads.bin. First the whole of each road that crosses the corridor: Int32 count L; L + 1
Int32 offsets into the points; Float32 longitude and latitude of every point. Then the pieces, one per pixel a road
crosses: Int32 count k; k Int32 pixel numbers (positions in the .bin's pixel order); k Int32 point numbers, the start of
the stretch of road each piece lies on; k by 2 Uint16 positions along that stretch where the piece starts and ends
(0 to 65535); k Float32 lengths in metres; k Uint8, 1 for a major road (motorway to tertiary). Pieces follow each road
in order, so touching ends join back into lines, and they sit on the true road line, not on the estimate image's corners.

The browser draws each road that has any flooded piece in full, and its flooded pieces over it in another colour.

The browser (roadsFromBuffer, roadsUnder in app/estimator.js) draws the pieces whose pixel the estimate floods, placed
with the same corners as the estimate image, and adds up their length, so both follow every gauge reading, past moment
and what-if rise. The road rules are those of the frozen blind-spot audit (src/hidden_floods/audit.py exposure):
drivable ways only, footpaths and bridges left out.
"""

import json

import numpy as np

from hidden_floods.config import REPO_ROOT, data_root, load_site
from hidden_floods.pipeline import analysis_grid
from hidden_floods.series import yellow_series_site

OUT = REPO_ROOT / "app" / "data" / "dashboard"
SKIP = {"footway", "path", "steps", "cycleway", "pedestrian", "bridleway", "corridor", "proposed", "construction"}
MAJOR = {"motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link", "secondary", "secondary_link", "tertiary", "tertiary_link"}


def osm_path(name):
    for sub in ("ops", "ops_audit"):
        p = data_root() / name / sub / "osm.json"
        if p.exists():
            return p
    raise FileNotFoundError(f"no osm.json for {name}")


def build(river):
    name, g = river["id"], river["grid"]
    site = yellow_series_site() if name == "yellow" else load_site(name)
    grid = analysis_grid(site)
    res = grid.res
    assert abs(res * res / 1e4 - g["pixel_ha"]) < 1e-9, "the dashboard grid has a different pixel size"
    # the crop's top-left corner, back on the analysis grid
    x0, y0 = (float(v) for v in grid.to_xy(*g["quad"][0]))
    c0, r0 = (x0 - grid.x0) / res, (grid.y0 - y0) / res
    assert abs(c0 - round(c0)) < 1e-3 and abs(r0 - round(r0)) < 1e-3, "crop corner is off the grid"
    c0, r0 = round(c0), round(r0)
    rows, cols, n = g["rows"], g["cols"], g["pixels"]
    idx = np.fromfile(OUT / f"{name}.bin", dtype=np.int32, count=n)
    lookup = np.full(rows * cols, -1, np.int64)
    lookup[idx] = np.arange(n)

    pix, seg_at, ts, length, big, lines, npts = [], [], [], [], [], [], 0
    osm = json.loads(osm_path(name).read_text(encoding="utf-8"))
    lon_lo = lat_lo = 1e9
    lon_hi = lat_hi = -1e9
    for el in osm.get("elements", []):
        if el.get("type") != "way" or "geometry" not in el:
            continue
        b = el.get("bounds")
        if b:
            lon_lo, lat_lo, lon_hi, lat_hi = min(lon_lo, b["minlon"]), min(lat_lo, b["minlat"]), max(lon_hi, b["maxlon"]), max(lat_hi, b["maxlat"])
        tags = el.get("tags", {})
        hw = tags.get("highway", "")
        if "building" in tags or hw in SKIP or tags.get("bridge") not in (None, "no"):
            continue
        x, y = (np.asarray(v, float) for v in grid.to_xy(np.array([p["lon"] for p in el["geometry"]]), np.array([p["lat"] for p in el["geometry"]])))
        cx, cy = (x - grid.x0) / res - c0, (grid.y0 - y) / res - r0      # the crop's pixel units
        first = len(pix)
        for i in range(len(x) - 1):
            seg = float(np.hypot(x[i + 1] - x[i], y[i + 1] - y[i]))
            k = max(int(seg // (res / 4)), 1)           # four samples per pixel width
            f = (np.arange(k) + 0.5) / k
            sx, sy = cx[i] + f * (cx[i + 1] - cx[i]), cy[i] + f * (cy[i + 1] - cy[i])
            c, r = np.floor(sx).astype(np.int64), np.floor(sy).astype(np.int64)
            ok = (r >= 0) & (r < rows) & (c >= 0) & (c < cols)
            p = np.full(k, -1, np.int64)
            p[ok] = lookup[r[ok] * cols + c[ok]]
            # one piece per run of samples on the same pixel, from the run's first sample edge to its last
            cut = np.nonzero(np.diff(p))[0] + 1
            for s0, s1 in zip(np.r_[0, cut], np.r_[cut, k], strict=True):
                if p[s0] < 0:
                    continue
                pix.append(p[s0])
                seg_at.append(npts + i)          # the road's points are stored from npts on, if it's kept
                ts.append([round(65535 * s0 / k), round(65535 * s1 / k)])
                length.append((s1 - s0) * seg / k)
                big.append(hw in MAJOR)
        if len(pix) > first:      # this road crosses the corridor: keep the whole of it for drawing
            lines.append([[p["lon"], p["lat"]] for p in el["geometry"]])
            npts += len(el["geometry"])
    with open(OUT / f"{name}_roads.bin", "wb") as f:
        f.write(np.int32(len(lines)).tobytes())
        f.write(np.cumsum([0] + [len(ln) for ln in lines]).astype(np.int32).tobytes())
        f.write(np.array([pt for ln in lines for pt in ln], np.float32).tobytes())
        f.write(np.int32(len(pix)).tobytes())
        f.write(np.array(pix, np.int32).tobytes())
        f.write(np.array(seg_at, np.int32).tobytes())
        f.write(np.array(ts, np.uint16).tobytes())
        f.write(np.array(length, np.float32).tobytes())
        f.write(np.array(big, np.uint8).tobytes())
    length = np.array(length)
    metres, major = length.sum(), length[np.array(big, bool)].sum()
    # the corridor must sit inside the area the roads were fetched for, or roads would be missing without notice
    corner = [grid.to_lonlat(x0 + dx * res, y0 - dy * res) for dx, dy in ((0, 0), (cols, rows))]
    inside = lon_lo <= min(corner[0][0], corner[1][0]) and max(corner[0][0], corner[1][0]) <= lon_hi and lat_lo <= min(corner[0][1], corner[1][1]) and max(corner[0][1], corner[1][1]) <= lat_hi
    print(f"{name:15} {metres / 1000:7.1f} km of drivable road in the corridor ({major / 1000:.1f} km major) in {len(pix):,} pieces of {len(lines):,} roads on {len(set(pix)):,} of {n:,} pixels;"
          f" corridor inside the OSM area: {'yes' if inside else 'NO, roads near its edge may be missing'}", flush=True)


def main():
    for river in json.loads((OUT / "rivers.json").read_text())["rivers"]:
        build(river)


if __name__ == "__main__":
    main()
