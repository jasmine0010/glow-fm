"""Physical drivers: what could explain the radar change on a pass, and what the data says about each explanation.

The response curve is the core test. The radar and the water level come from independent instruments, so a jump in HH
where the gauge water surface passes above the lidar ground supports river flooding as the driver. HH rising while HV
stays flat is the double-bounce signature of water under trunks. Rules for each status are fixed here, in code, and
apply to every pass. Explanations this data cannot test are reported as not tested.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass

import numpy as np

from hidden_floods.selfcal import smooth_nan
from hidden_floods.v3 import LC_OPEN, LC_TREE

BIN_EDGES_M = tuple(float(x) for x in np.arange(-5.0, 3.01, 0.5))
MIN_BIN_PX = 40            # 10 ha on the 50 m grid
MIN_FLAGGED_PX = 40
PIXEL_HA = 0.25


def _median(x: np.ndarray, mask: np.ndarray) -> float | None:
    v = x[mask]
    v = v[np.isfinite(v)]
    return float(np.median(v)) if v.size else None


def response_curve(depth, d_hh, d_hv, mask, edges=BIN_EDGES_M, min_px: int = MIN_BIN_PX) -> list[dict]:
    """Median HH and HV change in bins of water surface minus ground. Thin bins are left out rather than drawn."""
    out = []
    for lo, hi in itertools.pairwise(edges):
        m = mask & (depth >= lo) & (depth < hi)
        if m.sum() >= min_px:
            out.append({"water_above_ground_m": (lo + hi) / 2, "hh_db": _median(d_hh, m), "hv_db": _median(d_hv, m),
                        "ha": float(m.sum() * PIXEL_HA)})
    return out


@dataclass(frozen=True)
class DriverInputs:
    flagged: np.ndarray        # the map's flooded pixels
    wet: np.ndarray            # truth labels
    dry: np.ndarray
    depth: np.ndarray          # water surface minus ground (m); NaN outside the corridor
    d_hh: np.ndarray
    d_hv: np.ndarray
    landcover: np.ndarray
    hand: np.ndarray
    dist: np.ndarray
    valid: np.ndarray
    region: np.ndarray         # gauge-supported, inside the corridor, not permanent water
    threshold_db: float
    largest_gauge_rise_m: float | None
    smooth_px: int = 3
    hand_max_m: float = 6.0
    valley_m: float = 4000.0
    upland_hand_min_m: float = 12.0
    upland_max_distance_m: float = 15000.0
    signal: np.ndarray | None = None   # what the map thresholds, if not plain HH change


def river_status(flagged_labelled_px: int, share_below_water: float | None) -> str:
    if flagged_labelled_px < MIN_FLAGGED_PX or share_below_water is None:
        return "Too little mapped"
    if share_below_water >= 0.7:
        return "Best supported"
    return "Partly supported" if share_below_water >= 0.3 else "Weak here"


def vegetation_status(upland_hh_db: float | None, flagged_hh_db: float | None) -> str:
    if upland_hh_db is None or flagged_hh_db is None:
        return "Not tested"
    return "Unlikely" if abs(upland_hh_db) <= 0.5 and flagged_hh_db - upland_hh_db >= 1.0 else "Cannot rule out"


def summarize(x: DriverInputs) -> dict:
    """Numbers and a status for each explanation on one pass."""
    flagged = x.flagged & x.valid
    on_wet = int((flagged & x.wet & x.region).sum())
    on_dry = int((flagged & x.dry & x.region).sum())
    labelled = on_wet + on_dry
    share = on_wet / labelled if labelled else None
    flagged_region = flagged & x.region
    flagged_hh, flagged_hv = _median(x.d_hh, flagged_region), _median(x.d_hv, flagged_region)

    tree = x.valid & (x.landcover == LC_TREE)
    upland = tree & (x.hand > x.upland_hand_min_m) & (x.dist < x.upland_max_distance_m)
    upland_hh, upland_hv = _median(x.d_hh, upland), _median(x.d_hv, upland)

    change = smooth_nan(x.d_hh if x.signal is None else x.signal, x.smooth_px)
    open_floor = x.valid & (x.landcover == LC_OPEN) & (x.hand < x.hand_max_m) & (x.dist < x.valley_m)
    open_bright_ha = float((open_floor & (change > x.threshold_db)).sum() * PIXEL_HA)

    in_curve = tree & x.region & np.isfinite(x.depth)
    above = in_curve & (x.depth >= -3.0) & (x.depth < -1.0)
    below = in_curve & (x.depth >= 0.5) & (x.depth < 2.0)
    return {
        "curve": response_curve(x.depth, x.d_hh, x.d_hv, in_curve),
        "contrast": {"hh_above_water_db": _median(x.d_hh, above), "hv_above_water_db": _median(x.d_hv, above),
                     "hh_below_water_db": _median(x.d_hh, below), "hv_below_water_db": _median(x.d_hv, below)},
        "flagged_ha": float(flagged_region.sum() * PIXEL_HA),
        "flagged_hh_db": flagged_hh, "flagged_hv_db": flagged_hv,
        "share_flagged_below_water": share, "flagged_on_dry_ha": on_dry * PIXEL_HA,
        "upland_hh_db": upland_hh, "upland_hv_db": upland_hv,
        "open_land_bright_ha": open_bright_ha, "largest_gauge_rise_m": x.largest_gauge_rise_m,
        "status": {"river": river_status(labelled, share), "vegetation": vegetation_status(upland_hh, flagged_hh),
                   "ponding": "Not tested", "farmland": "Filtered out", "human": "Not assessed"},
    }
