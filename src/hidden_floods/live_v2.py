"""Live cases, protocol v2 (research/LIVE_PROTOCOL_V2.md): v1 with one input changed.

Where there is no lidar, ground height now comes from FABDEM V1-2, a global elevation model with trees and buildings
removed, instead of Copernicus GLO-30, which measures the treetops. The frozen bare-earth test chose this
(research/BARE_EARTH_RESULTS.md): on seven US passes it raised the method's mean CSI from 0.25 to 0.35, against 0.38
with lidar. Everything else is v1 unchanged, so this module reuses ``hidden_floods.live`` (hashed in the v1 receipt and
never edited) and replaces only the height source of non-US cases.

It offers the same names ``scripts/live_cases.py`` uses, so ``scripts/live_cases_v2.py`` runs the v1 job with this
module in place of ``live``. ``rerun_world`` rebuilds a published v1 world case under v2 from the arrays v1 published,
swapping only the height layer, so nothing but the height source can differ.

FABDEM: Hawker et al. (2022), Environ. Res. Lett. 17, 024016; https://doi.org/10.5523/bris.s5hqmjcdj8yo2ibzi9b4ew3sn.
CC BY-NC-SA 4.0. Layers made from it (the height layer in a v2 world pack) are shared under the same licence, for
non-commercial use. FABDEM is produced using Copernicus WorldDEM-30 (c) DLR e.V. 2010-2014 and (c) Airbus Defence and
Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import urllib.request
import zipfile
import zlib
from pathlib import Path

import numpy as np
from pyproj import Transformer
from scipy.ndimage import distance_transform_edt

from hidden_floods import live
from hidden_floods.config import REPO_ROOT, data_root
from hidden_floods.grid import Grid, warp_to_grid
from hidden_floods.live import (  # noqa: F401  (the names scripts/live_cases.py uses, unchanged from v1)
    OUT,
    RES_M,
    _iso,
    corners_lonlat,
    decode_pack,
    pick_scenes,
    run_rule,
    score_case,
    us_candidates,
    us_flood_window,
    world_candidates,
    write_pack,
)
from hidden_floods.trust import worldcover_class
from hidden_floods.v4 import median_baseline

PROTOCOL = "research/LIVE_PROTOCOL_V2.md"
RECEIPT = REPO_ROOT / "research" / "freeze_receipt_live_v2.json"
ATTEMPTS = REPO_ROOT / "research" / "live_v2_attempts.log"
FABDEM_DIR = data_root() / "fabdem"
FABDEM_BASE = "https://data.bris.ac.uk/datasets/s5hqmjcdj8yo2ibzi9b4ew3sn"
FABDEM_VERSION = "V1-2"
HEIGHTS = "FABDEM V1-2 bare-earth model (trees and buildings removed)"
LICENCE = ("Height layer made from FABDEM V1-2 (Hawker et al. 2022), CC BY-NC-SA 4.0, for non-commercial use. FABDEM is produced using "
           "Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the "
           "European Union and ESA; all rights reserved.")
SUFFIX = "_v2"


# ---------- FABDEM tiles, read by byte ranges from the 10x10 degree archives ----------
class _Remote(io.RawIOBase):
    """A seekable view of a remote file over HTTP range requests (the archives are about 2 GB; only a few MB are read)."""

    def __init__(self, url: str):
        self.url, self.pos = url, 0
        with urllib.request.urlopen(urllib.request.Request(url, method="HEAD", headers={"User-Agent": "research-client"}), timeout=120) as r:
            if r.headers.get("Accept-Ranges") != "bytes":
                raise RuntimeError(f"{url} doesn't accept byte ranges")
            self.size = int(r.headers["Content-Length"])

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=io.SEEK_SET):
        self.pos = {io.SEEK_SET: 0, io.SEEK_CUR: self.pos, io.SEEK_END: self.size}[whence] + offset
        return self.pos

    def readinto(self, b):
        if self.pos >= self.size or not len(b):
            return 0
        end = min(self.size, self.pos + len(b)) - 1
        req = urllib.request.Request(self.url, headers={"User-Agent": "research-client", "Range": f"bytes={self.pos}-{end}"})
        with urllib.request.urlopen(req, timeout=600) as r:
            data = r.read()
        b[: len(data)] = data
        self.pos += len(data)
        return len(data)


def _name(lat: int, lon: int) -> str:
    return f"{'N' if lat >= 0 else 'S'}{abs(lat):02d}{'E' if lon >= 0 else 'W'}{abs(lon):03d}"


def archive_for(lat: int, lon: int) -> str:
    """The 10x10 degree archive holding a 1x1 degree tile, named by its south-west and north-east corners."""
    la, lo = 10 * math.floor(lat / 10), 10 * math.floor(lon / 10)
    return f"{_name(la, lo)}-{_name(la + 10, lo + 10)}_FABDEM_{FABDEM_VERSION}.zip"


def tiles_for(grid: Grid) -> list[tuple[int, int]]:
    lon, lat = grid.to_lonlat(*np.array([[grid.x0, grid.x0 + grid.width * grid.res], [grid.y0, grid.y0 - grid.height * grid.res]]))
    return [(la, lo) for la in range(math.floor(min(lat)), math.floor(max(lat)) + 1) for lo in range(math.floor(min(lon)), math.floor(max(lon)) + 1)]


def fetch_tile(lat: int, lon: int) -> dict | None:
    """One FABDEM tile, kept in the local data folder. A tile already there is reused only if its size and CRC-32 match the
    archive directory. Returns its record (hash, size, CRC-32, archive), or None where the archive has no tile (open sea)."""
    tile, arc = _name(lat, lon), archive_for(lat, lon)
    zf = zipfile.ZipFile(io.BufferedReader(_Remote(f"{FABDEM_BASE}/{arc}"), buffer_size=1 << 20))
    member = next((m for m in zf.infolist() if m.filename.endswith(f"{tile}_FABDEM_{FABDEM_VERSION}.tif")), None)
    if member is None:
        return None
    path = FABDEM_DIR / member.filename.split("/")[-1]
    data = path.read_bytes() if path.exists() else b""
    if len(data) != member.file_size or zlib.crc32(data) != member.CRC:
        data = zf.read(member)              # zipfile checks the CRC-32 against the archive directory
        FABDEM_DIR.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return {"name": path.name, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data), "crc32": f"{member.CRC:08x}", "archive": arc}


def fabdem_box(grid: Grid, tiles: list[dict]) -> np.ndarray:
    """FABDEM heights averaged onto the grid, the same way v1 read Copernicus GLO-30. Each tile must match its record."""
    out = np.full(grid.shape, np.nan, np.float32)
    for t in tiles:
        path = FABDEM_DIR / t["name"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != t["sha256"]:
            raise ValueError(f"{t['name']} has changed since it was recorded")
        w = warp_to_grid(path, grid, categorical=False, nodata=np.nan, dtype=np.float32)
        out = np.where(np.isfinite(out), out, w)
    return out


def heights_to_water(dem: np.ndarray, water: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """v1's rule for boxes with no river line: height and distance to the nearest mapped water (live.prepare, world branch)."""
    if water.any():
        dist_px, (iy, ix) = distance_transform_edt(~water, return_indices=True)
        return (dem - dem[iy, ix]).astype(np.float32), (dist_px * RES_M).astype(np.float32)
    return np.full(water.shape, np.nan, np.float32), np.full(water.shape, np.inf, np.float32)


