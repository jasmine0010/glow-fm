"""The likely cause of each dashboard flood: how much rain fell on the river's catchment in the two weeks before it crested.

    python scripts/build_flood_rain.py

The Space Apps challenge asks to hypothesize the physical drivers behind what the radar shows. For a river flood the first
driver is the rain upstream, so for every river on the dashboard (app/data/dashboard/rivers.json) this finds:

- the crest: the time a gauge stood highest above its flood level, from the river's recorded levels (<id>_gauges.json);
- the catchment: everything that drains to the river's most downstream gauge, from USGS NLDI (its upstream basin);
- the rain: NASA GPM IMERG Late Run daily totals (GPM_3IMERGDL V07, 0.1 degree) averaged over the 0.1 degree cells whose
  centres lie in that catchment, for the DAYS days up to and including the crest day, and the wettest 3-day spell in them.

Two weeks, because big lowland rivers crest a week or more after the rain (the Choctawhatchee crested 8 days after its
heaviest rain). Writes app/data/dashboard/rain.json. Reads only the catchment's box from each daily file, through NASA's
OPeNDAP server, with the Earthdata sign-in that curl takes from ~/.netrc (this code never reads it). Daily files and
catchments are cached under the data root, so a rerun reads nothing new. Rain is a likely cause, not a proven one: rivers
also rise from water already in the ground, upstream releases or tides. Changes no method and no score.
"""

import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hidden_floods.config import REPO_ROOT, data_root
from hidden_floods.fetch import get_json

COLLECTION = "C2723754859-GES_DISC"     # GPM_3IMERGDL V07: IMERG Late Run, daily, 0.1 degree, mm/day
CMR = "https://cmr.earthdata.nasa.gov/search/granules.json"
OPENDAP = f"https://opendap.earthdata.nasa.gov/collections/{COLLECTION}/granules/"
DASH = REPO_ROOT / "app" / "data" / "dashboard"
CACHE = data_root() / "rain_daily"
JAR = CACHE / "jar.txt"
NLDI = "https://api.water.usgs.gov/nldi/linked-data/nwissite/USGS-{}/basin?f=json"
DAYS = 14
SPELL = 3


def catchment(usgs):
    """The outer rings of the basin draining to a USGS gauge, from NLDI (cached)."""
    path = CACHE / f"basin_{usgs}.json"
    if not path.exists():
        path.write_text(json.dumps(get_json(NLDI.format(usgs), timeout=180)))
    geom = json.loads(path.read_text())["features"][0]["geometry"]
    polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    return [np.array(p[0], float) for p in polys]


def inside(rings, xs, ys):
    """Which points (xs, ys) fall inside any of the rings (even-odd ray casting)."""
    hit = np.zeros(xs.shape, bool)
    for ring in rings:
        x1, y1 = ring[:-1, 0], ring[:-1, 1]
        x2, y2 = ring[1:, 0], ring[1:, 1]
        inn = np.zeros(xs.shape, bool)
        for a, b, c, d in zip(x1, y1, x2, y2, strict=True):
            crosses = ((b > ys) != (d > ys)) & (xs < (c - a) * (ys - b) / ((d - b) or 1e-12) + a)
            inn ^= crosses
        hit |= inn
    return hit


