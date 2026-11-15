"""One-time run of research/TRIBUTARY_GAUGE_PROTOCOL.md. Refuses to overwrite its results. Reads saved maps and public gauges."""
import csv
import hashlib
import http.client
import io
import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
from pyproj import Transformer
from scipy.stats import spearmanr

from hidden_floods.config import load_site
from hidden_floods.io.dem import dem_on_grid
from hidden_floods.pipeline import analysis_grid
from hidden_floods.sitegen import ngvd29_to_navd88_ft
from hidden_floods.stamps import stamp
from hidden_floods.truth import connected_to_channel
from hidden_floods.v3 import LC_OTHER, LC_TREE, LC_WETLAND

ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "research/tributary_gauge_results.json"
if RESULT.exists():
    sys.exit(f"{RESULT.name} already exists: this check runs once.")
UA = {"User-Agent": "hidden-floods-research/0.1"}
FT = 0.3048
EXCLUDE = {"02319302"}  # Madison Blue Spring
NWS = "https://water.noaa.gov/resources/downloads/reports/nwps_all_gauges_report.csv"


CACHE = ROOT / "outputs/tributary_gauges/cache"
CACHE.mkdir(parents=True, exist_ok=True)


def get(url, timeout=120, tries=8):
    saved = CACHE / hashlib.sha256(url.encode()).hexdigest()
    if saved.exists():
        return saved.read_text(encoding="utf8")
    for attempt in range(tries):
        try:
            text = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read().decode()
            saved.write_text(text, encoding="utf8")
            return text
        except (OSError, http.client.HTTPException):  # a dropped connection doesn't change any input, so the read is repeated
            if attempt == tries - 1:
                raise
            time.sleep(15 * (attempt + 1))
    raise RuntimeError(url)


def parse(t):
    return datetime.fromisoformat(t.replace("Z", "+00:00"))


def series(site_no, when):
    start, end = (when - timedelta(days=80)).strftime("%Y-%m-%dT%H:%MZ"), (when + timedelta(days=75)).strftime("%Y-%m-%dT%H:%MZ")
    q = urllib.parse.urlencode({"format": "json", "sites": site_no, "parameterCd": "00065", "startDT": start, "endDT": end, "siteStatus": "all"})
    best = []
    for ts in json.loads(get(f"https://waterservices.usgs.gov/nwis/iv/?{q}"))["value"]["timeSeries"]:
        nodata = ts["variable"]["noDataValue"]
        for block in ts["values"]:
            pts = [(parse(v["dateTime"]).timestamp(), float(v["value"])) for v in block["value"] if float(v["value"]) != nodata and float(v["value"]) > -900]
            if len(pts) > len(best):
                best = pts
    return np.array(best) if best else None


def stage_at(s, when, gap_h=6):
    if s is None:
        return None
    t = when.timestamp()
    k = int(np.argmin(np.abs(s[:, 0] - t)))
    return None if abs(s[k, 0] - t) > gap_h * 3600 else float(np.interp(t, s[:, 0], s[:, 1]))


def baseline_times(river, pair):
    over = json.loads((ROOT / "research/overbank_scenes.json").read_text())
    if river in over and pair in over[river]["passes"]:
        p = over[river]["passes"][pair]
        return [s["time"] for s in p["scenes"] if s["time"] != p["wet_time"]]
    v = json.loads((ROOT / "research/v4_test_scenes.json").read_text())[river]
    day = pair[-5:]
    months = {"jul": "07", "oct": "10"}
    tag = f"2026-{months[day[:3]]}-{day[3:]}"
    return [s["time"] for s in v["scenes"] if s["time"][:10] != tag]


proto = hashlib.sha256((ROOT / "research/TRIBUTARY_GAUGE_PROTOCOL.md").read_bytes()).hexdigest()
inv = [r for r in json.loads((ROOT / "outputs/tributary_gauges/inventory.json").read_text()) if r["inside_grid"] and r["has_stage_that_day"] and r["site"] not in EXCLUDE]
flood = {}
try:
    for r in csv.DictReader(io.StringIO(get(NWS))):
        keys = {k.strip().lower(): v for k, v in r.items() if k}
        sid = (keys.get("usgs id") or keys.get("usgs_id") or keys.get("usgsid") or "").strip()
        try:
            if sid and float(keys.get("flood stage") or keys.get("flood_stage") or keys.get("flood")) > 0:
                flood[sid] = float(keys.get("flood stage") or keys.get("flood_stage") or keys.get("flood"))
        except (TypeError, ValueError):
            pass
except Exception as e:
    print("NWS list unavailable", repr(e)[:100])

