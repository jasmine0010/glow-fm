"""Fetch the FABDEM V1-2 tiles for the bare-earth test and record their hashes in research/bare_earth_tiles.json.

FABDEM is published as 10x10 degree zip archives of 1x1 degree GeoTIFF tiles (about 2 GB each). The server supports byte ranges, so only the
archive directory and the needed tiles are read. Tiles are written and hashed, never decoded: no elevation over a test river is looked at here.
Yellow is included for the code check; it is not a test river, and the script refuses if its tiles also cover one.

Source: University of Bristol data repository, https://doi.org/10.5523/bris.s5hqmjcdj8yo2ibzi9b4ew3sn (FABDEM V1-2).
Licence: CC BY-NC-SA 4.0 (the dataset's readme.txt and license.txt). Hawker et al. (2022), Environ. Res. Lett. 17, 024016.
FABDEM is produced using Copernicus WorldDEM-30 (c) DLR e.V. 2010-2014 and (c) Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS
by the European Union and ESA; all rights reserved.
"""

import hashlib
import io
import json
import math
import urllib.request
import zipfile
import zlib
from datetime import UTC, datetime

from hidden_floods.config import load_site
from hidden_floods.frozen_bare_earth import DEM_DIR, TILES
from hidden_floods.frozen_no_lidar import PASSES

BASE = "https://data.bris.ac.uk/datasets/s5hqmjcdj8yo2ibzi9b4ew3sn"
VERSION = "V1-2"
HEADERS = {"User-Agent": "research-client"}


class RangeFile(io.RawIOBase):
    """A read-only, seekable view of a remote file, fetched with HTTP range requests."""

    def __init__(self, url: str):
        self.url, self.pos = url, 0
        with urllib.request.urlopen(urllib.request.Request(url, method="HEAD", headers=HEADERS), timeout=120) as r:
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
        req = urllib.request.Request(self.url, headers={**HEADERS, "Range": f"bytes={self.pos}-{end}"})
        with urllib.request.urlopen(req, timeout=600) as r:
            data = r.read()
        b[: len(data)] = data
        self.pos += len(data)
        return len(data)


def tile_names(river: str) -> list[str]:
    w, s, e, n = load_site(river).bbox
    return [f"{'N' if la >= 0 else 'S'}{abs(la):02d}{'E' if lo >= 0 else 'W'}{abs(lo):03d}" for la in range(math.floor(s), math.ceil(n)) for lo in range(math.floor(w), math.ceil(e))]


def archive_for(tile: str) -> str:
    """The 10x10 degree archive holding a 1x1 degree tile, named by its south-west and north-east corners."""
    lat = int(tile[1:3]) * (1 if tile[0] == "N" else -1)
    lon = int(tile[4:7]) * (1 if tile[3] == "E" else -1)
    la, lo = 10 * math.floor(lat / 10), 10 * math.floor(lon / 10)
    name = lambda a, o: f"{'N' if a >= 0 else 'S'}{abs(a):02d}{'E' if o >= 0 else 'W'}{abs(o):03d}"
    return f"{name(la, lo)}-{name(la + 10, lo + 10)}_FABDEM_{VERSION}.zip"


def main():
    test = sorted({r for r, _ in PASSES})
    wanted = {r: tile_names(r) for r in [*test, "yellow"]}
    test_tiles = {t for r in test for t in wanted[r]}
    if set(wanted["yellow"]) & test_tiles:
        raise SystemExit(f"the code-check tiles cover a test river: {set(wanted['yellow']) & test_tiles}")
    DEM_DIR.mkdir(parents=True, exist_ok=True)
    out = {"source": {"dataset": "FABDEM", "version": VERSION, "doi": "https://doi.org/10.5523/bris.s5hqmjcdj8yo2ibzi9b4ew3sn", "licence": "CC BY-NC-SA 4.0",
                      "citation": "Hawker, L. et al. (2022) A 30 m global map of elevation with forests and buildings removed. Environ. Res. Lett. 17, 024016",
                      "fetched_utc": datetime.now(UTC).isoformat(timespec="seconds"), "archives": {}}, "tiles": {}}
    archives = {}
    for river, tiles in wanted.items():
        out["tiles"][river] = {}
        for tile in tiles:
            arc = archive_for(tile)
            if arc not in archives:
                raw = RangeFile(f"{BASE}/{arc}")
                archives[arc] = zipfile.ZipFile(io.BufferedReader(raw, buffer_size=1 << 20))
                out["source"]["archives"][arc] = {"url": f"{BASE}/{arc}", "bytes": raw.size}
            zf = archives[arc]
            members = [m for m in zf.infolist() if m.filename.endswith(f"{tile}_FABDEM_{VERSION}.tif")]
            if not members:
                print(river, tile, "not in the archive (no land or no data)", flush=True)
                continue
            m = members[0]
            name = m.filename.split("/")[-1]
            path = DEM_DIR / name
            data = path.read_bytes() if path.exists() else b""
            if len(data) != m.file_size or zlib.crc32(data) != m.CRC:   # resume: reuse a tile only if it matches the archive directory
                data = zf.read(m)           # zipfile checks the member's CRC-32 against the archive directory
                path.write_bytes(data)
            out["tiles"][river][name] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data), "crc32": f"{m.CRC:08x}", "archive": arc}
            print(river, name, len(data), flush=True)
    TILES.write_text(json.dumps(out, indent=1))
    print("BARE EARTH TILES DONE", flush=True)


if __name__ == "__main__":
    main()
