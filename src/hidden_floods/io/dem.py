"""USGS 3DEP bare-earth elevation (NAVD88 metres).

Fetched from the 3DEP ImageServer in tiles (one large request times out with HTTP 504). Over the Choctawhatchee
floodplain the service draws on 1 m lidar DEMs (FL_Lower_Choctawhatchee_NWFWMD_Lidar_2017, FL_HurricaneMichael_2020).
"""

from __future__ import annotations

import io
import time
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
import rasterio

from hidden_floods.grid import Grid, warp_to_grid

EXPORT_URL = "https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer/exportImage"


def fetch_3dep(grid: Grid, out_path: Path, tile_px: int = 1000, retries: int = 4) -> Path:
    """Download a bare-earth DEM covering ``grid`` at ``grid.res`` and write it as a GeoTIFF."""
    epsg = int(grid.crs.split(":")[1])
    dem = np.full(grid.shape, np.nan, np.float32)
    for r0 in range(0, grid.height, tile_px):
        for c0 in range(0, grid.width, tile_px):
            h, w = min(tile_px, grid.height - r0), min(tile_px, grid.width - c0)
            bx0, by1 = grid.x0 + c0 * grid.res, grid.y0 - r0 * grid.res
            query = {"bbox": f"{bx0},{by1 - h * grid.res},{bx0 + w * grid.res},{by1}", "bboxSR": epsg, "imageSR": epsg,
                     "size": f"{w},{h}", "format": "tiff", "pixelType": "F32", "noData": -9999,
                     "interpolation": "RSP_BilinearInterpolation", "f": "image"}
            for attempt in range(retries):
                try:
                    data = urllib.request.urlopen(EXPORT_URL + "?" + urllib.parse.urlencode(query), timeout=300).read()
                    with rasterio.open(io.BytesIO(data)) as src:
                        tile = src.read(1).astype(np.float32)
                    break
                except Exception:
                    if attempt == retries - 1:
                        raise
                    time.sleep(5)
            tile[tile < -9000] = np.nan
            dem[r0 : r0 + h, c0 : c0 + w] = tile[:h, :w]
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(out_path, "w", driver="GTiff", height=grid.height, width=grid.width, count=1, dtype="float32",
                       crs=grid.crs, transform=grid.transform, nodata=np.nan, compress="deflate") as dst:
        dst.write(dem, 1)
    return out_path


def dem_on_grid(dem_path: Path, grid: Grid) -> np.ndarray:
    """Bare-earth elevation averaged onto ``grid``."""
    return warp_to_grid(dem_path, grid, categorical=False, nodata=np.nan, dtype=np.float32)
