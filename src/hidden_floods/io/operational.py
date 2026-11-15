"""Operational flood products used as baselines: Copernicus GFM and OPERA DSWx-S1.

Encodings (checked on the downloaded files):
- GFM (EODC STAC collection ``GFM``, Equi7 20 m): ensemble flood extent 1 = flood, 0 = no flood, 255 = no data;
  exclusion mask 1 = excluded; reference water mask 1 (and 2) = water. Some scenes have no exclusion-mask asset.
- DSWx-S1 WTR (MGRS UTM 30 m): 0 not water, 1 open water, 3 inundated vegetation, 250 HAND-masked,
  251 layover/shadow, 255 no data.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from hidden_floods.grid import Grid, warp_to_grid

DSWX_NOT_WATER, DSWX_OPEN_WATER, DSWX_INUNDATED_VEG = 0, 1, 3
DSWX_MASKED = (250, 251)
NODATA = 255


@dataclass
class GfmMosaic:
    covered: np.ndarray
    flood: np.ndarray
    excluded: np.ndarray
    reference_water: np.ndarray
    scenes: list[str]


def gfm_mosaic(ops_dir: Path, date: str, grid: Grid) -> GfmMosaic:
    """Union of all GFM scenes on ``date`` (YYYYMMDD) on ``grid``."""
    covered, flood, excluded, refw = (np.zeros(grid.shape, bool) for _ in range(4))
    scenes = []
    for fe_path in sorted(Path(ops_dir).glob(f"GFM_{date}T*_ensemble_flood_extent.tif")):
        stem = str(fe_path).removesuffix("_ensemble_flood_extent.tif")
        fe = warp_to_grid(fe_path, grid, categorical=True, nodata=NODATA)
        covered |= fe != NODATA
        flood |= fe == 1
        if Path(stem + "_exclusion_mask.tif").exists():
            excluded |= warp_to_grid(stem + "_exclusion_mask.tif", grid, categorical=True, nodata=NODATA) == 1
        if Path(stem + "_reference_water_mask.tif").exists():
            rw = warp_to_grid(stem + "_reference_water_mask.tif", grid, categorical=True, nodata=NODATA)
            refw |= (rw == 1) | (rw == 2)
        scenes.append(Path(stem).name)
    return GfmMosaic(covered, flood, excluded, refw, scenes)


def dswx_s1_mosaic(ops_dir: Path, date: str, grid: Grid) -> np.ndarray:
    """DSWx-S1 WTR classes on ``grid`` for acquisitions on ``date``; first valid tile wins where tiles overlap."""
    out = np.full(grid.shape, NODATA, np.uint8)
    for path in sorted(Path(ops_dir).glob(f"OPERA_L3_DSWx-S1_*_{date}T*_B01_WTR.tif")):
        w = warp_to_grid(path, grid, categorical=True, nodata=NODATA, dtype=np.uint8)
        out = np.where(out == NODATA, w, out)
    return out


def dswx_water(wtr: np.ndarray) -> np.ndarray:
    return (wtr == DSWX_OPEN_WATER) | (wtr == DSWX_INUNDATED_VEG)
