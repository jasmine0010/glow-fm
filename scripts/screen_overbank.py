"""Screen unread Southeast rivers for the overbank test (research/OVERBANK_PROTOCOL.md).

Uses only USGS site metadata, 15-minute stage, NWS flood stages and catalogue footprints. Reads no radar, flood layer or truth.
Writes research/overbank_screen.json.
"""

import csv
import io
import json
import re
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta

import numpy as np

from hidden_floods.config import REPO_ROOT, data_root
from hidden_floods.fetch import USGS_OGC, get_json
from hidden_floods.stack import CMR, parse

BASINS = {
    "satilla": ("-82.75,30.75,-81.5,31.35", r"^SATILLA RIVER"), "st_marys": ("-82.5,30.25,-81.6,30.95", r"^ST\.? MARY'?S RIVER"),
    "ogeechee": ("-82.8,31.9,-81.2,33.2", r"^OGEECHEE RIVER"), "ochlockonee": ("-84.7,30.2,-83.9,31.4", r"^OCHLOCKONEE RIVER"),
    "suwannee": ("-83.6,29.4,-82.3,30.8", r"^SUWANNEE RIVER"), "alapaha": ("-83.4,30.3,-82.8,31.4", r"^ALAPAHA RIVER"),
    "withlacoochee": ("-83.7,30.3,-82.9,31.2", r"^WITHLACOOCHEE RIVER"), "altamaha": ("-82.9,31.3,-81.4,32.1", r"^ALTAMAHA RIVER"),
    "apalachicola": ("-85.4,29.7,-84.7,30.8", r"^APALACHICOLA RIVER"), "escambia": ("-87.7,30.4,-87.0,31.1", r"^ESCAMBIA RIVER"),
    "perdido": ("-87.7,30.4,-87.2,31.1", r"^PERDIDO RIVER"), "blackwater": ("-87.1,30.5,-86.5,31.0", r"^BLACKWATER RIVER"),
}
START, END = datetime(2026, 8, 1), datetime(2026, 11, 5)
NWS = "https://water.noaa.gov/resources/downloads/reports/nwps_all_gauges_report.csv"
CACHE = data_root() / "screen"


def fetch_text(url, timeout=120):
    req = urllib.request.Request(url, headers={"User-Agent": "hidden-floods"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def sites_in(bbox, pattern):
    text = fetch_text(f"https://waterservices.usgs.gov/nwis/site/?format=rdb&bBox={bbox}&parameterCd=00065&siteType=ST&hasDataTypeCd=iv&siteStatus=active&siteOutput=expanded")
    rows = [ln.split("\t") for ln in text.splitlines() if ln and not ln.startswith("#")]
    recs = [dict(zip(rows[0], r, strict=False)) for r in rows[2:]]
    return [r for r in recs if re.search(pattern, r["station_nm"].upper())]


def stage_series(site_no):
    path = CACHE / f"stage_{site_no}.json"
    if path.exists():
        rows = json.loads(path.read_text())
    else:
        url, rows = f"{USGS_OGC}/continuous/items?" + urllib.parse.urlencode({"f": "json", "monitoring_location_id": f"USGS-{site_no}", "parameter_code": "00065", "time": f"{START:%Y-%m-%dT%H:%M:%SZ}/{END:%Y-%m-%dT%H:%M:%SZ}", "limit": 10000}), []
        while url:
            page = get_json(url, timeout=300)
            rows += [[f["properties"]["time"], f["properties"]["value"]] for f in page.get("features", [])]
            url = next((ln["href"] for ln in page.get("links", []) if ln.get("rel") == "next"), None)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rows))
    good = sorted((datetime.fromisoformat(t.replace("Z", "")[:19]), float(v)) for t, v in rows if v not in (None, ""))
    return ([t.timestamp() for t, _ in good], [v for _, v in good]) if good else None


def stage_at(series, t):
    ts, vs = series
    x = t.timestamp()
    i = int(np.searchsorted(ts, x))
    if i == 0 or i == len(ts) or ts[i] - ts[i - 1] > 3 * 3600:
        return None
    return float(np.interp(x, ts, vs)) * 0.3048


