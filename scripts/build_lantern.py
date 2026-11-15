"""Data for the story page's journey, "The Lantern" (app/lantern.js): the planet drawn only from its floodplain forests.

    python scripts/build_lantern.py

Writes to app/data/story/:
- lantern_points.bin: forested floodplain on a 0.5 degree grid, as Int16 triples (lon x 100, lat x 100, km2), from the
  blind-spot atlas cells. The build stops unless every cell's forest is counted (it must sum to the atlas total).
- lantern_people.json: the high blind-spot towns with their GeoNames population, merged exactly as the atlas does
  (city districts skipped, towns within 10 km merged). The build stops unless the total matches the atlas.
- lantern_coast.json: simplified coastlines for a faint outline, and Greenland on its own for the size comparison.
Reads only files already made by build_atlas.py and its cache in outputs/atlas.
"""

import io
import json
import math
import zipfile

import numpy as np
from build_atlas import OUT as ATLAS, PEOPLE_MERGE_KM, WORK

from hidden_floods.config import REPO_ROOT

STORY = REPO_ROOT / "app" / "data" / "story"
STEP = 5                      # 5 x 0.1 degree cells = 0.5 degree points
MIN_KM2 = 1.0                 # a point needs at least 1 km2 of forested floodplain to be drawn
GREENLAND_KM2 = 2_166_086     # CIA World Factbook area of Greenland, quoted in the page's fine print


def points(summary):
    tree = np.zeros((1400, 3600), np.float64)
    for name in summary["cell_files"]:
        lat0, lon0 = map(int, name.split("_"))
        data = np.frombuffer((ATLAS / "cells" / f"{name}.bin").read_bytes(), "<u2").reshape(2, 100, 100) / 100
        r0, c0 = (80 - (lat0 + 10)) * 10, (lon0 + 180) * 10
        tree[r0:r0 + 100, c0:c0 + 100] = data[1]
    total = tree.sum()
    if abs(total - summary["tree_km2"]) > 0.01 * summary["tree_km2"]:
        raise SystemExit(f"cells sum to {total:.0f} km2 of forested floodplain, the atlas says {summary['tree_km2']}")
    coarse = tree.reshape(1400 // STEP, STEP, 3600 // STEP, STEP).sum(axis=(1, 3))
    rows, cols = np.nonzero(coarse >= MIN_KM2)
    lat = 80 - (rows + 0.5) * STEP / 10
    lon = -180 + (cols + 0.5) * STEP / 10
    km2 = coarse[rows, cols]
    out = np.stack([np.round(lon * 100), np.round(lat * 100), np.minimum(np.round(km2), 32767)], 1).astype("<i2")
    (STORY / "lantern_points.bin").write_bytes(out.tobytes())
    return {"points": int(len(km2)), "km2_drawn": float(km2.sum()), "km2_total": float(total)}


def people(summary):
    """The atlas's own merge (scripts/build_atlas.py count_people), kept as places instead of only a total."""
    towns = json.loads((ATLAS / "towns.json").read_text(encoding="utf8"))
    wanted = {(t[0], round(t[2], 3), round(t[3], 3)) for t in towns}
    with zipfile.ZipFile(WORK / "cities5000.zip") as z:
        text = z.read("cities5000.txt").decode("utf8")
    found = []
    for line in io.StringIO(text):
        p = line.rstrip("\n").split("\t")
        lat, lon = float(p[4]), float(p[5])
        if (p[1], round(lat, 3), round(lon, 3)) in wanted and p[7] != "PPLX":
            found.append((int(p[14] or 0), lat, lon))
    kept = []
    for pop, lat, lon in sorted(found, reverse=True):
        near = False
        for _, klat, klon in kept:
            dx = (lon - klon) * 111.32 * math.cos(math.radians((lat + klat) / 2))
            if dx * dx + ((lat - klat) * 111.32) ** 2 < PEOPLE_MERGE_KM ** 2:
                near = True
                break
        if not near:
            kept.append((pop, lat, lon))
    total = sum(k[0] for k in kept)
    if total != summary["towns"]["people"]["total"] or len(kept) != summary["towns"]["people"]["places"]:
        raise SystemExit(f"people {total} in {len(kept)} places, the atlas says {summary['towns']['people']}")
    rows = [[round(lon, 2), round(lat, 2), pop] for pop, lat, lon in kept]
    (STORY / "lantern_people.json").write_text(json.dumps(rows, separators=(",", ":")))
    return {"places": len(kept), "people": total}


def thin(ring, gap):
    """Keep a point only when it is at least `gap` degrees from the last one kept."""
    out = [ring[0]]
    for x, y in ring[1:]:
        if abs(x - out[-1][0]) + abs(y - out[-1][1]) >= gap:
            out.append([x, y])
    return [[round(x, 2), round(y, 2)] for x, y in out]


def coast():
    data = json.loads((WORK / "ne_countries.geojson").read_text(encoding="utf8"))
    rings, greenland = [], []
    for f in data["features"]:
        g = f["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        for poly in polys:
            r = thin(poly[0], 1.0)
            if len(r) >= 8:
                rings.append(r)
            if f["properties"].get("ADMIN") == "Greenland" and len(poly[0]) > len(greenland):
                greenland = poly[0]
    out = {"rings": rings, "greenland": thin(greenland, 0.25), "greenland_km2": GREENLAND_KM2}
    (STORY / "lantern_coast.json").write_text(json.dumps(out, separators=(",", ":")))
    return {"rings": len(rings), "coast_points": sum(len(r) for r in rings), "greenland_points": len(out["greenland"])}


def main():
    STORY.mkdir(parents=True, exist_ok=True)
    summary = json.loads((ATLAS / "summary.json").read_text())
    print("lantern", points(summary), people(summary), coast())


if __name__ == "__main__":
    main()
