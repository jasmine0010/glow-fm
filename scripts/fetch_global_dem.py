"""Download Copernicus GLO-30 tiles for the no-lidar test and record their hashes in research/global_dem_tiles.json.

The tiles are only hashed here, not opened. The public archive needs no login. Yellow is included for the code check, and isn't a test river.
Copernicus DEM: © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018, provided under COPERNICUS by the European Union and ESA.
"""

import hashlib
import json
import math
import re
import subprocess

from hidden_floods.config import load_site
from hidden_floods.fetch import download
from hidden_floods.frozen_no_lidar import DEM_DIR, PASSES, TILES

BASE = "https://copernicus-dem-30m.s3.eu-central-1.amazonaws.com"


def tile_name(lat: int, lon: int) -> str:
    return f"Copernicus_DSM_COG_10_{'N' if lat >= 0 else 'S'}{abs(lat):02d}_00_{'E' if lon >= 0 else 'W'}{abs(lon):03d}_00_DEM"


def main():
    out = {}
    for river in sorted({r for r, _ in PASSES} | {"yellow"}):
        w, s, e, n = load_site(river).bbox
        out[river] = {}
        for lat in range(math.floor(s), math.ceil(n)):
            for lon in range(math.floor(w), math.ceil(e)):
                name = tile_name(lat, lon)
                url, path = f"{BASE}/{name}/{name}.tif", DEM_DIR / f"{name}.tif"
                head = subprocess.run(["curl", "-sIL", "--fail", url], check=False, capture_output=True, text=True)
                if head.returncode:
                    print(river, name, "not in the archive", flush=True)
                    continue
                size = int(re.findall(r"content-length:\s*(\d+)", head.stdout, re.IGNORECASE)[-1])
                if path.exists() and path.stat().st_size != size:
                    path.unlink()
                download(url, path)
                if path.stat().st_size != size:
                    raise RuntimeError(f"{name}: got {path.stat().st_size} bytes, expected {size}")
                out[river][name] = hashlib.sha256(path.read_bytes()).hexdigest()
                print(river, name, size, flush=True)
    TILES.write_text(json.dumps(out, indent=1))
    print("GLOBAL DEM TILES DONE", flush=True)


if __name__ == "__main__":
    main()
