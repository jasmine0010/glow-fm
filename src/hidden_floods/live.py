"""Live cases: the frozen method v4 run on floods happening now, under research/LIVE_PROTOCOL.md.

A live case is a 24 km box around a flood that is being reported now:
- **US:** a NOAA river gauge at minor, moderate or major flood stage. The box gets 3DEP lidar heights, USGS river lines
  and gauges, so the method runs as on the tested rivers and the result is scored against the gauge-and-lidar estimate.
- **Elsewhere:** a GDACS flood. There is no lidar or gauge, so heights come from the Copernicus GLO-30 surface model and
  the map is published unscored, labelled as not checked against ground truth.

For each case the job reads only the box from the NISAR scenes (with the user's Earthdata sign-in, through
``stack.read_scene``), runs the frozen v4 rule once, and writes a small pack the browser can rerun with other settings.
Nothing here ever handles the sign-in itself.
"""

from __future__ import annotations

import http.client
import json
import math
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import h5py
import numpy as np
from scipy.ndimage import binary_dilation, distance_transform_edt

from hidden_floods.audit import GAUGE_SUPPORT_M, gauge_supported
from hidden_floods.config import REPO_ROOT, data_root
from hidden_floods.fetch import CMR, USGS_OGC, get_json
from hidden_floods.grid import Grid, grid_from_lonlat_bbox, warp_to_grid
from hidden_floods.io.dem import dem_on_grid, fetch_3dep
from hidden_floods.io.gauges import load_usgs
from hidden_floods.io.nisar import GCOV_GRID
from hidden_floods.metrics import block_bootstrap, block_ids, score
from hidden_floods.selfcal import height_above_river
from hidden_floods.stack import RangeFile, Scene, read_scene, signed_url
from hidden_floods.trust import timing_class, worldcover_class
from hidden_floods.truth import ValleyLine, hydraulic_truth, refine_centerline
from hidden_floods.v4 import V4Rule, median_baseline

OUT = REPO_ROOT / "app" / "data" / "live"
WORK = data_root() / "live"
RECEIPT = REPO_ROOT / "research" / "freeze_receipt_live.json"
ATTEMPTS = REPO_ROOT / "research" / "live_attempts.log"

# Fixed in research/LIVE_PROTOCOL.md.
HALF_BOX_KM = 12.0
RES_M = 50.0
BASELINE_DAYS = 60
MIN_BASELINE = 3
MAX_BASELINE = 6
COLLECTIONS = (("NISAR_L2_GCOV_V1", "2026-10-21T17:07:00Z", None), ("NISAR_L2_GCOV_PROVISIONAL_V1", None, "2026-10-21T17:07:00Z"))
NWPS = "https://api.water.noaa.gov/nwps/v1/gauges"
NLDI = "https://api.water.usgs.gov/nldi/linked-data/nwissite"
NWIS_SITE = "https://waterservices.usgs.gov/nwis/site/"
WORLDCOVER = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_{tile}_Map.tif"
GLO30 = "https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_{n}_00_{e}_00_DEM/Copernicus_DSM_COG_10_{n}_00_{e}_00_DEM.tif"
CORRIDOR_M, MARGIN_M, MAX_DRY_HEIGHT_M = 4000.0, 0.5, 5.0   # the tested rivers' truth settings
SINGLE_GAUGE_SUPPORT_M = 3000.0
TIDAL = re.compile(r"MLLW|\btide\b", re.IGNORECASE)
LAKE = re.compile(r"^[^,]*\bLake (near|at)\b")   # "Devils Lake near ...", not "River above Lake Harney"
FT = 0.3048
NAME = re.compile(r"GCOV_(\d+)_(\d+)_([AD])_(\d+)_(\d+)_([A-Z]+)_[AM]_(\d{8}T\d{6})_\d{8}T\d{6}_(P\d+)_._(.)_J_(\d+)$")


