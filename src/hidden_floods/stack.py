"""Corridor-only reads of many NISAR scenes, for a per-pixel multi-date baseline.

A GCOV file is about 6 GB, but a river corridor needs only part of it. The file is opened over HTTP range requests, so
only the needed chunks travel. Earthdata sign-in is handled by curl from the user's ``~/.netrc``; the signed link it
ends at is short-lived, used in memory and never saved or printed.
"""

from __future__ import annotations

import io
import re
import subprocess
import time
import urllib.parse
import urllib.request
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from hidden_floods.config import Site, data_root
from hidden_floods.fetch import CMR, get_json
from hidden_floods.grid import Grid
from hidden_floods.io.nisar import read_gcov

GRANULE = re.compile(r"GCOV_(\d+)_(\d+)_([AD])_(\d+)_(\d+)_([A-Z]+)_A_(\d{8}T\d{6})_.*_P05023_._F_J_(\d+)$")
BLOCK = 4 * 1024 * 1024
MAX_BLOCKS = 64


@dataclass(frozen=True)
class Scene:
    name: str
    track: str
    frame: str
    time: str
    url: str


def parse(name: str) -> dict | None:
    m = GRANULE.search(name)
    if not m:
        return None
    t = m[7]
    return {"track": m[2] + m[3], "frame": m[4], "mode": f"{m[5]}_{m[6]}", "time": f"{t[:4]}-{t[4:6]}-{t[6:8]}T{t[9:11]}:{t[11:13]}:{t[13:15]}Z", "version": m[8]}


def track_scenes(bbox, track: str, frame: str, start: str, end: str) -> list[Scene]:
    """All 40 MHz HH+HV provisional scenes on one track and frame, latest version per date, oldest first."""
    q = urllib.parse.urlencode({"short_name": "NISAR_L2_GCOV_PROVISIONAL_V1", "bounding_box": ",".join(map(str, bbox)),
                                "temporal": f"{start},{end}", "page_size": 200, "sort_key": "start_date"})
    best: dict[str, tuple[str, Scene]] = {}
    for it in get_json(f"{CMR}?{q}").get("items", []):
        name = it["umm"]["GranuleUR"]
        p = parse(name)
        if not p or p["track"] != track or p["frame"] != frame or p["mode"] != "4005_DHDH":
            continue
        url = next((u["URL"] for u in it["umm"].get("RelatedUrls", [])
                    if u.get("Type") == "GET DATA" and u["URL"].startswith("https") and u["URL"].endswith(".h5")), None)
        if url and (p["time"] not in best or p["version"] > best[p["time"]][0]):
            best[p["time"]] = (p["version"], Scene(name, track, frame, p["time"], url))
    return [best[t][1] for t in sorted(best)]


def signed_url(url: str, jar: Path) -> str:
    """Follow the Earthdata sign-in with curl and return the final link. curl reads the credentials, this code never does."""
    jar.parent.mkdir(parents=True, exist_ok=True)
    out = subprocess.run(["curl", "-s", "-n", "-L", "--fail", "--retry", "3", "-c", str(jar), "-b", str(jar), "-r", "0-0", "-o", "NUL", "-w", "%{url_effective}", url],
                         check=True, capture_output=True, text=True)
    return out.stdout.strip()


class RangeFile(io.RawIOBase):
    """Read-only file over HTTP range requests, with a small block cache."""

    def __init__(self, url: str, size: int | None = None):
        super().__init__()
        self.url, self.pos, self.bytes_fetched = url, 0, 0
        self.blocks: OrderedDict[int, bytes] = OrderedDict()
        self.size = size if size is not None else self._size()

    def _get(self, start: int, end: int) -> tuple[bytes, str]:
        req = urllib.request.Request(self.url, headers={"Range": f"bytes={start}-{end}"})
        for attempt in range(5):
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    return r.read(), r.headers.get("Content-Range", "")
            except OSError:
                if attempt == 4:
                    raise
                time.sleep(3 * (attempt + 1))
        raise RuntimeError("unreachable")

    def _size(self) -> int:
        return int(self._get(0, 0)[1].rsplit("/", 1)[1])

    def _block(self, i: int) -> bytes:
        if i in self.blocks:
            self.blocks.move_to_end(i)
            return self.blocks[i]
        data = self._get(i * BLOCK, min((i + 1) * BLOCK, self.size) - 1)[0]
        self.bytes_fetched += len(data)
        self.blocks[i] = data
        if len(self.blocks) > MAX_BLOCKS:
            self.blocks.popitem(last=False)
        return data

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def seek(self, offset: int, whence: int = 0) -> int:
        self.pos = {0: offset, 1: self.pos + offset, 2: self.size + offset}[whence]
        return self.pos

    def tell(self) -> int:
        return self.pos

    def readinto(self, b) -> int:
        n = min(len(b), max(self.size - self.pos, 0))
        done, view = 0, memoryview(b)
        while done < n:
            i, off = (self.pos + done) // BLOCK, (self.pos + done) % BLOCK
            chunk = self._block(i)
            take = min(n - done, len(chunk) - off)
            view[done:done + take] = chunk[off:off + take]
            done += take
        self.pos += done
        return done


def cache_path(site: Site, scene_name: str) -> Path:
    return data_root() / "stack" / site.name / f"{scene_name}.npz"


def read_scene(site: Site, grid: Grid, scene: Scene, local_dirs: tuple[Path, ...] = ()) -> dict[str, np.ndarray]:
    """HH and HV (dB) on the site grid: from the cache, then a local full file, then range requests."""
    path = cache_path(site, scene.name)
    if path.exists():
        z = np.load(path)
        return {"hh": z["hh"], "hv": z["hv"]}
    source = next((d / f"{scene.name}.h5" for d in local_dirs if (d / f"{scene.name}.h5").exists()), None)
    if source is None:
        source = RangeFile(signed_url(scene.url, data_root() / "stack" / "cookies.txt"))
    power = read_gcov(source, grid)
    with np.errstate(divide="ignore", invalid="ignore"):
        hh, hv = 10 * np.log10(power["HHHH"]).astype(np.float32), 10 * np.log10(power["HVHV"]).astype(np.float32)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, hh=hh, hv=hv)
    return {"hh": hh, "hv": hv}