def curl(url, seed=False):
    jar = ["-c", str(JAR), "-b", str(JAR)] if seed else ["-b", str(JAR)]
    out = subprocess.run(["curl", "-n", "-L", "-s", "--fail", "--retry", "4", "--retry-delay", "3", "--max-time", "120", *jar, url],
                         check=False, capture_output=True, text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if out.returncode:
        raise RuntimeError(f"curl exit {out.returncode} for {url[:120]}")
    return out.stdout


def granule(day):
    """The daily file's name for a date, from NASA's public catalogue."""
    q = f"{CMR}?collection_concept_id={COLLECTION}&temporal={day:%Y-%m-%dT00:00:00Z},{day:%Y-%m-%dT23:59:59Z}&page_size=5"
    names = [e["title"] for e in get_json(q, timeout=120)["feed"]["entry"] if f"{day:%Y%m%d}-S000000" in e["title"]]
    if not names:
        raise RuntimeError(f"no IMERG daily file for {day:%Y-%m-%d} yet")
    return names[0]


def cell(lon, lat):
    """Index of the 0.1 degree cell holding a point (cell centres at -179.95 + 0.1 i and -89.95 + 0.1 j)."""
    return int(np.floor((lon + 180) * 10)), int(np.floor((lat + 90) * 10))


def day_box(day, i0, i1, j0, j1):
    """mm that day in every cell of the box, from the cache or NASA."""
    path = CACHE / f"{day:%Y%m%d}_{i0}_{i1}_{j0}_{j1}.json"
    if path.exists():
        return json.loads(path.read_text())
    name = granule(day).replace(":", "%3A")
    text = curl(f"{OPENDAP}{name}.dap.csv?dap4.ce=/precipitation%5B0%5D%5B{i0}:{i1}%5D%5B{j0}:{j1}%5D", seed=not JAR.exists())
    rows = [[float(v) for v in ln.split(",")[1:]] for ln in text.splitlines() if ln.startswith("/precipitation")]
    if len(rows) != i1 - i0 + 1 or any(len(r) != j1 - j0 + 1 for r in rows):
        raise ValueError(f"unexpected shape for {day:%Y-%m-%d}")
    path.write_text(json.dumps(rows))
    return rows


def crest(river):
    """When a gauge stood highest above its flood level (or rose most, where no flood level is listed)."""
    series = {g["id"].replace("USGS-", ""): g for g in json.loads((DASH / f"{river['id']}_gauges.json").read_text())}
    best = None
    for g in river["gauges"]:
        s = series.get(g["id"])
        if not s or not s["stage_ft"]:
            continue
        stage = np.array(s["stage_ft"], float)
        k = int(np.nanargmax(stage))
        over = stage[k] - g["flood_ft"] if g.get("flood_ft") else stage[k] - np.nanmin(stage) - 1e6   # a listed flood level wins
        if best is None or over > best[0]:
            best = (over, s["times"][k], g["name"], bool(g.get("flood_ft") and stage[k] >= g["flood_ft"]))
    if best is None:
        return None
    return {"time": best[1], "gauge": best[2], "above_flood_level": best[3]}


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    rivers = json.loads((DASH / "rivers.json").read_text())["rivers"]
    out = {"source": "NASA GPM IMERG Late Run V07, daily (GPM_3IMERGDL), over each river's catchment from USGS NLDI",
           "days": DAYS, "spell_days": SPELL, "rivers": {}}
    for r in rivers:
        c = crest(r)
        if not c:
            print(f"{r['id']:16} no recorded levels, skipped", flush=True)
            continue
        outlet = max(r["gauges"], key=lambda g: g["chain_m"])
        try:
            rings = catchment(outlet["id"])
        except Exception as err:  # noqa: BLE001  (a gauge NLDI doesn't know has no catchment here)
            print(f"{r['id']:16} no catchment for {outlet['id']} ({type(err).__name__}), skipped", flush=True)
            continue
        allpts = np.vstack(rings)
        i0, j0 = cell(allpts[:, 0].min(), allpts[:, 1].min())
        i1, j1 = cell(allpts[:, 0].max(), allpts[:, 1].max())
        ii, jj = np.meshgrid(np.arange(i0, i1 + 1), np.arange(j0, j1 + 1), indexing="ij")
        mask = inside(rings, -179.95 + 0.1 * ii, -89.95 + 0.1 * jj)
        if not mask.any():                 # a catchment smaller than one cell: use the cell holding the gauge
            gi, gj = cell(outlet["lon"], outlet["lat"])
            mask = (ii == gi) & (jj == gj)
        end = datetime.fromisoformat(c["time"][:10])
        days = [end - timedelta(days=k) for k in range(DAYS - 1, -1, -1)]
        try:
            grids = [np.array(day_box(d, i0, i1, j0, j1), float) for d in days]
        except (RuntimeError, ValueError) as err:
            print(f"{r['id']:16} rain not read: {err}", flush=True)
            continue
        daily = [float(np.nanmean(np.where(g < 0, np.nan, g)[mask])) for g in grids]
        total = float(np.sum(daily))
        spells = [sum(daily[k:k + SPELL]) for k in range(DAYS - SPELL + 1)]
        k = int(np.argmax(spells))
        km2 = float(mask.sum()) * (11.1 ** 2) * np.cos(np.radians((allpts[:, 1].min() + allpts[:, 1].max()) / 2))
        out["rivers"][r["id"]] = {"crest": c["time"], "crest_gauge": c["gauge"], "crest_above_flood_level": c["above_flood_level"],
                                  "outlet_gauge": outlet["name"], "outlet_usgs": outlet["id"], "catchment_cells": int(mask.sum()), "catchment_km2_approx": round(km2, -1),
                                  "from": f"{days[0]:%Y-%m-%d}", "to": f"{days[-1]:%Y-%m-%d}", "mm": round(total), "daily_mm": [round(x, 1) for x in daily],
                                  "spell_from": f"{days[k]:%Y-%m-%d}", "spell_to": f"{days[k + SPELL - 1]:%Y-%m-%d}", "spell_mm": round(spells[k])}
        print(f"{r['id']:16} crest {c['time'][:10]}  {round(total):4d} mm over {int(mask.sum()):4d} cells in {DAYS} days; "
              f"wettest {SPELL} days {days[k]:%b %d}-{days[k + SPELL - 1]:%d}: {round(spells[k])} mm", flush=True)
    (DASH / "rain.json").write_text(json.dumps(out, indent=1))
    print(f"-> {DASH / 'rain.json'}  ({len(out['rivers'])} of {len(rivers)} rivers)")


if __name__ == "__main__":
    main()
