"""Method v2 — a self-calibrating flooded-forest detector and a truth-confidence rule.

Motivation (research/SECOND_EVENT_RESULTS.md): the size of the L-band double-bounce ΔHH change varies by event
(+3.0 dB at Isaias, +1.0 dB at Pearl), so a fixed threshold does not transfer. v2 takes everything it needs from
the scene and the terrain, never from gauges or truth:

- a height-above-river surface (HAND proxy) from lidar alone: the channel elevation profile along the valley line,
  taken as a low percentile of the DEM next to the line, so DEM minus that profile is height above the river;
- a *reference* ΔHH distribution from forest well above the river (cannot flood), whose upper quantile sets the
  scene's own change threshold;
- detection = forest AND low height above river AND ΔHH above the scene threshold.
"""

from __future__ import annotations

import itertools
from dataclasses import asdict, dataclass

import numpy as np

from hidden_floods.detect import PairFeatures


def channel_profile(dem_m: np.ndarray, distance_m: np.ndarray, chainage_m: np.ndarray, near_m: float = 250.0,
                    bin_m: float = 1000.0, q: float = 10.0) -> tuple[np.ndarray, np.ndarray]:
    """Channel elevation along the valley: the ``q``-th percentile of DEM within ``near_m`` of the line, per
    ``bin_m`` chainage bin, forced non-increasing downstream. Returns (bin centres, elevations)."""
    sel = (distance_m < near_m) & np.isfinite(dem_m)
    s, z = chainage_m[sel], dem_m[sel]
    edges = np.arange(0.0, s.max() + bin_m, bin_m)
    centres, elev = [], []
    for a, b in itertools.pairwise(edges):
        m = (s >= a) & (s < b)
        if m.sum() >= 5:
            centres.append((a + b) / 2)
            elev.append(np.percentile(z[m], q))
    elev = np.minimum.accumulate(np.array(elev))  # water flows downhill
    return np.array(centres), elev


def height_above_river(dem_m: np.ndarray, distance_m: np.ndarray, chainage_m: np.ndarray, **kw) -> np.ndarray:
    centres, elev = channel_profile(dem_m, distance_m, chainage_m, **kw)
    return dem_m - np.interp(chainage_m, centres, elev)


def smooth_nan(a: np.ndarray, size: int) -> np.ndarray:
    """NaN-aware ``size`` x ``size`` box mean (size <= 1 returns the input)."""
    if size <= 1:
        return a
    from scipy.ndimage import uniform_filter

    ok = np.isfinite(a)
    num = uniform_filter(np.where(ok, a, 0.0), size, mode="nearest")
    den = uniform_filter(ok.astype(float), size, mode="nearest")
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(den > 0, num / den, np.nan)


@dataclass(frozen=True)
class SelfCalRule:
    """Flooded forest = forest & height-above-river < ``hand_max_m`` & ΔHH > quantile ``q`` of the reference.

    The reference is forest with height above river > ``ref_hand_min_m`` inside the valley study area
    (distance to the line < ``ref_max_distance_m``), i.e. nearby forest that cannot be flooded.
    """

    q: float = 97.5
    hand_max_m: float = 8.0
    ref_hand_min_m: float = 12.0
    ref_max_distance_m: float = 15000.0
    forest_hv_db: float = -16.0
    min_threshold_db: float = 0.5
    smooth_px: int = 1

    def forest(self, f: PairFeatures) -> np.ndarray:
        return f.valid & (f.hv_dry > self.forest_hv_db)

    def change(self, f: PairFeatures) -> np.ndarray:
        return smooth_nan(f.d_hh, self.smooth_px)

    def threshold_db(self, f: PairFeatures, hand_m: np.ndarray, distance_m: np.ndarray, change=None) -> float:
        change = self.change(f) if change is None else change
        ref = self.forest(f) & (hand_m > self.ref_hand_min_m) & (distance_m < self.ref_max_distance_m)
        if ref.sum() < 500:
            raise ValueError(f"too few reference pixels ({int(ref.sum())}) to calibrate the threshold")
        return max(float(np.nanpercentile(change[ref], self.q)), self.min_threshold_db)

    def apply(self, f: PairFeatures, hand_m: np.ndarray, distance_m: np.ndarray) -> tuple[np.ndarray, float]:
        change = self.change(f)
        t = self.threshold_db(f, hand_m, distance_m, change)
        return self.forest(f) & (hand_m < self.hand_max_m) & (change > t), t

    def to_dict(self) -> dict:
        return {"type": "selfcal_v2", **asdict(self)}


def gauge_supported(chainage_m: np.ndarray, gauge_chainage_m, max_m: float) -> np.ndarray:
    """Truth-confidence rule: True where the nearest gauge (along the valley) is within ``max_m``."""
    g = np.asarray(gauge_chainage_m, float)
    return np.min(np.abs(chainage_m[..., None] - g), axis=-1) <= max_m
