"""Method v4 candidate: ask whether a flood is present, choose the radar signal for the scene, and compare with a per-pixel baseline.

Three changes from v3, each aimed at a measured failure (research/MODEL_IDEAS.md):

1. **Confidence check.** Low valley forest should have brightened more than higher valley forest. If not, the map is
   labelled low confidence. Otsu alone always finds a split, even with no flood. Development found that using this as
   a hard gate (``flood_check_db``) blanks real, weak floods and lowers scores, so by default it only labels the pass.
2. **Scene-adaptive signal.** Double bounce raises HH far more than HV, while wetting raises both. When higher valley
   ground has brightened, the map uses HH change minus HV change instead of HH change.
3. **Multi-date baseline.** The dry reference is the per-pixel median of same-track scenes, not one date.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from hidden_floods.selfcal import smooth_nan
from hidden_floods.v3 import LC_OTHER, LC_TREE, LC_WETLAND, T_LATE, otsu_threshold

MIN_BASELINE_SCENES = 3
LOW_MAX_M, HIGH_MIN_M, HIGH_MAX_M = 2.0, 4.0, 8.0
MIN_CHECK_PX = 200


def median_baseline(stack_db: np.ndarray, min_scenes: int = MIN_BASELINE_SCENES) -> np.ndarray:
    """Per-pixel median over scenes (axis 0), NaN where fewer than ``min_scenes`` have a value."""
    with np.errstate(invalid="ignore"):
        out = np.nanmedian(stack_db, axis=0)
    out[np.isfinite(stack_db).sum(axis=0) < min_scenes] = np.nan
    return out


def valley_shift(d_hh, landcover, hand, dist, valley_m: float = 4000.0) -> dict:
    """Median HH change on low and on higher valley forest. Needs no gauge and no truth."""
    tree = np.isfinite(d_hh) & (landcover == LC_TREE) & (dist < valley_m)
    low, high = tree & (hand < LOW_MAX_M), tree & (hand > HIGH_MIN_M) & (hand < HIGH_MAX_M)
    if low.sum() < MIN_CHECK_PX or high.sum() < MIN_CHECK_PX:
        return {"low_db": None, "high_db": None, "low_minus_high_db": None}
    a, b = float(np.median(d_hh[low])), float(np.median(d_hh[high]))
    return {"low_db": a, "high_db": b, "low_minus_high_db": a - b}


@dataclass(frozen=True)
class V4Rule:
    baseline: str = "median"            # "single" or "median"
    signal: str = "adaptive"            # "hh", "hh_minus_hv" or "adaptive"
    flood_check_db: float | None = None # hard gate on low-minus-high; None maps every pass
    confidence_db: float = 0.5          # low-minus-high above this: high confidence
    wet_scene_db: float = 0.5           # higher valley ground brighter than this: use HH minus HV
    smooth_px: int = 3
    hand_max_m: float = 6.0
    valley_m: float = 4000.0
    min_threshold_db: float = 0.5
    landcover: tuple[int, ...] = (LC_TREE, LC_WETLAND, LC_OTHER)
    abstain_timing: tuple[int, ...] = (T_LATE,)

    def apply(self, d_hh, d_hv, landcover, timing, hand, dist) -> dict:
        """``d_hh`` and ``d_hv`` are changes (dB) from the chosen baseline, before smoothing."""
        shift = valley_shift(smooth_nan(d_hh, self.smooth_px), landcover, hand, dist, self.valley_m)
        mapped = ~np.isin(timing, self.abstain_timing)
        use_ratio = self.signal == "hh_minus_hv" or (self.signal == "adaptive" and shift["high_db"] is not None and shift["high_db"] > self.wet_scene_db)
        change = smooth_nan(d_hh - d_hv if use_ratio else d_hh, self.smooth_px)
        eligible = np.isfinite(change) & np.isin(landcover, self.landcover) & (hand < self.hand_max_m)
        floor = eligible & (dist < self.valley_m)
        if floor.sum() < 500:
            raise ValueError(f"too few valley-floor pixels ({int(floor.sum())})")
        thr = max(otsu_threshold(change[floor]), self.min_threshold_db)
        flood_found = self.flood_check_db is None or (shift["low_minus_high_db"] is not None and shift["low_minus_high_db"] > self.flood_check_db)
        pred = eligible & (change > thr) & mapped if flood_found else np.zeros(change.shape, bool)
        confident = shift["low_minus_high_db"] is not None and shift["low_minus_high_db"] > self.confidence_db
        return {"pred": pred, "mapped": mapped, "threshold_db": thr, "flood_found": bool(flood_found), "confident": bool(confident),
                "used_hh_minus_hv": bool(use_ratio), **shift}

    def to_dict(self) -> dict:
        d = asdict(self)
        d["landcover"], d["abstain_timing"] = list(self.landcover), list(self.abstain_timing)
        return {"type": "v4", **d}
