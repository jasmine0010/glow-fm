"""How often, and how soon, NISAR sees a flood while it is happening.

    python scripts/build_coverage.py

For every flood in the saved worldwide list (app/data/dashboard/world_floods.json: floods GDACS reported over 60 days,
one reported point each), this asks NASA's CMR catalog, which needs no login, for every NISAR GCOV scene covering that
point during the flood. For each scene it keeps when it was recorded and when it first entered the catalog (the
earliest "Insert" date across the provisional and final collections), so the delay between the two is the wait before
anyone can use it. Scenes of the kind the method needs (40 MHz, HH and HV) are counted separately.

Writes app/data/figures/coverage.json. It describes NISAR's first season as the catalog shows it on the day it's run;
rerun it to update. GDACS's dates for a flood still in progress run to its latest report, so "during the flood" is
GDACS's window, not a measured flood duration.
"""

import json
import re
import time
import urllib.parse
import urllib.request
from datetime import UTC, datetime

import numpy as np
from build_app import DATA

CMR = "https://cmr.earthdata.nasa.gov/search/granules.umm_json"
COLLECTIONS = ("NISAR_L2_GCOV_PROVISIONAL_V1", "NISAR_L2_GCOV_V1")
NAME = re.compile(r"GCOV_(\d+)_(\d+)_([AD])_(\d+)_(\d+)_([A-Z]+)_[AM]_(\d{8}T\d{6})_\d{8}T\d{6}_")
DAY_MS = 86_400_000
OUT = DATA / "figures" / "coverage.json"


def get_json(url):
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "research-client"}), timeout=90) as r:
                return json.loads(r.read())
        except Exception:
            if attempt == 3:
                raise
            time.sleep(5 * (attempt + 1))
    return None


def ms(text):
    return int(datetime.fromisoformat(text).timestamp() * 1000)


def iso(t_ms):
    return datetime.fromtimestamp(t_ms / 1000, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def scenes(lon, lat, start_ms, end_ms):
    """Each NISAR GCOV acquisition over the point in the window: when recorded, when first in the catalog, and its kind."""
    found = {}
    for short in COLLECTIONS:
        page = 1
        while True:
            q = urllib.parse.urlencode({"short_name": short, "point": f"{lon:.5f},{lat:.5f}", "temporal": f"{iso(start_ms)},{iso(end_ms)}",
                                        "page_size": 200, "page_num": page})
            items = get_json(f"{CMR}?{q}").get("items", [])
            for it in items:
                u, m = it["umm"], NAME.search(it["umm"]["GranuleUR"])
                if not m:
                    continue
                begin = ms(u["TemporalExtent"]["RangeDateTime"]["BeginningDateTime"])
                inserts = [ms(d["Date"]) for d in u.get("ProviderDates") or [] if d.get("Type") == "Insert"] or [ms(it["meta"]["revision-date"])]
                key = (m[2], m[3], m[4], begin // 60_000)                     # track, direction, frame, minute
                kind = m[5] == "4005" and m[6] == "DHDH"                       # what the method reads
                rec = found.get(key)
                if rec is None or min(inserts) < rec["insert"]:
                    found[key] = {"begin": begin, "insert": min(inserts), "kind": kind or (rec or {}).get("kind", False), "dir": m[3]}
                else:
                    rec["kind"] = rec["kind"] or kind
            if len(items) < 200:
                break
            page += 1
    return sorted(found.values(), key=lambda s: s["begin"])


def main():
    saved = json.loads((DATA / "dashboard" / "world_floods.json").read_text(encoding="utf8"))
    now = int(time.time() * 1000)
    rows = []
    for e in saved["events"]:
        start, end = e["from"], min(e["to"], now)
        if end <= start:
            continue
        ss = scenes(e["lon"], e["lat"], start, end)
        method = [s for s in ss if s["kind"]]
        first_pass = (ss[0]["begin"] - start) / DAY_MS if ss else None
        first_ready = (min(s["insert"] for s in ss) - start) / DAY_MS if ss else None
        rows.append({"id": e["id"], "country": e["country"], "alert": e["alert"], "lat": e["lat"], "lon": e["lon"], "from": iso(start), "to": iso(end),
                     "days": round((end - start) / DAY_MS, 2), "passes": len(ss), "method_passes": len(method),
                     "first_pass_days": None if first_pass is None else round(first_pass, 2),
                     "first_ready_days": None if first_ready is None else round(first_ready, 2),
                     "ready_during_flood": bool(ss) and min(s["insert"] for s in ss) <= end,
                     "latency_days": [round((s["insert"] - s["begin"]) / DAY_MS, 2) for s in ss]})
        print(f"{e['country']:<28} {len(ss):>3} passes ({len(method)} of the method's kind), first after {first_pass if first_pass is None else round(first_pass, 1)} d, "
              f"ready after {first_ready if first_ready is None else round(first_ready, 1)} d", flush=True)
        time.sleep(0.3)

    lat = np.array([x for r in rows for x in r["latency_days"]])
    covered = [r for r in rows if r["passes"]]
    summary = {
        "floods": len(rows), "covered": len(covered), "covered_by_method_kind": sum(1 for r in rows if r["method_passes"]),
        "ready_during_flood": sum(1 for r in rows if r["ready_during_flood"]),
        "scenes": int(lat.size),
        "latency_days": {"median": round(float(np.median(lat)), 1), "p25": round(float(np.percentile(lat, 25)), 1), "p75": round(float(np.percentile(lat, 75)), 1),
                         "min": round(float(lat.min()), 1), "max": round(float(lat.max()), 1), "share_over_7": round(float((lat > 7).mean()), 3)} if lat.size else None,
        "first_pass_days_median": round(float(np.median([r["first_pass_days"] for r in covered])), 1) if covered else None,
        "first_ready_days_median": round(float(np.median([r["first_ready_days"] for r in covered])), 1) if covered else None,
        "checked_utc": iso(now), "gdacs_window_days": saved.get("days"),
    }
    # ---------- checks ----------
    assert all(r["first_ready_days"] >= r["first_pass_days"] for r in covered), "a scene entered the catalog before it was recorded"
    assert all(x >= 0 for x in lat), "negative latency"
    assert summary["covered_by_method_kind"] <= summary["covered"] <= summary["floods"]
    OUT.write_text(json.dumps({"summary": summary, "floods": rows}, separators=(",", ":")))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
