"""Run it anywhere: the site plus a local box server, so the Run it yourself page can take any place and any NISAR pass.

    python scripts/custom_server.py            # http://127.0.0.1:8767
    python scripts/custom_server.py 9000       # another port

The browser can search NASA's catalog and run the method itself, but it can't read NISAR's data files: NASA's data
server refuses cross-site reads, and every file sits behind an Earthdata sign-in. This server does that one step. It
reads only the box you drew (5 to 50 km a side, inside one NISAR scene) from the chosen pass and the passes before it, with the sign-in this computer already uses
(~/.netrc, through the same code as the live cases), and returns the same small pack the live cases publish. The
browser then runs the method as it does on every live case.

Local only: it listens on 127.0.0.1, publishes nothing, and writes its packs to outputs/custom (not in app/data).
Custom runs use the global inputs everywhere (FABDEM bare-earth heights, the nearest mapped water, ESA WorldCover),
have no gauges and so no score, and are uses of the frozen method, not tests of it.
"""

import json
import math
import re
import sys
import threading
import time
import traceback
import urllib.parse
from datetime import UTC, datetime, timedelta
from functools import partial
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from live_cases import quicklook
from serve_app import APP, NoCache, Server

from hidden_floods import live, live_v2
from hidden_floods.config import REPO_ROOT
from hidden_floods.fetch import CMR, get_json
from hidden_floods.grid import Grid, grid_from_lonlat_bbox
from hidden_floods.stack import Scene
from hidden_floods.trust import worldcover_class
from hidden_floods.v4 import median_baseline

OUT = REPO_ROOT / "outputs" / "custom"
JOBS: dict[str, dict] = {}
LISTED: dict[str, dict] = {}       # passes the server has listed, by scene name: only these can be run
LOCK = threading.Lock()            # one box at a time: the reads are the slow part, and they share a cache
SAFE_ID = re.compile(r"^[a-z0-9_.-]+$")
BOX_KM = (5.0, 50.0)               # a box's sides: big enough to have a valley floor, small enough to read in minutes
READER_META = '  <meta name="glowfm-reader" content="local">' + chr(10)


def iso(t: datetime) -> str:
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def box_km(box) -> tuple[float, float]:
    w, so, e, n = box
    return (e - w) * 111.32 * math.cos(math.radians((so + n) / 2)), (n - so) * 111.32


def inside(poly, lon, lat) -> bool:
    c = False
    for i in range(len(poly)):
        (x1, y1), (x2, y2) = poly[i], poly[i - 1]
        if (y1 > lat) != (y2 > lat) and lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1:
            c = not c
    return c


def scenes_in_box(box, start: datetime, end: datetime) -> list:
    """The method's kind of pass (40 MHz, HH and HV) whose scene covers the whole box: live.scenes_over, for a box."""
    w, so, e, n = box
    best = {}
    for short, after, before in live.COLLECTIONS:
        lo = max(start, live._parse_time(after)) if after else start
        hi = min(end, live._parse_time(before)) if before else end
        if lo >= hi:
            continue
        q = urllib.parse.urlencode({"short_name": short, "bounding_box": f"{w:.5f},{so:.5f},{e:.5f},{n:.5f}", "temporal": f"{iso(lo)},{iso(hi)}", "page_size": 200, "sort_key": "start_date"})
        for it in get_json(f"{CMR}?{q}").get("items", []):
            u = it["umm"]
            m = live.NAME.search(u["GranuleUR"])
            if not m or m[6] != "DHDH" or m[5] != "4005":
                continue
            pts = u["SpatialExtent"]["HorizontalSpatialDomain"]["Geometry"]["GPolygons"][0]["Boundary"]["Points"]
            poly = [(p["Longitude"], p["Latitude"]) for p in pts]
            if not all(inside(poly, x, y) for x, y in ((w, so), (w, n), (e, so), (e, n))):
                continue                                       # the box must sit inside one scene
            url = next((r["URL"] for r in u.get("RelatedUrls", []) if r.get("Type") == "GET DATA" and r["URL"].startswith("https") and r["URL"].endswith(".h5")), None)
            if not url:
                continue
            t = live._parse_time(u["TemporalExtent"]["RangeDateTime"]["BeginningDateTime"])
            key, rank = f"{m[2]}{m[3]}_{m[4]}_{m[5]}_{m[6]}", f"{m[8]}_{m[10]}"
            slot = (key, t.strftime("%Y%m%dT%H%M"))
            if slot not in best or rank > best[slot][0]:
                best[slot] = (rank, live.LiveScene(Scene(u["GranuleUR"], m[2] + m[3], m[4], live._iso(t), url), t, key, u))
    return sorted((v[1] for v in best.values()), key=lambda x: x.time)