def _get(url: str, timeout: int = 120, tries: int = 3) -> bytes:
    """A public source, with two more tries when it's slow or busy (5xx or a timeout). A 404 is final."""
    req = urllib.request.Request(url, headers={"User-Agent": "hidden-floods-live"})
    for attempt in range(1, tries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code < 500 or attempt == tries:
                raise
        except (TimeoutError, ConnectionError, http.client.HTTPException, urllib.error.URLError):
            if attempt == tries:
                raise
        time.sleep(10 * attempt)
    raise RuntimeError("unreachable")


def _iso(t: datetime) -> str:
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_time(text: str) -> datetime:
    return datetime.fromisoformat(text).astimezone(UTC)


# ---------- NISAR scenes ----------
@dataclass(frozen=True)
class LiveScene:
    scene: Scene
    time: datetime
    stack_key: str        # track, direction, frame and mode: scenes that can be compared pixel for pixel
    granule: dict


def scenes_over(lon: float, lat: float, start: datetime, end: datetime) -> list[LiveScene]:
    """Dual-pol (HH+HV) GCOV scenes covering the point, from the collection that holds each date, one per date."""
    best: dict[tuple[str, str], tuple[str, LiveScene]] = {}
    for short, after, before in COLLECTIONS:
        lo = max(start, _parse_time(after)) if after else start
        hi = min(end, _parse_time(before)) if before else end
        if lo >= hi:
            continue
        q = urllib.parse.urlencode({"short_name": short, "point": f"{lon:.5f},{lat:.5f}", "temporal": f"{_iso(lo)},{_iso(hi)}",
                                    "page_size": 200, "sort_key": "start_date"})
        for it in get_json(f"{CMR}?{q}").get("items", []):
            u = it["umm"]
            m = NAME.search(u["GranuleUR"])
            if not m or m[6] != "DHDH" or m[5] != "4005":   # 40 MHz HH+HV, the kind the tested rivers used
                continue
            url = next((r["URL"] for r in u.get("RelatedUrls", []) if r.get("Type") == "GET DATA" and r["URL"].startswith("https") and r["URL"].endswith(".h5")), None)
            if not url:
                continue
            t = _parse_time(u["TemporalExtent"]["RangeDateTime"]["BeginningDateTime"])
            key = f"{m[2]}{m[3]}_{m[4]}_{m[5]}_{m[6]}"
            rank = f"{m[8]}_{m[10]}"
            slot = (key, t.strftime("%Y%m%dT%H%M"))
            if slot not in best or rank > best[slot][0]:
                best[slot] = (rank, LiveScene(Scene(u["GranuleUR"], m[2] + m[3], m[4], _iso(t), url), t, key, u))
    return sorted((v[1] for v in best.values()), key=lambda s: s.time)


def pick_scenes(lon: float, lat: float, flood_from: datetime, flood_to: datetime) -> dict:
    """The newest pass during the flood, and up to six same-stack passes from the 60 days before it began."""
    during = [s for s in scenes_over(lon, lat, flood_from, flood_to)]
    if not during:
        return {"ok": False, "reason": "No NISAR pass of the kind the method uses (40 MHz, HH and HV) over this point during the flood is in NASA's catalog yet."}
    wet = during[-1]
    before = [s for s in scenes_over(lon, lat, flood_from - timedelta(days=BASELINE_DAYS), flood_from) if s.stack_key == wet.stack_key]
    base = before[-MAX_BASELINE:]
    if len(base) < MIN_BASELINE:
        return {"ok": False, "reason": f"Only {len(base)} earlier pass{'' if len(base) == 1 else 'es'} on the same track before the flood; the method needs {MIN_BASELINE}.",
                "wet": wet}
    return {"ok": True, "wet": wet, "baseline": base, "passes_during": len(during)}


# ---------- where the floods are ----------
def us_candidates() -> list[dict]:
    """NOAA gauges at minor, moderate or major flood stage now, with their USGS site."""
    gauges = json.loads(_get(NWPS, timeout=180))["gauges"]
    out = []
    for g in gauges:
        obs = (g.get("status") or {}).get("observed") or {}
        if obs.get("floodCategory") not in ("minor", "moderate", "major"):
            continue
        if TIDAL.search(g["name"]) or LAKE.search(g["name"]):   # coastal water levels and lakes, not river floods
            continue
        out.append({"lid": g["lid"], "name": g["name"], "lat": g["latitude"], "lon": g["longitude"], "category": obs["floodCategory"],
                    "state": (g.get("state") or {}).get("abbreviation", "")})
    return out


def us_flood_window(lid: str, now: datetime) -> dict:
    """When the current run above minor flood stage began, from NOAA's 30-day record."""
    detail = json.loads(_get(f"{NWPS}/{lid}"))
    minor = ((detail.get("flood") or {}).get("categories") or {}).get("minor", {}).get("stage")
    rows = json.loads(_get(f"{NWPS}/{lid}/stageflow/observed")).get("data", [])
    rows = [(_parse_time(r["validTime"]), r["primary"]) for r in rows if r.get("primary") not in (None, -999)]
    if minor is None or minor < 0 or not rows:
        return {"usgs": detail.get("usgsId"), "from": None, "minor_ft": minor}
    start = None
    for t, v in reversed(rows):
        if v >= minor:
            start = t
        elif start is not None:
            break
    return {"usgs": detail.get("usgsId"), "from": start, "from_is_record_start": start == rows[0][0], "minor_ft": minor,
            "stage_now_ft": rows[-1][1], "to": now}


def world_candidates(gdacs_events: list[dict]) -> list[dict]:
    """GDACS floods from the saved worldwide list, kept as given (alert, dates and one reported point)."""
    return [{"id": e["id"], "name": e["name"], "country": e["country"], "alert": e["alert"], "lat": e["lat"], "lon": e["lon"],
             "from": datetime.fromtimestamp(e["from"] / 1000, UTC), "to": datetime.fromtimestamp(e["to"] / 1000, UTC), "current": e["current"],
             "report": e.get("report")} for e in gdacs_events]


# ---------- the box and its inputs ----------
def utm_epsg(lon: float, lat: float) -> str:
    zone = int((lon + 180) // 6) + 1
    return f"EPSG:{(32600 if lat >= 0 else 32700) + zone}"


def box_grid(lon: float, lat: float, epsg: str) -> Grid:
    dlat = HALF_BOX_KM / 111.32
    dlon = dlat / max(0.1, math.cos(math.radians(lat)))
    return grid_from_lonlat_bbox((lon - dlon, lat - dlat, lon + dlon, lat + dlat), epsg, RES_M)


def scene_origin(s: LiveScene) -> tuple[str, float, float, float]:
    """The scene's projection, the outer corner of its first pixel and its pixel spacing, from a small read of the file."""
    src = RangeFile(signed_url(s.scene.url, data_root() / "stack" / "cookies.txt"))
    with h5py.File(src, "r") as h:
        g = h[GCOV_GRID]
        sp = float(g["xCoordinateSpacing"][()])
        return f"EPSG:{int(g['projection'][()])}", float(g["xCoordinates"][0]) - sp / 2, float(g["yCoordinates"][0]) + sp / 2, sp


def aligned_grid(lon: float, lat: float, s: LiveScene) -> Grid:
    """The 24 km box on the scene's own UTM zone and pixel edges, so the 10 m pixels average cleanly into 50 m ones."""
    epsg, ex, ey, sp = scene_origin(s)
    g0 = box_grid(lon, lat, epsg)
    if abs(RES_M / sp - round(RES_M / sp)) > 1e-9:
        raise ValueError(f"the scene's {sp} m pixels don't divide the {RES_M} m grid")
    x0 = ex + round((g0.x0 - ex) / sp) * sp
    y0 = ey + round((g0.y0 - ey) / sp) * sp
    return Grid(epsg, x0, y0, g0.res, g0.width, g0.height)


def read_box(case_id: str, grid: Grid, s: LiveScene) -> dict:
    # The cache name carries the grid's corner, so a scene read on another grid is never reused by mistake.
    return read_scene(SimpleNamespace(name=f"live_{case_id}_{grid.crs[5:]}_{grid.x0:.0f}_{grid.y0:.0f}"), grid, s.scene)


def worldcover_box(grid: Grid) -> np.ndarray:
    """WorldCover 2021 codes on the box, read straight from ESA's public tiles."""
    lon, lat = grid.to_lonlat(*np.array([[grid.x0, grid.x0 + grid.width * grid.res], [grid.y0, grid.y0 - grid.height * grid.res]]))
    out = np.zeros(grid.shape, np.uint8)
    for la in range(int(math.floor(min(lat) / 3) * 3), int(math.floor(max(lat) / 3) * 3) + 1, 3):
        for lo in range(int(math.floor(min(lon) / 3) * 3), int(math.floor(max(lon) / 3) * 3) + 1, 3):
            tile = f"{'N' if la >= 0 else 'S'}{abs(la):02d}{'E' if lo >= 0 else 'W'}{abs(lo):03d}"
            try:
                w = warp_to_grid(f"/vsicurl/{WORLDCOVER.format(tile=tile)}", grid, categorical=True, nodata=0, dtype=np.uint8)
            except Exception:  # noqa: BLE001, S112  (public sources fail in many ways; the case moves on)
                continue
            out = np.where(out == 0, w, out)
    return out


def glo30_box(grid: Grid) -> np.ndarray:
    """Copernicus GLO-30 surface heights on the box. It includes trees and buildings, unlike bare-earth lidar."""
    lon, lat = grid.to_lonlat(*np.array([[grid.x0, grid.x0 + grid.width * grid.res], [grid.y0, grid.y0 - grid.height * grid.res]]))
    out = np.full(grid.shape, np.nan, np.float32)
    for la in range(math.floor(min(lat)), math.floor(max(lat)) + 1):
        for lo in range(math.floor(min(lon)), math.floor(max(lon)) + 1):
            n, e = f"{'N' if la >= 0 else 'S'}{abs(la):02d}", f"{'E' if lo >= 0 else 'W'}{abs(lo):03d}"
            try:
                w = warp_to_grid(f"/vsicurl/{GLO30.format(n=n, e=e)}", grid, categorical=False, nodata=np.nan, dtype=np.float32)
            except Exception:  # noqa: BLE001, S112  (public sources fail in many ways; the case moves on)
                continue
            out = np.where(np.isfinite(out), out, w)
    return out


def lidar_box(case_id: str, grid: Grid) -> np.ndarray:
    path = WORK / case_id / "dem3dep.tif"
    if not path.exists():
        fetch_3dep(grid, path)
    return dem_on_grid(path, grid)


def river_line(usgs: str) -> list[tuple[float, float]]:
    """The main stem through the gauge, 20 km up and down, from USGS river lines, upstream to downstream."""
    segs = []
    for nav in ("UM", "DM"):
        g = json.loads(_get(f"{NLDI}/USGS-{usgs}/navigation/{nav}/flowlines?distance=20"))
        for f in g.get("features", []):
            geom = f["geometry"]
            parts = geom["coordinates"] if geom["type"] == "MultiLineString" else [geom["coordinates"]]
            segs += [[tuple(p[:2]) for p in part] for part in parts if len(part) > 1]
    if not segs:
        return []
    key = lambda p: (round(p[0], 5), round(p[1], 5))
    starts = {key(s[0]): s for s in segs}
    ends = {key(s[-1]) for s in segs}
    head = next((s for s in segs if key(s[0]) not in ends), segs[0])
    line, seen = list(head), {id(head)}
    while key(line[-1]) in starts and id(starts[key(line[-1])]) not in seen:
        nxt = starts[key(line[-1])]
        seen.add(id(nxt))
        line += nxt[1:]
    return line


def gauges_on_stem(usgs: str) -> list[str]:
    """USGS sites on the main stem 20 km up and down from the flood gauge, including it."""
    ids = {usgs}
    for nav in ("UM", "DM"):
        try:
            g = json.loads(_get(f"{NLDI}/USGS-{usgs}/navigation/{nav}/nwissite?distance=20"))
        except Exception:  # noqa: BLE001, S112  (public sources fail in many ways; the case moves on)
            continue
        ids |= {f["properties"]["identifier"].removeprefix("USGS-") for f in g.get("features", []) if f["properties"].get("identifier", "").startswith("USGS-")}
    return sorted(ids)


def gauge_datum(usgs: str) -> dict | None:
    text = _get(f"{NWIS_SITE}?format=rdb&sites={usgs}&siteOutput=expanded").decode()
    lines = [ln for ln in text.splitlines() if not ln.startswith("#")]
    if len(lines) < 3:
        return None
    row = dict(zip(lines[0].split("\t"), lines[2].split("\t"), strict=False))
    try:
        alt = float(row.get("alt_va", ""))
    except ValueError:
        alt = None   # some gauges, often tidal ones, publish water elevation instead (see gauge_level)
    return {"usgs": usgs, "name": row.get("station_nm"), "lat": float(row["dec_lat_va"]), "lon": float(row["dec_long_va"]), "datum_ft": alt,
            "datum": row.get("alt_datum_cd")}


def usgs_record(case_id: str, usgs: str, param: str, when: datetime):
    """15-minute USGS readings of one parameter around ``when`` (USGS water-data OGC API, as fetch_usgs_stage)."""
    out = WORK / case_id / "gauges" / f"usgs_{usgs}_{param}.json"
    if not out.exists():
        feats, url = [], (f"{USGS_OGC}/continuous/items?" + urllib.parse.urlencode(
            {"f": "json", "monitoring_location_id": f"USGS-{usgs}", "parameter_code": param,
             "time": f"{_iso(when - timedelta(days=12))}/{_iso(when + timedelta(days=4))}", "limit": 10000}))
        while url:
            page = json.loads(_get(url, timeout=300))
            feats += page.get("features", [])
            url = next((ln["href"] for ln in page.get("links", []) if ln.get("rel") == "next"), None)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"features": feats}))
    return load_usgs(out)


