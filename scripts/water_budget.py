"""One-time run of research/WATER_BUDGET_PROTOCOL.md. Refuses to overwrite its results."""
import hashlib
import http.client
import itertools
import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

from hidden_floods.audit import GAUGE_SUPPORT_M, reference_water
from hidden_floods.config import load_site
from hidden_floods.io.dem import dem_on_grid
from hidden_floods.io.gauges import water_surface_navd88_m
from hidden_floods.pipeline import analysis_grid
from hidden_floods.selfcal import gauge_supported
from hidden_floods.stamps import stamp
from hidden_floods.truth import ValleyLine, connected_to_channel, interpolate_wse, refine_centerline

ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "research/water_budget_results.json"
if RESULT.exists():
    sys.exit(f"{RESULT.name} already exists: this check runs once.")
CACHE = ROOT / "outputs/water_budget/cache"
CACHE.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "hidden-floods-research/0.1"}
CFS = 0.0283168
NOW = datetime.now(UTC)
EVENTS = {"satilla": "047A_oct15", "ochlockonee": "026D_oct14", "st_marys": "098D_oct07", "pee_dee": "098D_jul27", "neuse": "090A_jul26", "lower_sabine": "134A_jul17",
          "yellow": "055D_oct16", "choctawhatchee": "076A_oct17", "pearl": "105A_jul03", "tangipahoa": "105A_jun21", "pine_island": "012D_sep07", "village_creek": "134A_sep03"}


def get(url, tries=8):
    saved = CACHE / hashlib.sha256(url.encode()).hexdigest()
    if saved.exists():
        return saved.read_text(encoding="utf8")
    for attempt in range(tries):
        try:
            text = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120).read().decode()
            saved.write_text(text, encoding="utf8")
            return text
        except (OSError, http.client.HTTPException):
            if attempt == tries - 1:
                raise
            time.sleep(15 * (attempt + 1))
    raise RuntimeError(url)


def series(site_no, param, start, end):
    q = urllib.parse.urlencode({"format": "json", "sites": site_no, "parameterCd": param, "startDT": start.strftime("%Y-%m-%dT%H:%MZ"), "endDT": end.strftime("%Y-%m-%dT%H:%MZ"), "siteStatus": "all"})
    best = []
    for ts in json.loads(get(f"https://waterservices.usgs.gov/nwis/iv/?{q}"))["value"]["timeSeries"]:
        nodata = ts["variable"]["noDataValue"]
        for block in ts["values"]:
            pts = [(datetime.fromisoformat(v["dateTime"]).timestamp(), float(v["value"])) for v in block["value"] if float(v["value"]) != nodata and float(v["value"]) > -900]
            if len(pts) > len(best):
                best = pts
    return np.array(best) if best else None


def on_grid(s, times, gap_h=6):
    """Values at ``times``, NaN when the nearest reading is more than ``gap_h`` away."""
    if s is None:
        return np.full(len(times), np.nan)
    out = np.interp(times, s[:, 0], s[:, 1])
    nearest = np.abs(s[np.clip(np.searchsorted(s[:, 0], times), 0, len(s) - 1), 0] - times)
    earlier = np.abs(s[np.clip(np.searchsorted(s[:, 0], times) - 1, 0, len(s) - 1), 0] - times)
    out[np.minimum(nearest, earlier) > gap_h * 3600] = np.nan
    return out


def drainage(ids):
    q = urllib.parse.urlencode({"format": "rdb", "sites": ",".join(ids), "siteOutput": "expanded", "siteStatus": "all"})
    lines = [x.split("\t") for x in get(f"https://waterservices.usgs.gov/nwis/site/?{q}").splitlines() if x and not x.startswith("#")]
    h = lines[0]
    out = {}
    for r in lines[2:]:
        v = r[h.index("drain_area_va")].strip()
        out[r[h.index("site_no")]] = float(v) if v else None
    return out


