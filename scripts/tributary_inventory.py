"""Inventory of stage gauges the estimate doesn't use. Prints where they are and whether they have data. Reads no flags and prints no water levels."""
import json
import tomllib
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
from pyproj import Transformer

from hidden_floods.config import load_site
from hidden_floods.pipeline import analysis_grid

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/tributary_gauges"
OUT.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "hidden-floods-research/0.1"}
PASSES = [("satilla", "047A_oct15", "2026-10-15T10:45:42Z"), ("satilla", "098D_oct19", "2026-10-19T00:11:51Z"), ("st_marys", "098D_oct07", None), ("st_marys", "047A_oct15", None), ("ochlockonee", "026D_oct14", None),
          ("alapaha", "047A_oct15", None), ("alapaha", "148A_oct22", None), ("withlacoochee", "047A_oct15", None), ("withlacoochee", "148A_oct10", None),
          ("pee_dee", "098D_jul27", None), ("neuse", "090A_jul26", None), ("lower_sabine", "134A_jul17", None)]


def get(url, timeout=60):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read().decode()


inventory = []
for river, pair, _ in PASSES:
    site = load_site(river)
    grid = analysis_grid(site)
    cfg = tomllib.loads((ROOT / "sites" / f"{river}.toml").read_text())
    used = {g["id"].replace("USGS-", "") for g in cfg["gauges"]}
    when = site.pairs[pair].wet_time
    day = when[:10]
    q = urllib.parse.urlencode({"format": "rdb", "bBox": ",".join(f"{v:.5f}" for v in cfg["bbox"]), "parameterCd": "00065", "hasDataTypeCd": "iv", "siteStatus": "all", "siteOutput": "expanded"})
    lines = [x for x in get(f"https://waterservices.usgs.gov/nwis/site/?{q}").splitlines() if x and not x.startswith("#")]
    head = lines[0].split("\t")
    rows = [dict(zip(head, x.split("\t"), strict=False)) for x in lines[2:]]
    z = np.load(ROOT / "outputs" / river / pair / "frozen_v4_layers.npz")
    depth = z["depth"]
    to = Transformer.from_crs(4326, grid.crs, always_xy=True)
    X, Y = np.meshgrid(grid.xs, grid.ys)
    in_corr = np.isfinite(depth)
    cx, cy = X[in_corr], Y[in_corr]
    print(f"\n{river} {pair}: {len(rows)} stage gauges in the box, {len(used)} used by the estimate", flush=True)
    for r in rows:
        if r["site_no"] in used:
            continue
        lon, lat = float(r["dec_long_va"]), float(r["dec_lat_va"])
        x, y = to.transform(lon, lat)
        inside = grid.xs[0] <= x <= grid.xs[-1] and grid.ys[-1] <= y <= grid.ys[0]
        dist = float(np.min(np.hypot(cx - x, cy - y))) if len(cx) else None
        rc = (int((grid.ys[0] - y) / grid.res), int((x - grid.xs[0]) / grid.res))
        region = bool(z["region"][rc]) if inside else False
        has_value = False
        try:
            q = urllib.parse.urlencode({"format": "json", "sites": r["site_no"], "parameterCd": "00065", "startDT": f"{day}T00:00Z", "endDT": f"{day}T23:59Z", "siteStatus": "all"})
            j = json.loads(get(f"https://waterservices.usgs.gov/nwis/iv/?{q}"))
            has_value = any(len(s["values"][0]["value"]) > 0 for s in j["value"]["timeSeries"])
        except Exception as e:
            print("   read failed", r["site_no"], repr(e)[:80])
        row = {"river": river, "pair": pair, "site": r["site_no"], "name": r["station_nm"], "lon": lon, "lat": lat, "alt_ft": r.get("alt_va"), "datum": r.get("alt_datum_cd"), "alt_accuracy_ft": r.get("alt_acy_va"), "drain_sqmi": r.get("drain_area_va"), "inside_grid": bool(inside), "in_region": region, "km_to_corridor": None if dist is None else round(dist / 1000, 1), "has_stage_that_day": has_value}
        inventory.append(row)
        print("  ", {k: row[k] for k in ("site", "name", "alt_ft", "datum", "drain_sqmi", "inside_grid", "in_region", "km_to_corridor", "has_stage_that_day")}, flush=True)
(OUT / "inventory.json").write_text(json.dumps(inventory, indent=1))
print("\nusable:", sum(r["inside_grid"] and r["has_stage_that_day"] for r in inventory))
