"""US floods from the past N days, not only the ones in flood now: the river gauges that reached NOAA's minor flood stage.

    python scripts/past_us_floods.py            # the list, into outputs/past_us_floods.json
    python scripts/past_us_floods.py --days 60

The live job (scripts/live_cases.py, frozen) takes NOAA gauges at flood stage *now*, and NOAA's own record of each goes back
30 days, so a US flood that has already receded never becomes a case. The world list looks back 60 days (GDACS), so this
does the same for the US, in three steps:

1. USGS daily gage height for every state over the window (one request per state): the daily maximum where USGS
   publishes one, the daily mean elsewhere (about seven times as many sites have a mean; a flood day's mean still
   tops the minor stage unless the flood lasted only hours).
2. Sites whose level rose at least RISE_FT, matched to the NOAA gauge at the same place (within MATCH_M).
3. NOAA's minor flood stage for each match (one request per gauge), kept only if that NOAA gauge names this USGS site and
   a daily maximum reached the minor stage. The flood runs from the first such day to the day after the last.

Gage height and NOAA's stage are read in the same gauge datum at USGS-run gauges (NOAA's observed stage at these sites is
the USGS feed); a gauge whose NOAA record names a different USGS site is left out. Tidal gauges and lakes are left out, as
in the live job, and so are gauges read in a tidal datum ("in MHHW"). scripts/prepare_all_floods.py takes this list as extra candidates.
"""

import argparse
import json
import math
import re
import sys
import time
import urllib.parse
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hidden_floods import live
from hidden_floods.config import REPO_ROOT

OUT = REPO_ROOT / "outputs" / "past_us_floods.json"
DV = "https://waterservices.usgs.gov/nwis/dv/"
STATES = (
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA",
    "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK",
    "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "PR",
)
RISE_FT = 2.0          # a rise smaller than this over the window isn't a flood worth looking up
MATCH_M = 400.0        # a NOAA gauge and a USGS site this close are the same gauge
TIDAL_DATUM = re.compile(r"MHHW|MLLW|NAVD", re.IGNORECASE)   # stages read in a tidal or survey datum, not the gauge's own
HAS_LEVELS = {"no_flooding", "action", "minor", "moderate", "major", "low_threshold", "obs_not_current"}


def metres(a, b):
    """Distance between two (lat, lon) points, in metres (equirectangular, fine at these distances)."""
    k = math.cos(math.radians((a[0] + b[0]) / 2))
    return 111_320 * math.hypot(a[0] - b[0], (a[1] - b[1]) * k)


def daily_max(state, start, end):
    """{site: {name, lat, lon, days: [(date, ft)], stat}} for one state's daily gage height: maxima where published, else means."""
    q = urllib.parse.urlencode({"format": "json", "stateCd": state, "parameterCd": "00065", "statCd": "00001,00003",
                                "startDT": start.isoformat(), "endDT": end.isoformat(), "siteStatus": "all"})
    try:
        body = json.loads(live._get(f"{DV}?{q}", timeout=180))
    except Exception as e:  # noqa: BLE001  (a state with no daily gage height answers with an error; it simply has none)
        print(f"  {state}: no daily levels ({type(e).__name__})", flush=True)
        return {}
    out = {}
    for ts in body["value"]["timeSeries"]:
        info, stat = ts["sourceInfo"], ts["variable"]["options"]["option"][0].get("optionCode")
        days = [(v["dateTime"][:10], float(v["value"])) for v in (ts["values"][0]["value"] if ts["values"] else []) if v["value"] not in ("", "-999999")]
        sid = info["siteCode"][0]["value"]
        if not days or (sid in out and out[sid]["stat"] == "00001"):     # a maximum beats a mean
            continue
        loc = info["geoLocation"]["geogLocation"]
        out[sid] = {"name": info["siteName"], "lat": loc["latitude"], "lon": loc["longitude"], "days": days, "stat": stat}
    return out


