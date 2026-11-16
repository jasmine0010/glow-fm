"""Was the river in flood when NISAR passed? Writes each US live case's gauge reading at the pass into the case index.

    python scripts/pass_stage.py

A US case is picked because its gauge reached NOAA's minor flood stage at some point in the flood, judged by daily
readings. A gauge that rises and falls with the tide can top that stage for an hour a day, so NISAR's pass may catch the
river below flood stage and lower than in the passes before. Then there's no new water to map, and the run is no test.
This reads USGS's 15-minute gage height nearest the pass and compares it with NOAA's minor flood stage; a case whose
river was below it is marked, and Run it yourself doesn't offer it.

Gage height and NOAA's stage are in the same datum at these gauges: NOAA's observed stage is the USGS feed, and a NOAA
gauge that names a different USGS site gets no verdict (as in scripts/past_us_floods.py). No reading within
NEAR_MIN of the pass also gives no verdict, and the case stays listed. Readings are cached in outputs/pass_stage.
scripts/prepare_all_floods.py runs this after preparing new floods. Added Nov 15, 2026.
"""

import json
import sys
import urllib.parse
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hidden_floods import live
from hidden_floods.config import REPO_ROOT

INDEX = REPO_ROOT / "app" / "data" / "live" / "index.json"
PAST = REPO_ROOT / "outputs" / "past_us_floods.json"
CACHE = REPO_ROOT / "outputs" / "pass_stage"
IV = "https://waterservices.usgs.gov/nwis/iv/"
NEAR_MIN = 45
# Below flood stage at the pass but offered anyway, chosen by hand after seeing the case's score, and said so on the page.
EXEMPT = {
    "us_macf1_20261007": "0.2 ft under flood stage, but 4 to 9 ft above the river at the earlier passes. Offered by exception, "
                         "chosen by hand after seeing its score",
}


def when(s):
    return datetime.fromisoformat(s)


def cached(name, url):
    path = CACHE / name
    if not path.exists():
        path.write_bytes(live._get(url))
    return json.loads(path.read_text(encoding="utf8"))


def minor_stage(lid, usgs, past):
    """NOAA's minor flood stage for this gauge, or None when NOAA's record names another USGS site."""
    hit = next((f for f in past if f["lid"].lower() == lid and f["usgs"] == usgs), None)
    if hit:
        return hit["minor_ft"]
    detail = cached(f"nwps_{lid}.json", f"{live.NWPS}/{lid.upper()}")
    minor = ((detail.get("flood") or {}).get("categories") or {}).get("minor", {}).get("stage")
    return minor if minor and minor > 0 and (detail.get("usgsId") or "") == usgs else None


def stage_at(usgs, t):
    """USGS gage height (ft) nearest time t, and when it was read; None when nothing is within NEAR_MIN."""
    q = urllib.parse.urlencode({"format": "json", "sites": usgs, "parameterCd": "00065",
                                "startDT": f"{(t - timedelta(days=1)):%Y-%m-%d}", "endDT": f"{(t + timedelta(days=1)):%Y-%m-%d}"})
    series = cached(f"iv_{usgs}_{t:%Y%m%d}.json", f"{IV}?{q}")["value"]["timeSeries"]
    readings = [(when(v["dateTime"]).astimezone(UTC), float(v["value"])) for s in series[:1] for v in s["values"][0]["value"]]
    if not readings:
        return None
    at, ft = min(readings, key=lambda r: abs(r[0] - t))
    return (ft, at) if abs(at - t) <= timedelta(minutes=NEAR_MIN) else None


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    index = json.loads(INDEX.read_text(encoding="utf8"))
    past = json.loads(PAST.read_text(encoding="utf8"))["floods"] if PAST.exists() else []
    for c in index["cases"]:
        if c["kind"] != "us":
            continue
        rec = json.loads((INDEX.parent / c["id"] / "case.json").read_text(encoding="utf8"))
        lid, usgs, t = c["id"].split("_")[1], rec.get("usgs"), when(rec["wet"]["time"])
        try:
            minor = minor_stage(lid, usgs, past) if usgs else None
            got = stage_at(usgs, t) if minor is not None else None
        except Exception as err:  # noqa: BLE001
            print(f"  {c['id']}: no reading ({err})")
            minor = got = None
        if got is None:
            c.pop("pass_stage", None)
            print(f"?    {c['id']}: no verdict")
            continue
        ft, at = got
        c["pass_stage"] = {"ft": ft, "flood_ft": minor, "read_utc": f"{at:%Y-%m-%dT%H:%M}Z", "in_flood": ft >= minor}
        if ft < minor and c["id"] in EXEMPT:
            c["pass_stage"]["exempt"] = EXEMPT[c["id"]]
        print(f"{'in ' if ft >= minor else 'EXEMPT' if c['id'] in EXEMPT else 'OUT'}  {c['id']}: {ft:.2f} ft at the pass, flood stage {minor} ft")
    INDEX.write_text(json.dumps(index, indent=2, default=str), encoding="utf8")
    print("PASS STAGE DONE")


if __name__ == "__main__":
    main()
