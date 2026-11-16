"""Screen every NISAR pass, Jun 21 - Nov 15, 2026, over the forested rivers no frozen test or live run has read.

    python scripts/screen_expansion.py

Like scripts/screen_overbank.py, it uses only USGS site metadata, 15-minute stage, NWS flood stages and catalogue
footprints, and reads no radar, flood layer or truth. Unlike it, it keeps every pass, not only each track's best,
and reads both NISAR catalogues: PROVISIONAL up to Oct 21 and GCOV V1 after (a pair never mixes the two).

For each pass on each track and frame: the dry pass is the one with the lowest mean gauge stage within 60 days on the
same track, frame and catalogue (SECOND_EVENT_PROTOCOL.md section 2(b)); each gauge's rise over it; each gauge's margin
over its NWS flood stage; and how many earlier passes the track has for v4's baseline. A pass meets 2(b) when at least
two gauges read at both times and one rose more than 1.0 m. Writes research/expansion_screen.json.
"""

import csv
import io
import json
import re
import sys
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hidden_floods.config import REPO_ROOT, data_root
from hidden_floods.fetch import USGS_OGC, get_json
from hidden_floods.live import NAME
from hidden_floods.stack import CMR

# Rivers in research/overbank_screen.json that the overbank test didn't take, and research/THIRD_STORM_SCREEN.md's
# ranks 6-8. Rivers with a frozen test or a prepared Run it yourself case are left out (EXCLUDED records why).
BASINS = {
    "ogeechee": ("-82.8,31.9,-81.2,33.2", r"^OGEECHEE RIVER"), "suwannee": ("-83.6,29.4,-82.3,30.8", r"^SUWANNEE RIVER"),
    "altamaha": ("-82.9,31.3,-81.4,32.1", r"^ALTAMAHA RIVER"), "apalachicola": ("-85.4,29.7,-84.7,30.8", r"^APALACHICOLA RIVER"),
    "escambia": ("-87.7,30.4,-87.0,31.1", r"^ESCAMBIA RIVER"), "perdido": ("-87.7,30.4,-87.2,31.1", r"^PERDIDO RIVER"),
    "blackwater": ("-87.1,30.5,-86.5,31.0", r"^BLACKWATER RIVER"), "tar": ("-78.1,35.6,-76.9,36.1", r"^TAR RIVER"),
    "trinity_lower": ("-95.1,29.8,-94.6,30.7", r"^TRINITY R"), "ef_san_jacinto": ("-95.35,29.95,-94.95,30.6", r"^E\.? ?F(OR)?K\.? SAN JACINTO"),
}
EXCLUDED = "Rivers with a frozen test (Pearl, Tangipahoa, Yellow, Choctawhatchee, Village Creek, Pine Island Bayou, Pee Dee, " \
           "Neuse, lower Sabine, Satilla, Alapaha, Ochlockonee, Withlacoochee, St Marys) or a prepared Run it yourself case."
START, END, SWITCH = datetime(2026, 6, 21), datetime(2026, 11, 15, 23, 59), datetime(2026, 10, 21, 17, 7)
COLLECTIONS = (("NISAR_L2_GCOV_PROVISIONAL_V1", START, SWITCH), ("NISAR_L2_GCOV_V1", SWITCH, END))
NWS = "https://water.noaa.gov/resources/downloads/reports/nwps_all_gauges_report.csv"
CACHE = data_root() / "screen_expansion"
RISE_M, PAIR_DAYS = 1.0, 60


def fetch_text(url, timeout=120):
    path = CACHE / ("nws.csv" if url == NWS else re.sub(r"[^A-Za-z0-9]+", "_", url)[-120:] + ".txt")
    if not path.exists():
        path.write_text(get_text(url, timeout), encoding="utf8")
    return path.read_text(encoding="utf8")


def get_text(url, timeout):
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
        path.write_text(json.dumps(rows))
    good = sorted((datetime.fromisoformat(t.replace("Z", "")[:19]), float(v)) for t, v in rows if v not in (None, ""))
    return ([t.timestamp() for t, _ in good], [v for _, v in good]) if good else None


def stage_at(series, t):
    """Stage in metres at time t, or None when the record has a gap of more than 3 hours there."""
    ts, vs = series
    x = t.timestamp()
    i = int(np.searchsorted(ts, x))
    if i == 0 or i == len(ts) or ts[i] - ts[i - 1] > 3 * 3600:
        return None
    return float(np.interp(x, ts, vs)) * 0.3048