# ---------- new cases ----------
def prepare(case: dict, picked: dict, score_it: bool) -> live.Prepared:
    """v1's inputs, except that a box with no lidar gets FABDEM heights. US cases are v1 exactly."""
    if case["kind"] == "us":
        p = live.prepare(case, picked, score_it)
        p.info["protocol"] = PROTOCOL
        return p
    wet_s = picked["wet"]
    grid = live.aligned_grid(case["lon"], case["lat"], wet_s)
    wet = live.read_box(case["id"], grid, wet_s)
    stack = [live.read_box(case["id"], grid, s) for s in picked["baseline"]]
    base = {"hh": median_baseline(np.stack([x["hh"] for x in stack])), "hv": median_baseline(np.stack([x["hv"] for x in stack]))}
    lc = worldcover_class(raw_lc := live.worldcover_box(grid))
    water = raw_lc == 80
    tiles = [t for la, lo in tiles_for(grid) if (t := fetch_tile(la, lo))]
    hand, dist = heights_to_water(fabdem_box(grid, tiles), water)
    info = {"epsg": grid.crs, "heights": HEIGHTS, "river": "nearest water in ESA WorldCover", "protocol": PROTOCOL, "fabdem_tiles": tiles, "licence": LICENCE}
    return live.Prepared(case["id"], case["kind"], grid, wet, base, stack[-1], hand, dist, lc, np.zeros(grid.shape, np.uint8), water, None, info)


# ---------- the v1 world cases, rebuilt under v2 ----------
def grid_of(rec: dict) -> Grid:
    """A published case's grid, from its corners: the north-west corner lies on the scene's 10 m pixel edges."""
    to_xy = Transformer.from_crs("EPSG:4326", rec["inputs"]["epsg"], always_xy=True)
    x0, y0 = to_xy.transform(*rec["corners"][0])
    return Grid(rec["inputs"]["epsg"], round(x0 / 10) * 10.0, round(y0 / 10) * 10.0, RES_M, rec["layout"]["width"], rec["layout"]["height"])


def replace_heights(folder_v1: Path, layout: dict, hand: np.ndarray, folder_v2: Path) -> None:
    """The v1 pack, byte for byte, except its height layer."""
    raw = bytearray((folder_v1 / "pack.bin").read_bytes())
    n, off = layout["width"] * layout["height"], 0
    for a in layout["arrays"]:
        size = n * {"int16": 2, "uint16": 2, "uint8": 1}[a["type"]]
        if a["name"] == "hand":
            raw[off:off + size] = live._db16(hand).tobytes()
        off += size
    folder_v2.mkdir(parents=True, exist_ok=True)
    (folder_v2 / "pack.bin").write_bytes(bytes(raw))


