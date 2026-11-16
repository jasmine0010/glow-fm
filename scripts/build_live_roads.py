"""Roads for Run it yourself: the drivable roads in each prepared flood's 24 km box, from OpenStreetMap.

    python scripts/build_live_roads.py

For every case in app/data/live/index.json, asks the Overpass service once for the highway ways in the box (cached
in <data root>/live/roads/<case>.json, so a rebuild needs no network) and writes app/data/live/<case>/roads.bin:
Int32 count L; L + 1 Int32 offsets into the points; L Uint8, 1 for a major road (motorway to tertiary); zero padding
to a multiple of 4 bytes; Float32 longitude and latitude of every point.

The page (live.js) lays these roads on the case's 50 m grid and draws, and counts, the stretches on ground the
method flags as flooded. A custom run from the local box reader asks Overpass from the browser instead. The road rules
are those of the frozen blind-spot audit (src/hidden_floods/audit.py exposure): drivable ways only, footpaths and
bridges left out. The case files themselves (case.json, pack.bin) are not touched.
"""

import json
import math
from itertools import pairwise

import numpy as np
from build_roads import MAJOR, SKIP, overpass

from hidden_floods.config import REPO_ROOT, data_root

LIVE = REPO_ROOT / "app" / "data" / "live"
CACHE = data_root() / "live" / "roads"


def build(case_id):
    rec = json.loads((LIVE / case_id / "case.json").read_text(encoding="utf-8"))
    lons, lats = [p[0] for p in rec["corners"]], [p[1] for p in rec["corners"]]
    box = (min(lons) - 0.002, min(lats) - 0.002, max(lons) + 0.002, max(lats) + 0.002)
    cached = CACHE / f"{case_id}.json"
    if not cached.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(overpass(box))
    osm = json.loads(cached.read_text(encoding="utf-8"))
    lines, major = [], []
    for el in osm.get("elements", []):
        tags = el.get("tags", {})
        hw = tags.get("highway", "")
        if el.get("type") != "way" or "geometry" not in el or not hw or hw in SKIP or tags.get("bridge") not in (None, "no"):
            continue
        lines.append([[p["lon"], p["lat"]] for p in el["geometry"]])
        major.append(hw in MAJOR)
    with open(LIVE / case_id / "roads.bin", "wb") as f:
        f.write(np.int32(len(lines)).tobytes())
        f.write(np.cumsum([0] + [len(ln) for ln in lines]).astype(np.int32).tobytes())
        f.write(np.array(major, np.uint8).tobytes())
        f.write(bytes(-len(lines) % 4))
        f.write(np.array([pt for ln in lines for pt in ln], np.float32).tobytes())
    km_per_deg = 111.32
    km = sum(math.hypot((b[0] - a[0]) * km_per_deg * math.cos(math.radians(a[1])), (b[1] - a[1]) * km_per_deg) for ln in lines for a, b in pairwise(ln))
    print(f"{case_id:28} {len(lines):5,} drivable roads, about {km:,.0f} km in and around the box", flush=True)


def main():
    # Overpass times out now and then: a failed box is skipped, the rest carry on, and the failures get one more try.
    failed = []
    for c in json.loads((LIVE / "index.json").read_text(encoding="utf-8"))["cases"]:
        try:
            build(c["id"])
        except RuntimeError as e:
            print(f"{c['id']:28} skipped for now: {e}", flush=True)
            failed.append(c["id"])
    still = []
    for case_id in failed:
        try:
            build(case_id)
        except RuntimeError as e:
            print(f"{case_id:28} failed again: {e}", flush=True)
            still.append(case_id)
    print(f"ROADS DONE: {len(still)} without roads" + (f" ({', '.join(still)})" if still else ""), flush=True)


if __name__ == "__main__":
    main()