def scenes_covering(lon, lat):
    """40 MHz HH+HV scenes over a point, from the catalogue that holds each date: {name: (track, frame, catalogue, time)}."""
    out = {}
    for short, lo, hi in COLLECTIONS:
        q = urllib.parse.urlencode({"short_name": short, "point": f"{lon},{lat}", "temporal": f"{lo:%Y-%m-%dT%H:%M:%SZ},{hi:%Y-%m-%dT%H:%M:%SZ}", "page_size": 200, "sort_key": "start_date"})
        for it in get_json(f"{CMR}?{q}").get("items", []):
            m = NAME.search(it["umm"]["GranuleUR"])
            if m and m[5] == "4005" and m[6] == "DHDH":
                t = m[7]
                out[it["umm"]["GranuleUR"]] = (m[2] + m[3], m[4], short, f"{t[:4]}-{t[4:6]}-{t[6:8]}T{t[9:11]}:{t[11:13]}:{t[13:15]}")
    return out


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
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
    report, rows = {"window": [f"{START:%Y-%m-%d}", f"{END:%Y-%m-%d}"], "excluded": EXCLUDED, "basins": {}}, []
    for basin, (bbox, pat) in BASINS.items():
        gauges = []
        for rec in sites_in(bbox, pat):
            series = stage_series(rec["site_no"])
            if series:
                gauges.append({"id": rec["site_no"], "name": rec["station_nm"], "lon": float(rec["dec_long_va"]), "lat": float(rec["dec_lat_va"]),
                               "datum": rec["alt_datum_cd"].strip(), "series": series, "flood_m": flood.get(rec["site_no"])})
        by_track = defaultdict(dict)
        for g in gauges:
            for name, (track, frame, short, t) in scenes_covering(g["lon"], g["lat"]).items():
                by_track[(track, frame, short)].setdefault(t, {"name": name, "gauges": set()})["gauges"].add(g["id"])
        passes = []
        for (track, frame, short), scenes in sorted(by_track.items()):
            times = sorted(scenes)
            for wet in times:
                tw = datetime.fromisoformat(wet)
                gs = [g for g in gauges if g["id"] in scenes[wet]["gauges"] and stage_at(g["series"], tw) is not None]
                pool = [t for t in times if t != wet and abs(datetime.fromisoformat(t) - tw) <= timedelta(days=PAIR_DAYS)
                        and all(stage_at(g["series"], datetime.fromisoformat(t)) is not None for g in gs)]
                row = {"basin": basin, "track": track, "frame": frame, "catalogue": short.replace("NISAR_L2_GCOV_", ""), "wet": wet,
                       "earlier_passes": sum(t < wet for t in times), "gauges": len(gs)}
                if len(gs) >= 2 and pool:
                    dry = min(pool, key=lambda t: np.mean([stage_at(g["series"], datetime.fromisoformat(t)) for g in gs]))
                    td = datetime.fromisoformat(dry)
                    rises = {g["id"]: round(stage_at(g["series"], tw) - stage_at(g["series"], td), 2) for g in gs}
                    margins = {g["id"]: None if not g["flood_m"] else round(stage_at(g["series"], tw) - g["flood_m"], 2) for g in gs}
                    known = [v for v in margins.values() if v is not None]
                    row |= {"dry": dry, "rises_m": rises, "mean_rise_m": round(float(np.mean(list(rises.values()))), 2), "max_rise_m": max(rises.values()),
                            "flood_margin_m": margins, "gauges_above_flood": sum(v >= 0 for v in known), "gauges_with_flood_stage": len(known),
                            "meets_2b": max(rises.values()) > RISE_M}
                passes.append(row)
        report["basins"][basin] = {"gauges": [{k: v for k, v in g.items() if k != "series"} for g in gauges], "passes": passes}
        rows += passes
        print(f"== {basin}: {len(gauges)} gauges, {len(passes)} passes, {sum(p.get('meets_2b', False) for p in passes)} meet 2(b), "
              f"{sum(p.get('gauges_above_flood', 0) > 0 for p in passes)} with a gauge above flood stage", flush=True)
    (REPO_ROOT / "research" / "expansion_screen.json").write_text(json.dumps(report, indent=1))
    print("\nPasses that meet 2(b) or have a gauge above flood stage:")
    for p in sorted(rows, key=lambda p: (-p.get("gauges_above_flood", 0), -p.get("max_rise_m", 0))):
        if p.get("meets_2b") or p.get("gauges_above_flood"):
            print(f"  {p['basin']:15} {p['track']}/{p['frame']} {p['catalogue']:11} wet {p['wet'][:16]} dry {p['dry'][:10]} "
                  f"max rise {p['max_rise_m']:.2f} m, {p['gauges_above_flood']}/{p['gauges_with_flood_stage']} above flood, "
                  f"margins {p['flood_margin_m']}, {p['earlier_passes']} earlier passes")
    print("SCREEN DONE", flush=True)


if __name__ == "__main__":
    main()
