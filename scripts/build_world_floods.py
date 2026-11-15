"""A saved copy of the dashboard's worldwide flood list, used only when the live GDACS feed doesn't answer.

    python scripts/build_world_floods.py

Reads the same sources as app/worldfloods.js: floods reported in the last 60 days from GDACS, the UN and EU disaster alert
system, and the number of NISAR GCOV scenes covering each reported point during the flood from NASA's CMR catalog. It needs no
login. The output changes with the date it's run, so it isn't part of build_app.py; rerun it before a demo.
"""

import json
import time
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta

from build_app import DATA

from hidden_floods.stamps import stamp

GDACS = "https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH"
CMR = "https://cmr.earthdata.nasa.gov/search/granules.umm_json"
DAYS = 60                        # the same window as app/worldfloods.js; scenes must cover the reported point
OUT = DATA / "dashboard" / "world_floods.json"


def get(url):
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "hidden-floods-build"}), timeout=60) as r:
                return r.status, r.read()
        except Exception:
            if attempt == 2:
                raise
            time.sleep(5)


def ms(text):
    return int(datetime.fromisoformat(text.replace("Z", "")).replace(tzinfo=UTC).timestamp() * 1000)


def events(now):
    start = (now - timedelta(days=DAYS)).date().isoformat()
    out = {}
    for page in range(1, 6):
        status, body = get(f"{GDACS}?eventlist=FL&fromdate={start}&todate={now.date().isoformat()}&alertlevel=green;orange;red&pagesize=100&pagenumber={page}")
        if status in (204, 404) or not body:
            break
        features = json.loads(body).get("features", [])
        for f in features:
            p, g = f["properties"], f.get("geometry") or {}
            lon, lat = g["coordinates"] if g.get("type") == "Point" else ((f["bbox"][0] + f["bbox"][2]) / 2, (f["bbox"][1] + f["bbox"][3]) / 2)
            e = {"id": str(p["eventid"]), "name": p.get("name") or f"Flood in {p['country']}", "country": p["country"], "alert": p["alertlevel"],
                 "current": str(p.get("iscurrent")) == "true", "from": ms(p["fromdate"]), "to": ms(p["todate"]), "lat": lat, "lon": lon,
                 "report": (p.get("url") or {}).get("report")}
            if e["id"] not in out or e["to"] > out[e["id"]]["to"]:
                out[e["id"]] = e
        if len(features) < 100:
            break
    return list(out.values())


def quick_of(umm):
    """The latest scene's ready-made LATLON picture and corner points, as app/worldfloods.js reads them."""
    link = next((u["URL"] for u in umm.get("RelatedUrls", []) if u.get("Type") == "GET RELATED VISUALIZATION" and u["URL"].startswith("https:") and u["URL"].endswith("_LATLON.png")), None)
    poly = (((umm.get("SpatialExtent") or {}).get("HorizontalSpatialDomain") or {}).get("Geometry") or {}).get("GPolygons", [{}])[0].get("Boundary", {}).get("Points", [])
    if not link or len(poly) < 4:
        return None
    return {"url": link, "corners": [[q["Longitude"], q["Latitude"]] for q in poly[:4]], "time": ms(umm["TemporalExtent"]["RangeDateTime"]["BeginningDateTime"])}


SPLIT = "2026-10-21T17:07:00Z"   # first scene in NASA's newer NISAR collection; see app/worldfloods.js
OLD, NEW = "NISAR_L2_GCOV_PROVISIONAL_V1", "NISAR_L2_GCOV_V1"


def scenes(short, e, start, end):
    iso = lambda t: datetime.fromtimestamp(t / 1000, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    q = urllib.parse.urlencode({"short_name": short, "point": f"{e['lon']:.4f},{e['lat']:.4f}", "temporal": f"{iso(start)},{iso(end)}",
                                "sort_key": "-start_date", "page_size": "1"})
    j = json.loads(get(f"{CMR}?{q}")[1])
    return j["hits"], (j["items"][0]["umm"] if j["items"] else None)


def nisar(e, now):
    """Passes over the reported point during the flood: the old collection before SPLIT, the new one after, so none count twice."""
    split, end = ms(SPLIT), min(e["to"] + 86_400_000, int(now.timestamp() * 1000))
    parts = []
    if end > split:
        parts.append(scenes(NEW, e, max(e["from"], split), end))
    if e["from"] < split:
        parts.append(scenes(OLD, e, e["from"], min(end, split)))
    newest = next((u for _, u in parts if u), None)
    latest = newest["TemporalExtent"]["RangeDateTime"]["BeginningDateTime"] if newest else None
    return {"count": sum(h for h, _ in parts), "latest": ms(latest) if latest else None, "quick": quick_of(newest) if newest else None}


def main():
    now = datetime.now(UTC)
    rows = events(now)
    for k, e in enumerate(rows):
        e["nisar"] = nisar(e, now)
        if k % 20 == 0:
            print(f"{k + 1}/{len(rows)} {e['country']}: {e['nisar']['count']} NISAR scenes", flush=True)
    OUT.write_text(json.dumps({**stamp("saved"), "days": DAYS, "events": rows}, ensure_ascii=False, separators=(",", ":")), encoding="utf8")
    seen = sum(1 for e in rows if e["nisar"]["count"])
    print(f"{len(rows)} floods, {seen} with NISAR passes during the flood -> {OUT}")


if __name__ == "__main__":
    main()