def find(days, now):
    start, end = (now - timedelta(days=days)).date(), now.date()
    # NOAA's gauge list is large and its server times out now and then: a copy from the last day stands in.
    saved = REPO_ROOT / "outputs" / "nwps_gauges.json"
    try:
        gauges = json.loads(live._get(live.NWPS, timeout=180))["gauges"]
        saved.parent.mkdir(parents=True, exist_ok=True)
        saved.write_text(json.dumps(gauges))
    except Exception:
        if not saved.exists() or time.time() - saved.stat().st_mtime > 86_400:
            raise
        print("NOAA's gauge list didn't answer; using the copy from the last day", flush=True)
        gauges = json.loads(saved.read_text())
    nwps = [g for g in gauges
            if ((g.get("status") or {}).get("observed") or {}).get("floodCategory") in HAS_LEVELS
            and not live.TIDAL.search(g["name"]) and not live.LAKE.search(g["name"]) and not TIDAL_DATUM.search(g["name"])]
    print(f"{len(nwps):,} NOAA gauges with flood levels; reading {days} days of USGS daily maxima by state", flush=True)
    risen = {}
    for st in STATES:
        sites = daily_max(st, start, end)
        for sid, s in sites.items():
            vals = [v for _, v in s["days"]]
            if max(vals) - min(vals) >= RISE_FT:
                risen[sid] = s | {"state": st}
        time.sleep(0.3)
    print(f"{len(risen):,} USGS sites rose at least {RISE_FT} ft", flush=True)
    floods, checked = [], 0
    for sid, s in risen.items():
        near = min(nwps, key=lambda g: metres((s["lat"], s["lon"]), (g["latitude"], g["longitude"])))
        if metres((s["lat"], s["lon"]), (near["latitude"], near["longitude"])) > MATCH_M:
            continue
        checked += 1
        try:
            detail = json.loads(live._get(f"{live.NWPS}/{near['lid']}"))
        except Exception:  # noqa: BLE001, S112
            continue
        minor = ((detail.get("flood") or {}).get("categories") or {}).get("minor", {}).get("stage")
        if minor is None or minor <= 0 or (detail.get("usgsId") or "") != sid:
            continue
        over = [d for d, v in s["days"] if v >= minor]
        # Above "flood stage" on nearly every day of the window is a datum that doesn't match NOAA's, not a flood.
        if not over or len(over) > 0.8 * len(s["days"]):
            continue
        top = max(v for _, v in s["days"])
        cats = (detail.get("flood") or {}).get("categories") or {}
        # How bad it got at its peak, in NOAA's own categories.
        category = next((k for k in ("major", "moderate") if (cats.get(k) or {}).get("stage") not in (None, -9999) and top >= cats[k]["stage"] > 0), "minor")
        floods.append({"lid": near["lid"], "name": near["name"], "state": (near.get("state") or {}).get("abbreviation", s["state"]),
                       "lat": near["latitude"], "lon": near["longitude"], "usgs": sid, "minor_ft": minor, "peak_ft": top, "category": category,
                       "peak_day": next(d for d, v in s["days"] if v == top), "daily": "max" if s["stat"] == "00001" else "mean",
                       "from": f"{over[0]}T00:00:00Z", "to": f"{(datetime.fromisoformat(over[-1]) + timedelta(days=1)).date()}T23:59:59Z",
                       "ongoing": over[-1] == s["days"][-1][0], "from_is_window_start": over[0] == s["days"][0][0]})
        time.sleep(0.2)
    print(f"{checked} matched NOAA gauges looked up; {len(floods)} reached minor flood stage", flush=True)
    out = {"made_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "days": days, "rise_ft": RISE_FT, "match_m": MATCH_M, "floods": floods}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1))
    for f in sorted(floods, key=lambda f: f["from"]):
        print(f"  {f['lid']:6} {f['from'][:10]} to {f['to'][:10]}  {f['name']}, {f['state']}{'  (ongoing)' if f['ongoing'] else ''}")
    print(f"-> {OUT}")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=60)
    find(ap.parse_args().days, datetime.now(UTC))
