"""NISAR L2 PROVISIONAL products (GCOV backscatter, GUNW interferograms), read from local HDF5 files.

Layout notes (product specification 1.5.0, PROVISIONAL CRID P05023):
- GCOV: ``science/LSAR/GCOV/grids/frequencyA/{HHHH,HVHV}`` are linear power (NaN fill) on a 10 m UTM grid whose
  ``xCoordinates``/``yCoordinates`` are pixel centres.
- GUNW: ``.../unwrappedInterferogram/HH/*`` at 80 m and ``.../wrappedInterferogram/HH/*`` at 20 m;
  incidence angle is a (height, y, x) cube under ``science/LSAR/GUNW/metadata/radarGrid``.
"""

from __future__ import annotations

from dataclasses import dataclass

import h5py
import numpy as np

from hidden_floods.grid import Grid, block_mean

GCOV_GRID = "science/LSAR/GCOV/grids/frequencyA"
GUNW_UNW = "science/LSAR/GUNW/grids/frequencyA/unwrappedInterferogram/HH"
GUNW_WRP = "science/LSAR/GUNW/grids/frequencyA/wrappedInterferogram/HH"
GUNW_RADARGRID = "science/LSAR/GUNW/metadata/radarGrid"
IDENT = "science/LSAR/identification"

L_BAND_CENTER_HZ = 1.239e9
WAVELENGTH_M = 299792458.0 / L_BAND_CENTER_HZ


def _epsg(group) -> str:
    return f"EPSG:{int(group['projection'][()])}"


def _window(xc: np.ndarray, yc: np.ndarray, spacing: float, grid: Grid):
    """Index window of a centre-coordinate source grid that tiles ``grid`` exactly (requires aligned pixel edges)."""
    edge_x0, edge_y0 = xc[0] - spacing / 2, yc[0] + spacing / 2
    c0 = (grid.x0 - edge_x0) / spacing
    r0 = (edge_y0 - grid.y0) / spacing
    if abs(c0 - round(c0)) > 1e-6 or abs(r0 - round(r0)) > 1e-6:
        raise ValueError("analysis grid corner is not aligned with source pixel edges")
    factor = grid.res / spacing
    if abs(factor - round(factor)) > 1e-9:
        raise ValueError(f"analysis resolution {grid.res} m is not a multiple of source spacing {spacing} m")
    return round(r0), round(c0), round(factor)


def _read_window(ds, r0: int, c0: int, nrows: int, ncols: int) -> np.ndarray:
    """Read rows/cols from a 2-D dataset, padding with NaN where the window leaves the dataset."""
    out = np.full((nrows, ncols), np.nan, dtype=np.float32)
    rr0, cc0 = max(r0, 0), max(c0, 0)
    rr1, cc1 = min(r0 + nrows, ds.shape[0]), min(c0 + ncols, ds.shape[1])
    if rr1 > rr0 and cc1 > cc0:
        out[rr0 - r0 : rr1 - r0, cc0 - c0 : cc1 - c0] = ds[rr0:rr1, cc0:cc1]
    return out


def read_gcov(path, grid: Grid, terms=("HHHH", "HVHV")) -> dict[str, np.ndarray]:
    """GCOV covariance terms on ``grid`` as linear power, by block-averaging the 10 m pixels (multilooking)."""
    with h5py.File(path, "r") as h:
        g = h[GCOV_GRID]
        if _epsg(g) != grid.crs:
            raise ValueError(f"GCOV projection {_epsg(g)} differs from grid {grid.crs}")
        xc, yc = g["xCoordinates"][:], g["yCoordinates"][:]
        spacing = float(g["xCoordinateSpacing"][()])
        r0, c0, f = _window(xc, yc, spacing, grid)
        return {t: block_mean(_read_window(g[t], r0, c0, grid.height * f, grid.width * f), f) for t in terms}


def identification(path) -> dict[str, object]:
    """Small identification fields (track, direction, times, urgent-observation flag) for provenance."""
    keys = ("granuleId", "trackNumber", "orbitPassDirection", "zeroDopplerStartTime", "isUrgentObservation",
            "compositeReleaseId", "productVersion")
    out = {}
    with h5py.File(path, "r") as h:
        g = h[IDENT]
        for k in keys:
            if k in g:
                v = g[k][()]
                out[k] = v.decode() if isinstance(v, bytes) else (v.item() if hasattr(v, "item") else v)
    return out


@dataclass
class GunwLayers:
    """GUNW layers cropped to a box on their native grid (centre coordinates)."""

    xs: np.ndarray
    ys: np.ndarray
    layers: dict[str, np.ndarray]


def read_gunw_box(path, xy_box, which: str = "unwrapped", layers=None) -> GunwLayers:
    """Crop GUNW layers to ``xy_box`` = (xmin, ymin, xmax, ymax) in the product projection.

    ``which`` is ``"unwrapped"`` (80 m: unwrappedPhase, coherenceMagnitude, ionospherePhaseScreen, connectedComponents)
    or ``"wrapped"`` (20 m: wrappedInterferogram as complex64, coherenceMagnitude).
    """
    group = GUNW_UNW if which == "unwrapped" else GUNW_WRP
    if layers is None:
        layers = (("unwrappedPhase", "coherenceMagnitude", "ionospherePhaseScreen", "connectedComponents")
                  if which == "unwrapped" else ("wrappedInterferogram", "coherenceMagnitude"))
    xmin, ymin, xmax, ymax = xy_box
    with h5py.File(path, "r") as h:
        g = h[group]
        xc, yc = g["xCoordinates"][:], g["yCoordinates"][:]
        c0, c1 = np.searchsorted(xc, xmin), np.searchsorted(xc, xmax)
        r0, r1 = np.searchsorted(-yc, -ymax), np.searchsorted(-yc, -ymin)
        return GunwLayers(xc[c0:c1], yc[r0:r1], {n: g[n][r0:r1, c0:c1] for n in layers})


def gunw_incidence_deg(path, x: float, y: float) -> float:
    """Incidence angle (degrees) at a map point, from the middle height layer of the radar-grid cube."""
    with h5py.File(path, "r") as h:
        g = h[GUNW_RADARGRID]
        cube = g["incidenceAngle"]
        gx, gy = g["xCoordinates"][:], g["yCoordinates"][:]
        ix, iy = int(np.abs(gx - x).argmin()), int(np.abs(gy - y).argmin())
        column = cube[:, iy, ix]
        return float(column[len(column) // 2])