proto = hashlib.sha256((ROOT / "research/WATER_BUDGET_PROTOCOL.md").read_bytes()).hexdigest()
reaches, volumes, checks = [], {}, {}
for river, pair in EVENTS.items():
    site = load_site(river)
    grid = analysis_grid(site)
    dem = dem_on_grid(site.dem_path, grid)
    perm = reference_water(site.operational_dir, grid)
    coarse = ValleyLine.from_lonlat(grid, site.valley_line)
    dist0, _ = coarse.project(*grid.meshgrid())
    line = refine_centerline(coarse, perm & (dist0 < site.corridor_m), grid)
    dist, chain = line.project(*grid.meshgrid())
    gxy = [grid.to_xy(g.lon, g.lat) for g in site.gauges]
    _, g_chain = line.project(*map(np.array, zip(*gxy, strict=True)))
    lo, hi = float(np.min(g_chain)), float(np.max(g_chain))
    corridor = (dist < site.corridor_m) & np.isfinite(dem) & (chain >= lo) & (chain <= hi)
    area_m2 = grid.res ** 2
    ref = datetime.fromisoformat(site.pairs[pair].wet_time)
    start, end = ref - timedelta(days=20), min(ref + timedelta(days=25), NOW)
    hours = np.arange(start.timestamp(), end.timestamp(), 3600.0)
    six = hours[::6]
    ids = [g.id.replace("USGS-", "") for g in site.gauges]
    stage = {i: series(i, "00065", start, end) for i in ids}
    flow = {i: series(i, "00060", start, end) for i in ids}
    areas = drainage(ids)
    wse = {i: np.array([water_surface_navd88_m(g, v) if np.isfinite(v) else np.nan for v in on_grid(stage[i], six)]) for i, g in zip(ids, site.gauges, strict=True)}

    def storage_at(values, shift=0.0):
        ok = np.isfinite(values)
        if ok.sum() < 2:
            return None
        depth = interpolate_wse(chain, g_chain[ok], values[ok] + shift) - dem  # noqa: B023
        wet = corridor & (depth > site.margin_m) & connected_to_channel(corridor & (depth > 0), perm) & ~perm  # noqa: B023
        return depth, wet

    # The estimate must reproduce the frozen one at the pass, or nothing here can be trusted.
    ref_vals = np.array([water_surface_navd88_m(g, on_grid(stage[i], np.array([ref.timestamp()]), 2)[0]) if stage[i] is not None else np.nan for i, g in zip(ids, site.gauges, strict=True)])
    result = storage_at(ref_vals)
    frozen_file = next((ROOT / "outputs" / river / pair / n for n in ("frozen_v4_layers.npz", "frozen_v3_layers.npz", "frozen_edouard_layers.npz", "frozen_layers.npz", "frozen_v2_layers.npz", "layers.npz") if (ROOT / "outputs" / river / pair / n).exists()), None)
    supported = gauge_supported(chain, g_chain, GAUGE_SUPPORT_M)
    check = {"pass": pair, "volume_supported_mm3": None if result is None else round(float(np.sum(result[0][result[1] & supported]) * area_m2 / 1e6), 2), "wet_supported_ha": None if result is None else int((result[1] & supported).sum() * area_m2 / 1e4)}
    if frozen_file:
        z = np.load(frozen_file)
        if "region" in z.files and result is not None:
            check["frozen_wet_ha"] = int((z["wet"] & z["region"]).sum() * area_m2 / 1e4)
    checks[river] = check
    print(river, check, flush=True)

    if river == "satilla":
        out = {}
        for shift in (-0.5, 0.0, 0.5):
            d, w = storage_at(ref_vals, shift)
            out[str(shift)] = {"volume_mm3": round(float(np.sum(d[w & supported]) * area_m2 / 1e6), 1), "wet_ha": int((w & supported).sum() * area_m2 / 1e4)}
        q = flow.get("02228000")
        peak = float(np.nanmax(on_grid(q, hours))) * CFS
        volumes["satilla_oct15"] = {"range": out, "atkinson_peak_m3s": round(peak, 0), "days_of_peak_flow": {k: round(v["volume_mm3"] * 1e6 / (peak * 86400), 1) for k, v in out.items()}}
        print(volumes, flush=True)

    # Estimated storage through time, per reach
    with_q = sorted([(float(c), i) for c, i in zip(g_chain, ids, strict=True) if flow[i] is not None], key=lambda t: t[0])
    pairs = list(itertools.pairwise(with_q))
    records = {f"{a[1]}-{b[1]}": [] for a, b in pairs}
    wet_ha = {f"{a[1]}-{b[1]}": [] for a, b in pairs}
    for k in range(len(six)):
        res = storage_at(np.array([wse[i][k] for i in ids]))
        for a, b in pairs:
            key = f"{a[1]}-{b[1]}"
            if res is None:
                records[key].append(np.nan)
                wet_ha[key].append(np.nan)
                continue
            mask = res[1] & (chain >= a[0]) & (chain <= b[0])
            records[key].append(float(np.sum(res[0][mask]) * area_m2))
            wet_ha[key].append(float(mask.sum() * area_m2 / 1e4))
    for a, b in pairs:
        up, dn, key = a[1], b[1], f"{a[1]}-{b[1]}"
        row = {"river": river, "reach": key, "up": up, "down": dn, "km": round((b[0] - a[0]) / 1000, 1), "area_up": areas.get(up), "area_down": areas.get(dn)}
        qu, qd = on_grid(flow[up], hours) * CFS, on_grid(flow[dn], hours) * CFS
        row["flow_coverage"] = round(float(min(np.isfinite(qu).mean(), np.isfinite(qd).mean())), 3)
        est = np.array(records[key])
        ha = np.array(wet_ha[key])
        row["peak_wet_ha"] = None if not np.isfinite(ha).any() else int(np.nanmax(ha))
        row["peak_est_mm3"] = None if not np.isfinite(est).any() else round(float(np.nanmax(est)) / 1e6, 2)
        valid_area = row["area_up"] and row["area_down"] and row["area_down"] > row["area_up"]
        row["ungauged_share"] = None if not valid_area else round((row["area_down"] - row["area_up"]) / row["area_down"], 3)
        row["judged"] = bool(valid_area and row["flow_coverage"] >= 0.9 and row["ungauged_share"] <= 0.40 and (row["peak_wet_ha"] or 0) >= 500)
        if valid_area and row["flow_coverage"] >= 0.5:
            fu, fd = np.interp(hours, hours[np.isfinite(qu)], qu[np.isfinite(qu)]), np.interp(hours, hours[np.isfinite(qd)], qd[np.isfinite(qd)])
            best, lag = -2.0, 0
            for h in range(241):
                if h >= len(fu) - 48:
                    break
                c = np.corrcoef(fu[:len(fu) - h], fd[h:])[0, 1]
                if np.isfinite(c) and c > best:
                    best, lag = float(c), h
            delayed = np.concatenate([np.full(lag, fu[0]), fu[:len(fu) - lag]])
            diff = delayed * row["area_down"] / row["area_up"] - fd
            diff -= np.mean(diff[:72])
            store = np.cumsum(diff) * 3600.0
            s6 = store[::6][:len(est)]
            keep = np.isfinite(est[:len(s6)])
            row["lag_hours"], row["lag_corr"] = lag, round(best, 3)
            row["peak_flow_mm3"] = round(float(np.max(store)) / 1e6, 2)
            if keep.sum() >= 10 and row["peak_est_mm3"]:
                e = est[:len(s6)]
                ratio = row["peak_flow_mm3"] / row["peak_est_mm3"]
                t_est, t_flow = six[int(np.nanargmax(e))], hours[int(np.argmax(store))]
                gap = abs(t_est - t_flow) / 86400
                rho = float(spearmanr(s6[keep], e[keep]).statistic)
                row.update({"ratio": round(ratio, 2), "peak_gap_days": round(gap, 1), "spearman": round(rho, 2), "est_peak_time": datetime.fromtimestamp(t_est, UTC).isoformat()[:13], "flow_peak_time": datetime.fromtimestamp(t_flow, UTC).isoformat()[:13]})
                row["amount_ok"], row["timing_ok"], row["shape_ok"] = bool(1 / 3 <= ratio <= 3), bool(gap <= 3), bool(rho >= 0.6)
                row["consistent"] = row["amount_ok"] and row["timing_ok"] and row["shape_ok"]
            row["days"] = [datetime.fromtimestamp(t, UTC).isoformat()[:10] for t in six[::4]]
            row["estimated_mm3_daily"] = [None if not np.isfinite(v) else round(float(v) / 1e6, 3) for v in e[::4]] if keep.sum() >= 10 and row["peak_est_mm3"] else []
            row["flow_mm3_daily"] = [round(float(v) / 1e6, 3) for v in s6[::4]]
        reaches.append(row)
        print({k: row.get(k) for k in ("river", "reach", "km", "ungauged_share", "flow_coverage", "peak_wet_ha", "peak_est_mm3", "peak_flow_mm3", "ratio", "peak_gap_days", "spearman", "lag_hours", "judged", "consistent")}, flush=True)

judged = [r for r in reaches if r["judged"] and "consistent" in r]
n, ok = len(judged), sum(r["consistent"] for r in judged)
overall = "no verdict" if n < 3 else "supported" if ok / n >= 2 / 3 else "not supported" if ok / n <= 1 / 3 else "mixed"
out = {"protocol_sha256": proto, **stamp("run"), "judged": n, "consistent": ok, "overall": overall, "satilla": [{k: r.get(k) for k in ("reach", "km", "ungauged_share", "judged", "peak_est_mm3", "peak_flow_mm3", "ratio", "peak_gap_days", "spearman", "consistent")} for r in reaches if r["river"] == "satilla"], "volumes": volumes, "reproduction_checks": checks, "reaches": reaches}
RESULT.write_text(json.dumps(out, indent=1))
print(json.dumps({k: out[k] for k in ("judged", "consistent", "overall", "satilla", "volumes")}, indent=1))
print("protocol", proto)
