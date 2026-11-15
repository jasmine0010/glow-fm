"""Module C — hydraulic truth under the canopy.

Water-surface elevation at each gauge (stage at the satellite time, converted to NAVD88) is interpolated along the
valley, then compared with lidar bare earth: water well above the ground and hydraulically connected to the channel
means flooded; ground well above the water means dry. Pixels near the water line are left unlabelled.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage

from hidden_floods.grid import Grid


@dataclass
class ValleyLine:
    """A polyline in grid coordinates (metres), upstream -> downstream."""

    x: np.ndarray
    y: np.ndarray

    @classmethod
    def from_lonlat(cls, grid: Grid, lonlat) -> ValleyLine:
        lon, lat = zip(*lonlat)
        x, y = grid.to_xy(np.array(lon), np.array(lat))
        return cls(np.asarray(x, float), np.asarray(y, float))

    @property
    def cumulative(self) -> np.ndarray:
        return np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(self.x), np.diff(self.y)))])

    def project(self, px: np.ndarray, py: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Distance to the line and chainage (distance along it) of the nearest point, for each input point."""
        cum = self.cumulative
        best_d = np.full(np.shape(px), np.inf)
        best_s = np.zeros(np.shape(px))
        for i in range(len(self.x) - 1):
            ax, ay, bx, by = self.x[i], self.y[i], self.x[i + 1], self.y[i + 1]
            seg2 = (bx - ax) ** 2 + (by - ay) ** 2
            t = np.clip(((px - ax) * (bx - ax) + (py - ay) * (by - ay)) / seg2, 0.0, 1.0)
            d = np.hypot(px - (ax + t * (bx - ax)), py - (ay + t * (by - ay)))
            closer = d < best_d
            best_d = np.where(closer, d, best_d)
            best_s = np.where(closer, cum[i] + t * np.sqrt(seg2), best_s)
        return best_d, best_s


def refine_centerline(line: ValleyLine, channel: np.ndarray, grid: Grid, search_m: float = 3000.0,
                      step_m: float = 1000.0, smooth: int = 2) -> ValleyLine:
    """Re-centre a coarse valley line on a channel/water mask.

    Walks the coarse line every ``step_m``; at each station takes the median position of channel pixels within
    ``search_m`` of that station, then smooths with a running mean of half-width ``smooth`` stations. Stations with no
    channel pixels keep the coarse position.
    """
    cum = line.cumulative
    stations = np.arange(0.0, cum[-1] + 1e-9, step_m)
    sx, sy = np.interp(stations, cum, line.x), np.interp(stations, cum, line.y)
    rows, cols = np.nonzero(channel)
    cx, cy = grid.xs[cols], grid.ys[rows]
    nx, ny = sx.copy(), sy.copy()
    for i, (x, y) in enumerate(zip(sx, sy)):
        near = np.hypot(cx - x, cy - y) < search_m
        if near.sum() >= 3:
            nx[i], ny[i] = np.median(cx[near]), np.median(cy[near])
    if smooth > 0 and len(nx) > 2 * smooth + 1:
        k = np.ones(2 * smooth + 1) / (2 * smooth + 1)
        pad = lambda a: np.pad(a, smooth, mode="edge")
        nx, ny = np.convolve(pad(nx), k, "valid"), np.convolve(pad(ny), k, "valid")
    # keep the exact gauge-defined end points so chainage at the gauges is unchanged in meaning
    nx[0], ny[0], nx[-1], ny[-1] = line.x[0], line.y[0], line.x[-1], line.y[-1]
    return ValleyLine(nx, ny)


@dataclass
class TruthLabels:
    wet: np.ndarray
    dry: np.ndarray
    depth_m: np.ndarray          # water-surface elevation minus ground (NaN outside the corridor)
    wse_m: np.ndarray            # interpolated water-surface elevation
    distance_m: np.ndarray       # distance to the valley line
    chainage_m: np.ndarray       # distance along the valley line from the upstream end
    corridor: np.ndarray


def interpolate_wse(chainage_m: np.ndarray, gauge_chainage_m, gauge_wse_m) -> np.ndarray:
    """Water-surface elevation along the valley, linear between gauges and held flat beyond the end gauges."""
    order = np.argsort(gauge_chainage_m)
    return np.interp(chainage_m, np.asarray(gauge_chainage_m)[order], np.asarray(gauge_wse_m)[order])


def connected_to_channel(below_water: np.ndarray, seeds: np.ndarray) -> np.ndarray:
    """Pixels below the water surface that connect (8-neighbour) to at least one channel seed pixel."""
    labels, n = ndimage.label(below_water, structure=np.ones((3, 3), bool))
    if n == 0:
        return np.zeros_like(below_water)
    keep = np.unique(labels[seeds & below_water])
    keep = keep[keep > 0]
    return np.isin(labels, keep)


def hydraulic_truth(grid: Grid, dem_m: np.ndarray, line: ValleyLine, gauge_xy, gauge_wse_m, corridor_m: float,
                    margin_m: float, max_dry_height_m: float, channel_seeds: np.ndarray | None = None,
                    max_chainage_m: float | None = None) -> TruthLabels:
    """Truth labels on ``grid``.

    ``gauge_xy`` are gauge positions in grid coordinates; each is projected onto ``line`` to get its chainage.
    If ``channel_seeds`` is given, wet labels additionally require connection to the channel through pixels whose
    ground is below the water surface. ``max_chainage_m`` stops labelling past the last gauge (default: last gauge).
    """
    X, Y = grid.meshgrid()
    dist, chain = line.project(X, Y)
    gx, gy = np.array([p[0] for p in gauge_xy]), np.array([p[1] for p in gauge_xy])
    _, g_chain = line.project(gx, gy)
    wse = interpolate_wse(chain, g_chain, gauge_wse_m)
    lo = float(np.min(g_chain))
    hi = float(np.max(g_chain)) if max_chainage_m is None else float(max_chainage_m)
    corridor = (dist < corridor_m) & np.isfinite(dem_m) & (chain >= lo) & (chain <= hi)
    depth = np.where(corridor, wse - dem_m, np.nan)
    wet = corridor & (depth > margin_m)
    if channel_seeds is not None:
        wet &= connected_to_channel(corridor & (depth > 0), channel_seeds)
    dry = corridor & (depth < -margin_m) & (depth > -max_dry_height_m)
    return TruthLabels(wet, dry, depth, wse, dist, chain, corridor)