def gauge_level(case_id: str, d: dict, when: datetime) -> dict | None:
    """Water surface (NAVD88 m) and timing at a gauge. Water elevation above NAVD88 (63160) is used directly when the
    gauge publishes it; otherwise stage (00065) plus the gauge datum, with no NGVD29 offset, as on the tested rivers."""
    for param in ("63160", "00065"):
        if param == "00065" and d["datum_ft"] is None:
            return None
        try:
            rec = usgs_record(case_id, d["usgs"], param, when)
            value = rec.at(_iso(when))
        except (ValueError, IndexError, urllib.error.URLError):
            continue
        wse_ft = value if param == "63160" else d["datum_ft"] + value
        return {"level_source": "water elevation above NAVD88" if param == "63160" else f"stage + gauge datum ({d['datum']})",
                "reading_ft": value, "wse_m": wse_ft * FT, "timing": int(timing_class(rec, _iso(when)))}
    return None


# ---------- running one case ----------
@dataclass
class Prepared:
    case_id: str
    kind: str                      # "us" or "world"
    grid: Grid
    wet: dict
    base_median: dict
    base_one: dict
    hand: np.ndarray
    dist: np.ndarray
    landcover: np.ndarray
    timing: np.ndarray
    water: np.ndarray
    truth: dict | None = None
    info: dict = field(default_factory=dict)


