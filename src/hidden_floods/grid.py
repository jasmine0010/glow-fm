"""The shared analysis grid: every layer is brought onto one north-up UTM grid before comparison."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.transform import Affine, from_origin
from rasterio.warp import Resampling, reproject


@dataclass(frozen=True)
class Grid:
    """North-up grid. ``x0``/``y0`` are the outer corner of the top-left pixel (not its centre)."""

    crs: str
    x0: float
    y0: float
    res: float
    width: int
    height: int

    @property
    def shape(self) -> tuple[int, int]:
        return self.height, self.width

    @property
    def transform(self) -> Affine:
        return from_origin(self.x0, self.y0, self.res, self.res)

    @property
    def xs(self) -> np.ndarray:
        """Pixel-centre x coordinates (one per column)."""
        return self.x0 + (np.arange(self.width) + 0.5) * self.res

    @property
    def ys(self) -> np.ndarray:
        """Pixel-centre y coordinates (one per row), decreasing downwards."""
        return self.y0 - (np.arange(self.height) + 0.5) * self.res

    @property
    def pixel_area_ha(self) -> float:
        return self.res * self.res / 1e4

    def meshgrid(self) -> tuple[np.ndarray, np.ndarray]:
        return np.meshgrid(self.xs, self.ys)

    def to_xy(self, lon, lat):
        return Transformer.from_crs(4326, self.crs, always_xy=True).transform(lon, lat)

    def to_lonlat(self, x, y):
        return Transformer.from_crs(self.crs, 4326, always_xy=True).transform(x, y)

    def index_of(self, x, y) -> tuple[np.ndarray, np.ndarray]:
        """Row/column (possibly out of range) of the pixels containing points x, y."""
        col = np.floor((np.asarray(x) - self.x0) / self.res).astype(int)
        row = np.floor((self.y0 - np.asarray(y)) / self.res).astype(int)
        return row, col

    def contains_index(self, row, col) -> np.ndarray:
        return (row >= 0) & (row < self.height) & (col >= 0) & (col < self.width)


def grid_from_lonlat_bbox(bbox, crs: str, res: float, snap: float | None = None) -> Grid:
    """Grid covering a lon/lat box, with its corner snapped to a multiple of ``snap`` metres (default ``res``)."""
    west, south, east, north = bbox
    t = Transformer.from_crs(4326, crs, always_xy=True)
    xs, ys = t.transform([west, east, west, east], [south, south, north, north])
    snap = snap or res
    x0 = np.floor(min(xs) / snap) * snap
    y0 = np.ceil(max(ys) / snap) * snap
    x1 = np.ceil(max(xs) / snap) * snap
    y1 = np.floor(min(ys) / snap) * snap
    return Grid(crs, float(x0), float(y0), float(res), round((x1 - x0) / res), round((y0 - y1) / res))


def block_mean(a: np.ndarray, factor: int) -> np.ndarray:
    """Mean over non-overlapping ``factor`` x ``factor`` blocks, ignoring NaN. Trailing partial blocks are dropped."""
    h, w = (a.shape[0] // factor) * factor, (a.shape[1] // factor) * factor
    blocks = a[:h, :w].reshape(h // factor, factor, w // factor, factor)
    with np.errstate(invalid="ignore"):
        return np.nanmean(blocks, axis=(1, 3))


def warp_to_grid(src_path, grid: Grid, categorical: bool, band: int = 1, nodata=None, dtype=None) -> np.ndarray:
    """Resample a raster file onto ``grid``: nearest neighbour for class maps, area-average for continuous data."""
    with rasterio.open(src_path) as src:
        dtype = dtype or (src.dtypes[band - 1] if categorical else "float32")
        fill = nodata if nodata is not None else (src.nodata if src.nodata is not None else (255 if categorical else np.nan))
        out = np.full(grid.shape, fill, dtype=dtype)
        reproject(
            rasterio.band(src, band),
            out,
            dst_transform=grid.transform,
            dst_crs=grid.crs,
            resampling=Resampling.nearest if categorical else Resampling.average,
            src_nodata=src.nodata,
            dst_nodata=fill,
        )
    return out