def scenes_covering(lon, lat):
    q = urllib.parse.urlencode({"short_name": "NISAR_L2_GCOV_PROVISIONAL_V1", "point": f"{lon},{lat}", "temporal": f"{START:%Y-%m-%dT%H:%M:%SZ},{END:%Y-%m-%dT%H:%M:%SZ}", "page_size": 200, "sort_key": "start_date"})
    out = {}
    for it in get_json(f"{CMR}?{q}").get("items", []):
        p = parse(it["umm"]["GranuleUR"])
        if p:
            out[it["umm"]["GranuleUR"]] = p
    return out


def main():
    flood = {}
    for r in csv.DictReader(io.StringIO(fetch_text(NWS))):
        keys = {k.strip().lower(): v for k, v in r.items() if k}
        site = (keys.get("usgs id") or keys.get("usgs_id") or keys.get("usgsid") or "").strip()
        value = keys.get("flood stage") or keys.get("flood_stage") or keys.get("flood")
        try:
            if site and float(value) > 0:        # the report uses negative values for "none listed"
                flood[site] = float(value) * 0.3048
        except (TypeError, ValueError):
            pass
    print(f"NWS flood stages: {len(flood)}", flush=True)
    report = {}
    for basin, (bbox, pat) in BASINS.items():
        gauges = []
        for rec in sites_in(bbox, pat):
            series = stage_series(rec["site_no"])
            if series:
                gauges.append({"id": rec["site_no"], "name": rec["station_nm"], "lon": float(rec["dec_long_va"]), "lat": float(rec["dec_lat_va"]), "datum_ft": rec["alt_va"].strip(), "datum": rec["alt_datum_cd"].strip(), "series": series, "flood_m": flood.get(rec["site_no"])})
        by_track = defaultdict(dict)
        for g in gauges:
            for name, p in scenes_covering(g["lon"], g["lat"]).items():
                by_track[(p["track"], p["frame"], p["mode"])].setdefault(p["time"][:19], {"name": name, "gauges": set()})["gauges"].add(g["id"])
        out = []
        for (track, frame, mode), scenes in sorted(by_track.items()):
            ids = sorted(set.union(*[s["gauges"] for s in scenes.values()]))
            gs = [g for g in gauges if g["id"] in ids]
            stage = {t: {g["id"]: stage_at(g["series"], datetime.fromisoformat(t)) for g in gs} for t in scenes}
            times = sorted(stage)
            best = None
            for wet in times:
                tw = datetime.fromisoformat(wet)
                dry_pool = [t for t in times if t != wet and abs(datetime.fromisoformat(t) - tw) <= timedelta(days=60)]
                for g_ok in [[g["id"] for g in gs if stage[wet][g["id"]] is not None]]:
                    pool = [t for t in dry_pool if all(stage[t][i] is not None for i in g_ok)]
                    if len(g_ok) < 2 or not pool:
                        continue
                    dry = min(pool, key=lambda t: np.mean([stage[t][i] for i in g_ok]))
                    rises = {i: stage[wet][i] - stage[dry][i] for i in g_ok}
                    m = float(np.mean(list(rises.values())))
                    if best is None or m > best["mean_rise_m"]:
                        best = {"wet": wet, "dry": dry, "mean_rise_m": m, "rises_m": {i: round(v, 2) for i, v in rises.items()},
                                "above_flood": {i: None if not next(g for g in gs if g["id"] == i)["flood_m"] else bool(stage[wet][i] >= next(g for g in gs if g["id"] == i)["flood_m"]) for i in g_ok}}
            out.append({"track": track, "frame": frame, "mode": mode, "scene_count": len(times), "times": times, "gauges_in_frame": ids, "best": best})
        report[basin] = {"gauges": [{k: v for k, v in g.items() if k != "series"} for g in gauges], "tracks": out}
        print(f"\n== {basin}", flush=True)
        for g in gauges:
            print(f"  {g['id']} {g['name'][:46]} ({g['lon']:.3f},{g['lat']:.3f}) datum {g['datum_ft']} {g['datum']} flood {None if not g['flood_m'] else round(g['flood_m'], 2)} m", flush=True)
        for t in out:
            if t["best"]:
                b = t["best"]
                print(f"  {t['track']}/{t['frame']} {t['mode']} n={t['scene_count']} wet {b['wet'][:13]} dry {b['dry'][:10]} mean {b['mean_rise_m']:.2f} m rises {b['rises_m']} above flood {b['above_flood']}", flush=True)
    (REPO_ROOT / "research" / "overbank_screen.json").write_text(json.dumps(report, indent=1))
    print("SCREEN DONE", flush=True)


if __name__ == "__main__":
    main()