def prepare(case: dict, picked: dict, score_it: bool) -> Prepared:
    """Read the box from each scene and build the method's inputs. Truth is built only when ``score_it`` is set."""
    wet_s = picked["wet"]
    grid = aligned_grid(case["lon"], case["lat"], wet_s)
    epsg = grid.crs
    wet = read_box(case["id"], grid, wet_s)
    stack = [read_box(case["id"], grid, s) for s in picked["baseline"]]
    base = {"hh": median_baseline(np.stack([x["hh"] for x in stack])), "hv": median_baseline(np.stack([x["hv"] for x in stack]))}
    lc = worldcover_class(raw_lc := worldcover_box(grid))
    water = raw_lc == 80
    info: dict = {"epsg": epsg}
    truth = None
    if case["kind"] == "us":
        dem = lidar_box(case["id"], grid)
        try:
            coords = river_line(case["usgs"])
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise ValueError(f"USGS river lines didn't answer (HTTP {e.code}).") from e
            coords = []
        if len(coords) < 2:
            raise ValueError("USGS has no river line through this gauge (it may sit on a lake), so heights above the river can't be measured.")
        coarse = ValleyLine.from_lonlat(grid, coords)
        dist0, _ = coarse.project(*grid.meshgrid())
        flowline = binary_dilation(dist0 < RES_M, iterations=1)
        channel = water | flowline
        line = refine_centerline(coarse, channel & (dist0 < CORRIDOR_M), grid)
        dist, chainage = line.project(*grid.meshgrid())
        hand = height_above_river(dem, dist, chainage)
        gauges = []
        for usgs in gauges_on_stem(case["usgs"]):
            d = gauge_datum(usgs)
            if not d:
                continue
            gx, gy = grid.to_xy(d["lon"], d["lat"])
            if not (grid.x0 <= gx <= grid.x0 + grid.width * RES_M and grid.y0 - grid.height * RES_M <= gy <= grid.y0):
                continue
            level = gauge_level(case["id"], d, wet_s.time)
            if level:
                gauges.append(d | level | {"xy": (gx, gy)})
        info["gauges"] = [{k: v for k, v in g.items() if k != "xy"} for g in gauges]
        if gauges:
            _, g_chain = line.project(np.array([g["xy"][0] for g in gauges]), np.array([g["xy"][1] for g in gauges]))
            timing = np.array([g["timing"] for g in gauges], np.uint8)[np.argmin(np.abs(chainage[..., None] - g_chain), axis=-1)]
        else:
            timing = np.zeros(grid.shape, np.uint8)
        if score_it and gauges:
            t = hydraulic_truth(grid, dem, line, [g["xy"] for g in gauges], [g["wse_m"] for g in gauges], CORRIDOR_M, MARGIN_M, MAX_DRY_HEIGHT_M,
                                channel_seeds=channel, max_chainage_m=float(np.max(g_chain)) + (SINGLE_GAUGE_SUPPORT_M if len(gauges) == 1 else 0.0))
            support = SINGLE_GAUGE_SUPPORT_M if len(gauges) == 1 else GAUGE_SUPPORT_M
            supported = gauge_supported(t.chainage_m, tuple(float(c) for c in g_chain), support)
            truth = {"wet": t.wet, "dry": t.dry, "region": supported & ~channel, "chainage": t.chainage_m}
        info["heights"] = "3DEP lidar (bare earth)"
        info["river"] = "USGS river line through the gauge"
    else:
        dem = glo30_box(grid)
        # No river line: height and distance are measured to the nearest mapped water.
        if water.any():
            dist_px, (iy, ix) = distance_transform_edt(~water, return_indices=True)
            dist = (dist_px * RES_M).astype(np.float32)
            hand = (dem - dem[iy, ix]).astype(np.float32)
        else:
            dist = np.full(grid.shape, np.inf, np.float32)
            hand = np.full(grid.shape, np.nan, np.float32)
        timing = np.zeros(grid.shape, np.uint8)
        info["heights"] = "Copernicus GLO-30 surface model (includes trees)"
        info["river"] = "nearest water in ESA WorldCover"
    perm = channel if case["kind"] == "us" else water
    return Prepared(case["id"], case["kind"], grid, wet, base, stack[-1], hand.astype(np.float32), dist.astype(np.float32), lc, timing, perm, truth, info)