def passes(box, start: datetime, end: datetime) -> list[dict]:
    """Passes covering the box, newest first, each with its earlier passes on the same track and frame."""
    found = scenes_in_box(box, start - timedelta(days=live.BASELINE_DAYS), end)
    out = []
    for s in found:
        if s.time < start:
            continue
        before = [b for b in found if b.stack_key == s.stack_key and s.time - timedelta(days=live.BASELINE_DAYS) <= b.time < s.time - timedelta(hours=1)]
        LISTED[s.scene.name] = {"scene": s, "baseline": before[-live.MAX_BASELINE:], "box": box}
        out.append({"name": s.scene.name, "time": iso(s.time), "stack": s.stack_key, "earlier": len(before[-live.MAX_BASELINE:]),
                    "usable": len(before) >= live.MIN_BASELINE, "quicklook": quicklook(s.granule)})
    return sorted(out, key=lambda p: p["time"], reverse=True)


def prepare_box(case_id: str, picked: dict, box) -> live.Prepared:
    """live_v2.prepare's inputs for a world box, on the box you drew instead of a fixed 24 km one (that module is hashed
    in the v2 freeze, so it isn't edited). The grid is lined up with the scene's own pixel edges, as for every live case."""
    wet_s = picked["wet"]
    epsg, ex, ey, sp = live.scene_origin(wet_s)
    g0 = grid_from_lonlat_bbox(box, epsg, live.RES_M)
    grid = Grid(epsg, ex + round((g0.x0 - ex) / sp) * sp, ey + round((g0.y0 - ey) / sp) * sp, g0.res, g0.width, g0.height)
    wet = live.read_box(case_id, grid, wet_s)
    stack = [live.read_box(case_id, grid, s) for s in picked["baseline"]]
    base = {"hh": median_baseline(np.stack([x["hh"] for x in stack])), "hv": median_baseline(np.stack([x["hv"] for x in stack]))}
    lc = worldcover_class(raw_lc := live.worldcover_box(grid))
    water = raw_lc == 80
    tiles = [t for la, lo in live_v2.tiles_for(grid) if (t := live_v2.fetch_tile(la, lo))]
    hand, dist = live_v2.heights_to_water(live_v2.fabdem_box(grid, tiles), water)
    info = {"epsg": grid.crs, "heights": live_v2.HEIGHTS, "river": "nearest water in ESA WorldCover", "protocol": live_v2.PROTOCOL, "fabdem_tiles": tiles,
            "licence": live_v2.LICENCE, "box_km": [round(x, 1) for x in box_km(box)]}
    return live.Prepared(case_id, "world", grid, wet, base, stack[-1], hand, dist, lc, np.zeros(grid.shape, np.uint8), water, None, info)


def run_job(job: dict) -> None:
    listed = LISTED[job["pass"]]
    wet, base = listed["scene"], listed["baseline"]
    job_id = job["id"]
    box = listed["box"]
    total = 1 + len(base)
    original = live.read_box
    def counted(case_id, grid, s):           # report each scene as it is read
        job["step"] = f"Reading NISAR pass {job['read'] + 1} of {total} ({s.time:%b %d})"
        out = original(case_id, grid, s)
        job["read"] += 1
        if job["read"] == total:
            job["step"] = "Reading land cover and bare-earth heights (FABDEM; a new region's tiles take a few minutes the first time)"
        return out
    with LOCK:
        job["state"], job["step"], job["read"] = "running", "Lining up the box with the pass", 0
        live.read_box = counted
        try:
            p = prepare_box(job_id, {"wet": wet, "baseline": base}, box)
        finally:
            live.read_box = original
    job["step"] = "Writing the pack"
    folder = OUT / job_id
    layout = live.write_pack(p, folder)
    rec = {"id": job_id, "kind": "world", "custom": True, "name": "Your place", "place": job["place"], "lat": (box[1] + box[3]) / 2, "lon": (box[0] + box[2]) / 2, "box": box,
           "wet": {"time": iso(wet.time), "name": wet.scene.name, "stack": wet.stack_key, "quicklook": quicklook(wet.granule)},
           "baseline": [{"time": iso(s.time), "name": s.scene.name} for s in base], "corners": live.corners_lonlat(p.grid),
           "pixel_ha": p.grid.pixel_area_ha, "layout": layout, "inputs": {k: v for k, v in p.info.items() if k != "fabdem_tiles"},
           "fabdem_tiles": p.info.get("fabdem_tiles"), "made_utc": iso(datetime.now(UTC))}
    (folder / "case.json").write_text(json.dumps(rec, default=lambda o: o.item() if isinstance(o, np.generic) else str(o)))
    job["state"], job["step"] = "done", "Ready"