def replay_v1(rec: dict, folder_v1: Path, rule) -> dict:
    """Rebuild v1's heights (Copernicus GLO-30) on the rebuilt grid and rerun the rule on v1's own arrays. Must give back
    v1's published run: this is what shows the rebuild changes nothing but the height source."""
    d = decode_pack(folder_v1, rec["layout"])
    grid = grid_of(rec)
    hand, dist = heights_to_water(live.glo30_box(grid), d["water"].astype(bool))
    raw = live._db16(hand)                                     # encoded exactly as the pack stores it (hundredths, clipped at ±327.67 m)
    hand = np.where(raw == -32768, np.nan, raw / 100.0).astype(np.float32)
    res = rule.apply(d["wet_hh"] - d["median_hh"], d["wet_hv"] - d["median_hv"], d["landcover"], d["timing"], hand, d["dist"])
    ref, both = rec["reference_run"], np.isfinite(hand) | np.isfinite(d["hand"])
    height_diff = float(np.nanmax(np.abs(hand - d["hand"])))
    return {"height_max_diff_m": height_diff, "height_nan_mismatch_px": int((np.isfinite(hand) != np.isfinite(d["hand"])).sum()),
            "height_px": int(both.sum()), "dist_max_diff_m": float(np.nanmax(np.abs(np.where(np.isfinite(dist), dist, 0) - np.where(np.isfinite(d["dist"]), d["dist"], 0)))),
            "flagged_px": int(res["pred"].sum()), "flagged_px_v1": ref["flagged_px"], "threshold_db": float(res["threshold_db"]), "threshold_db_v1": ref["threshold_db"],
            "used_hh_minus_hv": bool(res["used_hh_minus_hv"]), "confident": bool(res["confident"]),
            "agrees": height_diff < 0.006 and not (np.isfinite(hand) != np.isfinite(d["hand"])).any() and int(res["pred"].sum()) == ref["flagged_px"] and abs(float(res["threshold_db"]) - ref["threshold_db"]) < 1e-6
            and bool(res["used_hh_minus_hv"]) == ref["used_hh_minus_hv"] and bool(res["confident"]) == ref["confident"]}


def rerun_world(case_id: str, rule, root: Path = OUT) -> dict:
    """Publish ``<case_id>_v2``: the v1 world case's radar, land cover and water as published, with FABDEM heights."""
    folder_v1, rec = root / case_id, json.loads((root / case_id / "case.json").read_text(encoding="utf8"))
    if rec["kind"] != "world":
        raise ValueError(f"{case_id} has lidar; v2 changes nothing there")
    d = decode_pack(folder_v1, rec["layout"])
    grid = grid_of(rec)
    tiles = [t for la, lo in tiles_for(grid) if (t := fetch_tile(la, lo))]
    hand, _ = heights_to_water(fabdem_box(grid, tiles), d["water"].astype(bool))
    folder_v2 = root / f"{case_id}{SUFFIX}"
    replace_heights(folder_v1, rec["layout"], hand, folder_v2)
    d2 = decode_pack(folder_v2, rec["layout"])
    res = rule.apply(d2["wet_hh"] - d2["median_hh"], d2["wet_hv"] - d2["median_hv"], d2["landcover"], d2["timing"], d2["hand"], d2["dist"])
    land = d2["water"] == 0
    rec2 = {**rec, "id": f"{case_id}{SUFFIX}", "protocol": PROTOCOL, "rebuilt_from": case_id,
            "inputs": {**rec["inputs"], "heights": HEIGHTS, "protocol": PROTOCOL, "fabdem_tiles": tiles, "licence": LICENCE},
            "frozen_run": {"threshold_db": res["threshold_db"], "used_hh_minus_hv": res["used_hh_minus_hv"], "confident": res["confident"],
                           "low_minus_high_db": res["low_minus_high_db"], "flagged_ha": float((res["pred"] & land).sum() * rec["pixel_ha"]),
                           "mapped_ha": float(res["mapped"].sum() * rec["pixel_ha"])},
            "reference_run": {"threshold_db": res["threshold_db"], "flagged_px": int(res["pred"].sum()), "flagged_land_px": int((res["pred"] & land).sum()),
                              "used_hh_minus_hv": res["used_hh_minus_hv"], "confident": res["confident"], "low_minus_high_db": res["low_minus_high_db"]},
            "v1_run": {"flagged_ha": rec["frozen_run"]["flagged_ha"], "confident": rec["frozen_run"]["confident"], "threshold_db": rec["frozen_run"]["threshold_db"]}}
    rec2.pop("attempt", None)
    (folder_v2 / "case.json").write_text(json.dumps(rec2, indent=2, default=lambda o: o.item() if isinstance(o, np.generic) else str(o)))
    return rec2