rows = []
for r in inv:
    river, pair, sid = r["river"], r["pair"], r["site"]
    site = load_site(river)
    grid = analysis_grid(site)
    when = parse(site.pairs[pair].wet_time)
    z = np.load(ROOT / "outputs" / river / pair / "frozen_v4_layers.npz")
    X, Y = np.meshgrid(grid.xs, grid.ys)
    x, y = Transformer.from_crs(4326, grid.crs, always_xy=True).transform(r["lon"], r["lat"])
    dist = np.hypot(X - x, Y - y)
    disc = dist <= 1000
    outside = ~np.isfinite(z["depth"])
    mappable = disc & outside & np.isin(z["landcover"], (LC_TREE, LC_WETLAND, LC_OTHER)) & (z["hand"] < 6) & np.isfinite(z["d_hh"]) & z["mapped"]
    flagged = z["pred"] & mappable
    row = {"river": river, "pair": pair, "site": sid, "name": r["name"], "drain_sqmi": r["drain_sqmi"], "disc_px": int(disc.sum()), "mappable_px": int(mappable.sum()), "flagged_px": int(flagged.sum())}
    row["flagged_share"] = None if row["mappable_px"] < 100 else round(row["flagged_px"] / row["mappable_px"], 3)

    dem = dem_on_grid(site.dem_path, grid)
    alt = str(r["alt_ft"]).strip()
    datum_ok = False
    offset = 0.0
    if alt and float(alt) != 0 and r["datum"] in ("NAVD88", "NGVD29"):
        if r["datum"] == "NGVD29":
            offset = ngvd29_to_navd88_ft(r["lon"], r["lat"])
        datum_m = (float(alt) + offset) * FT
        near = dem[dist <= 200]
        low = float(np.nanmin(near)) if np.isfinite(near).any() else None
        row["datum_m"], row["lowest_ground_200m_m"] = round(datum_m, 2), None if low is None else round(low, 2)
        datum_ok = low is not None and low - 15 <= datum_m <= low + 5
    row["datum_ok"] = datum_ok

    s = series(sid, when)
    ft = stage_at(s, when)
    row["stage_ft"] = None if ft is None else round(ft, 2)
    base = [v for v in (stage_at(s, parse(t)) for t in baseline_times(river, pair)) if v is not None]
    row["baseline_scenes_read"] = len(base)
    row["rise_m"] = None if ft is None or len(base) < 3 else round((ft - float(np.median(base))) * FT, 2)
    row["elevated"] = None if row["rise_m"] is None else row["rise_m"] >= 1.0
    row["flood_stage_ft"] = flood.get(sid)
    row["above_flood_stage"] = None if ft is None or sid not in flood else ft >= flood[sid]

    if datum_ok and ft is not None and row["mappable_px"] >= 100:
        water = (ft + float(alt) + offset) * FT
        depth = water - dem
        below = disc & (depth > 0)
        wet = connected_to_channel(below, dist <= 300) & (depth > 0.5) & mappable
        dry = mappable & (depth < -0.5) & (depth > -5)
        row.update({"water_surface_m": round(water, 2), "wet_px": int(wet.sum()), "dry_px": int(dry.sum()), "flagged_wet_px": int((flagged & wet).sum()), "flagged_dry_px": int((flagged & dry).sum()), "flagged_near_line_or_other_px": int((flagged & ~wet & ~dry).sum())})
    rows.append(row)
    print({k: row.get(k) for k in ("river", "pair", "name", "mappable_px", "flagged_px", "flagged_share", "datum_ok", "stage_ft", "flood_stage_ft", "rise_m", "elevated", "water_surface_m", "lowest_ground_200m_m", "wet_px", "dry_px", "flagged_wet_px", "flagged_dry_px")}, flush=True)


def pooled(pairs):
    tp, fp = sum(p["flagged_wet_px"] for p in pairs), sum(p["flagged_dry_px"] for p in pairs)
    w, d = sum(p["wet_px"] for p in pairs), sum(p["dry_px"] for p in pairs)
    return {"flagged_wet": tp, "flagged_dry": fp, "local_precision": None if tp + fp == 0 else round(tp / (tp + fp), 3), "chance": None if w + d == 0 else round(w / (w + d), 3), "dry_share_of_flagged": None if tp + fp == 0 else round(fp / (tp + fp), 3)}


usable = [p for p in rows if "wet_px" in p and p["flagged_wet_px"] + p["flagged_dry_px"] >= 20]
out = {"protocol_sha256": proto, **stamp("run"), "pairs": rows, "usable_pairs": len(usable)}
if len(usable) >= 3:
    rng = np.random.default_rng(20261108)
    lifts = []
    for _ in range(2000):
        sample = [usable[i] for i in rng.integers(0, len(usable), len(usable))]
        tp, fp = sum(p["flagged_wet_px"] for p in sample), sum(p["flagged_dry_px"] for p in sample)
        w, d = sum(p["wet_px"] for p in sample), sum(p["dry_px"] for p in sample)
        if tp + fp and w + d:
            lifts.append(tp / (tp + fp) - w / (w + d))
    lo, hi = np.percentile(lifts, [2.5, 97.5])
    all_pool = pooled(usable)
    lift = all_pool["local_precision"] - all_pool["chance"]
    out["reading_1"] = {**all_pool, "lift": round(lift, 3), "lift_ci": [round(float(lo), 3), round(float(hi), 3)], "reading": "flags track measured water" if lo > 0 else "not shown"}
    share = all_pool["dry_share_of_flagged"]
    out["reading_2"] = {"dry_share_of_flagged": share, "reading": "mostly above measured water" if share >= 0.8 else "mostly below" if share <= 0.2 else "mixed"}
else:
    out["reading_1"] = {"reading": "no verdict", "pairs": len(usable)}
    out["reading_2"] = {"reading": "no verdict", **pooled(usable)}
ok = [p for p in rows if p["flagged_share"] is not None and p["rise_m"] is not None]
up, flat = [p["flagged_share"] for p in ok if p["elevated"]], [p["flagged_share"] for p in ok if not p["elevated"]]
out["reading_3"] = {"pairs": len(ok), "elevated_n": len(up), "not_elevated_n": len(flat), "elevated_mean_flagged_share": None if not up else round(float(np.mean(up)), 3), "not_elevated_mean_flagged_share": None if not flat else round(float(np.mean(flat)), 3)}
if len(ok) >= 4:
    rho = spearmanr([p["rise_m"] for p in ok], [p["flagged_share"] for p in ok])
    out["reading_3"]["spearman"] = round(float(rho.statistic), 2)
out["by_river"] = {river: pooled([p for p in usable if p["river"] == river]) for river in sorted({p["river"] for p in usable})}
RESULT.write_text(json.dumps(out, indent=1))
print(json.dumps({k: out[k] for k in ("usable_pairs", "reading_1", "reading_2", "reading_3", "by_river")}, indent=1))
print("protocol", proto)