def start_job(name: str, place: str) -> dict:
    listed = LISTED[name]
    w, so, e, n = listed["box"]
    job_id = f"custom_{w:.3f}_{so:.3f}_{e:.3f}_{n:.3f}_{listed['scene'].time:%Y%m%d%H%M}".replace("-", "m")
    if job_id in JOBS and JOBS[job_id]["state"] in ("queued", "running", "done"):
        return JOBS[job_id]
    job = {"id": job_id, "pass": name, "place": place[:80] or "Your place", "state": "queued", "step": "Waiting for the box reader", "read": 0, "started": time.time()}
    JOBS[job_id] = job
    def work():
        try:
            run_job(job)
        except Exception as e:  # noqa: BLE001  (reported to the page as it is)
            job["state"], job["step"] = "failed", f"{type(e).__name__}: {e}"
            traceback.print_exc()
    threading.Thread(target=work, daemon=True).start()
    return job


class Handler(NoCache):
    def send_json(self, obj, status=200):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        q = {k: v[0] for k, v in urllib.parse.parse_qs(url.query).items()}
        try:
            if url.path == "/api/health":
                return self.send_json({"ok": True, "local": True})
            if url.path == "/api/passes":
                box = [float(q[k]) for k in ("w", "s", "e", "n")]
                if not (-180 <= box[0] < box[2] <= 180 and -80 <= box[1] < box[3] <= 80):
                    return self.send_json({"error": "That box is outside NISAR's coverage."}, 400)
                kx, ky = box_km(box)
                if not (BOX_KM[0] <= min(kx, ky) and max(kx, ky) <= BOX_KM[1]):
                    return self.send_json({"error": f"Draw a box between {BOX_KM[0]:.0f} and {BOX_KM[1]:.0f} km a side (this one is {kx:.0f} × {ky:.0f} km)."}, 400)
                end = datetime.fromisoformat(q["to"]).replace(tzinfo=UTC) if q.get("to") else datetime.now(UTC)
                start = datetime.fromisoformat(q["from"]).replace(tzinfo=UTC) if q.get("from") else end - timedelta(days=30)
                if not timedelta(0) < end - start <= timedelta(days=120):
                    return self.send_json({"error": "Choose a window of up to 120 days."}, 400)
                return self.send_json({"passes": passes(box, start, end), "box_km": [round(kx, 1), round(ky, 1)]})
            m = re.match(r"^/api/job/([^/]+)$", url.path)
            if m and m[1] in JOBS:
                j = JOBS[m[1]]
                return self.send_json({k: j[k] for k in ("id", "state", "step", "read")} | {"seconds": round(time.time() - j["started"])})
            m = re.match(r"^/api/custom/([^/]+)/(case\.json|pack\.bin)$", url.path)
            if m and SAFE_ID.match(m[1]) and (OUT / m[1] / m[2]).exists():
                data = (OUT / m[1] / m[2]).read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "application/json" if m[2].endswith(".json") else "application/octet-stream")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return None
            if url.path.startswith("/api/"):
                return self.send_json({"error": "Not found."}, 404)
            if url.path == "/live.html":
                # Mark the page so it offers "choose any place"; a plain static copy of the site never asks for the reader.
                page = (APP / "live.html").read_text(encoding="utf8").replace("</head>", READER_META + "</head>", 1).encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(page)))
                self.end_headers()
                self.wfile.write(page)
                return None
        except (KeyError, ValueError) as e:
            return self.send_json({"error": f"Bad request: {e}"}, 400)
        return super().do_GET()

    def do_POST(self):
        url = urllib.parse.urlparse(self.path)
        if url.path != "/api/run":
            return self.send_json({"error": "Not found."}, 404)
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            name = str(body["pass"])
            if name not in LISTED:
                return self.send_json({"error": "List the passes for this place first."}, 400)
            if len(LISTED[name]["baseline"]) < live.MIN_BASELINE:
                return self.send_json({"error": "This pass has too few earlier passes on its track for the method."}, 400)
            job = start_job(name, str(body.get("place", "")))
            return self.send_json({"id": job["id"], "state": job["state"]})
        except (KeyError, ValueError) as e:
            return self.send_json({"error": f"Bad request: {e}"}, 400)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8767
    OUT.mkdir(parents=True, exist_ok=True)
    server = Server(("127.0.0.1", port), partial(Handler, directory=str(APP)))
    print(f"Serving {APP} and the local box reader at http://127.0.0.1:{port}")
    server.serve_forever()