def run_rule(p: Prepared, rule: V4Rule) -> dict:
    return rule.apply(p.wet["hh"] - p.base_median["hh"], p.wet["hv"] - p.base_median["hv"], p.landcover, p.timing, p.hand, p.dist)


def score_case(p: Prepared, res: dict, block_m: float, n_boot: int, seed: int) -> dict:
    t = p.truth
    scored = t["region"] & res["mapped"]
    s = score(res["pred"], t["wet"], t["dry"], scored)
    judged = s.tp + s.fn + s.fp > 0
    ci = block_bootstrap(res["pred"], t["wet"], t["dry"], block_ids(t["chainage"], block_m), scored, n_boot=n_boot, seed=seed) if judged else None
    area = p.grid.pixel_area_ha
    return {"scores": s.to_dict(area), "ci95": ci, "estimate_wet_ha": float((t["wet"] & scored).sum() * area),
            "estimate_dry_ha": float((t["dry"] & scored).sum() * area)}


# ---------- what the browser gets ----------
def corners_lonlat(grid: Grid) -> list[list[float]]:
    xs = [grid.x0, grid.x0 + grid.width * grid.res]
    ys = [grid.y0, grid.y0 - grid.height * grid.res]
    lon, lat = grid.to_lonlat(np.array([xs[0], xs[1], xs[1], xs[0]]), np.array([ys[0], ys[0], ys[1], ys[1]]))
    return [[round(float(a), 6), round(float(b), 6)] for a, b in zip(lon, lat, strict=True)]


