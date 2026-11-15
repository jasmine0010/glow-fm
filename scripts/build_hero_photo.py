"""The story page's satellite photo: cloud-free Sentinel-2 true color of the Satilla on Oct 14, 2026, 18.5 hours before NISAR's Oct 15 pass.

Same scene as research/INDEPENDENT_CHECK_PROTOCOL.md. The result is cached in outputs/hero_photo, because a full build clears app/data.
"""
import json
import urllib.request
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from rasterio.enums import Resampling
from rasterio.transform import from_bounds
from rasterio.vrt import WarpedVRT
from rasterio.warp import transform_bounds
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "outputs" / "hero_photo" / "photo_s2.jpg"
OUT = ROOT / "app" / "data" / "satilla" / "047A_oct15" / "photo_s2.webp"
META = CACHE.with_suffix(".json")
# Wider than the river's strip, so the photo fills the hero map on any screen.
WEST, SOUTH, EAST, NORTH = -82.78, 30.86, -81.65, 31.66
WIDTH = 2800
SEARCH = "https://earth-search.aws.element84.com/v1/search"


def items():
    body = {"collections": ["sentinel-2-l2a"], "bbox": [WEST, SOUTH, EAST, NORTH], "datetime": "2026-10-14T00:00:00Z/2026-10-14T23:59:59Z", "limit": 50}
    request = urllib.request.Request(SEARCH, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "User-Agent": "hidden-floods-research/0.1"})
    return json.loads(urllib.request.urlopen(request, timeout=90).read())["features"]


def build():
    found = items()
    left, bottom, right, top = transform_bounds("EPSG:4326", "EPSG:3857", WEST, SOUTH, EAST, NORTH)
    height = round(WIDTH * (top - bottom) / (right - left))
    transform = from_bounds(left, bottom, right, top, WIDTH, height)
    photo = np.zeros((3, height, WIDTH), np.uint8)
    for item in found:
        with rasterio.open(item["assets"]["visual"]["href"]) as src, WarpedVRT(src, crs="EPSG:3857", transform=transform, width=WIDTH, height=height, resampling=Resampling.average, nodata=0) as vrt:
            part = vrt.read()
        empty = photo.sum(0) == 0
        photo[:, empty] = part[:, empty]
    covered = float((photo.sum(0) > 0).mean())
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.moveaxis(photo, 0, -1)).save(CACHE, quality=84, optimize=True)
    META.write_text(json.dumps({"scenes": [f["id"] for f in found], "clouds": [f["properties"]["eo:cloud_cover"] for f in found], "times": [f["properties"]["datetime"] for f in found], "covered_share": round(covered, 3), "corners": [[WEST, NORTH], [EAST, NORTH], [EAST, SOUTH], [WEST, SOUTH]], "size": [WIDTH, height]}, indent=1))


def main():
    if not CACHE.exists():
        build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    photo = np.array(Image.open(CACHE).convert("RGB"))
    # Black ground that reaches the image's edge is past the satellite's swath, so the map shows through there.
    dark, _ = ndimage.label(photo.sum(2) < 12)
    edge = np.unique(np.r_[dark[0], dark[-1], dark[:, 0], dark[:, -1]])
    outside = np.isin(dark, edge[edge > 0])
    alpha = np.where(ndimage.binary_dilation(outside, iterations=2), 0, 255).astype(np.uint8)
    Image.fromarray(np.dstack([photo, alpha]), "RGBA").save(OUT, quality=82, method=5)
    print(META.read_text(), OUT.stat().st_size / 1e6, "MB")


if __name__ == "__main__":
    main()