def _db16(a: np.ndarray) -> np.ndarray:
    out = np.where(np.isfinite(a), np.clip(np.round(a * 100), -32767, 32767), -32768)
    return out.astype("<i2")


def write_pack(p: Prepared, folder: Path) -> dict:
    """Arrays in one little-endian file, in the order the browser reads them. dB and metres are stored in hundredths."""
    folder.mkdir(parents=True, exist_ok=True)
    h, w = p.grid.shape
    parts = [("wet_hh", _db16(p.wet["hh"])), ("wet_hv", _db16(p.wet["hv"])), ("median_hh", _db16(p.base_median["hh"])), ("median_hv", _db16(p.base_median["hv"])),
             ("one_hh", _db16(p.base_one["hh"])), ("one_hv", _db16(p.base_one["hv"])), ("hand", _db16(p.hand)),
             ("dist", np.where(np.isfinite(p.dist), np.clip(np.round(p.dist / 10), 0, 65535), 65535).astype("<u2")),
             ("landcover", p.landcover.astype(np.uint8)), ("timing", p.timing.astype(np.uint8)), ("water", p.water.astype(np.uint8))]
    if p.truth is not None:
        lab = np.zeros((h, w), np.uint8)
        lab[p.truth["dry"] & p.truth["region"]] = 2
        lab[p.truth["wet"] & p.truth["region"]] = 1
        parts.append(("estimate", lab))
    with open(folder / "pack.bin", "wb") as f:
        f.writelines(a.tobytes() for _, a in parts)
    return {"width": w, "height": h, "arrays": [{"name": n, "type": str(a.dtype).lstrip("<|")} for n, a in parts]}


def decode_pack(folder: Path, layout: dict) -> dict[str, np.ndarray]:
    """What the browser sees, decoded the same way, for checking the browser's run against Python's."""
    raw, off, out = (folder / "pack.bin").read_bytes(), 0, {}
    n = layout["width"] * layout["height"]
    for a in layout["arrays"]:
        dt = {"int16": "<i2", "uint16": "<u2", "uint8": "u1"}[a["type"]]
        v = np.frombuffer(raw, dt, n, off).reshape(layout["height"], layout["width"])
        off += n * np.dtype(dt).itemsize
        if a["type"] == "int16":
            v = np.where(v == -32768, np.nan, v / 100.0).astype(np.float32)
        elif a["name"] == "dist":
            v = np.where(v == 65535, np.inf, v * 10.0).astype(np.float32)
        out[a["name"]] = v
    return out
