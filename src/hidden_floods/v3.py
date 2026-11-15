"""Method v3 — v2's scene-calibrated change detector plus four targeted fixes from the held-out diagnosis.

1. **Land-cover gate** (ESA WorldCover) instead of the dry-date HV proxy: farmland detections were almost all false
   alarms (precision 0.03), so only tree cover and herbaceous wetland (optionally also "other") are mapped.
2. **Abstention by flood timing**: late recession scored CSI 0.21, so pixels whose nearest gauge is in that state
   (optionally also receding) are reported as "not mapped" instead of guessed. Coverage is always reported with
   accuracy, so abstaining can never hide misses.
3. **Absolute rule** for swamp that was already wet on the dry date (change detection cannot see it): a strong
   flood-date HH with a high HH/HV ratio, the NISAR handbook's double-bounce signature.
4. **Peak-envelope truth** (scoring only): a pixel that is dry at the satellite time but was flooded at the river's
   crest between the dry and wet dates may still hold ponded water, so it is treated as ambiguous and left out,
   rather than scored as a false alarm.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from hidden_floods.detect import PairFeatures
from hidden_floods.io.gauges import usgs_series, water_surface_navd88_m
from hidden_floods.selfcal import smooth_nan
from hidden_floods.truth import hydraulic_truth

LC_TREE, LC_WETLAND, LC_OPEN, LC_OTHER = 1, 2, 3, 0
T_UNKNOWN, T_RISING, T_CREST, T_RECEDING, T_LATE = 0, 1, 2, 3, 4


@dataclass(frozen=True)
class V3Rule:
    q: float = 90.0                       # scene threshold = q-th percentile of the upland-forest reference change
    smooth_px: int = 3
    hand_max_m: float = 6.0               # fixed on physical grounds (see THIRD_EVENT_PROTOCOL.md)
    ref_hand_min_m: float = 12.0
    ref_max_distance_m: float = 15000.0
    min_threshold_db: float = 0.5
    landcover: tuple[int, ...] = (LC_TREE, LC_WETLAND)
    abstain_timing: tuple[int, ...] = (T_LATE,)
    abs_hh_db: float | None = None        # absolute rule off when None
    abs_ratio_db: float | None = None

    def reference(self, f: PairFeatures, lc, hand, dist):
        return f.valid & (lc == LC_TREE) & (hand > self.ref_hand_min_m) & (dist < self.ref_max_distance_m)

    def apply(self, f: PairFeatures, lc: np.ndarray, timing: np.ndarray, hand: np.ndarray, dist: np.ndarray):
        """Returns (flooded, mapped, threshold_db). ``mapped`` = pixels the method commits to (not abstained)."""
        change = smooth_nan(f.d_hh, self.smooth_px)
        ref = self.reference(f, lc, hand, dist)
        if ref.sum() < 500:
            raise ValueError(f"too few reference pixels ({int(ref.sum())})")
        thr = max(float(np.nanpercentile(change[ref], self.q)), self.min_threshold_db)
        eligible = f.valid & np.isin(lc, self.landcover) & (hand < self.hand_max_m)
        flooded = eligible & (change > thr)
        if self.abs_hh_db is not None:
            flooded |= eligible & (f.hh_wet > self.abs_hh_db) & (f.ratio_wet > self.abs_ratio_db)
        mapped = ~np.isin(timing, self.abstain_timing)
        return flooded & mapped, mapped, thr

    def to_dict(self) -> dict:
        d = asdict(self)
        d["landcover"], d["abstain_timing"] = list(self.landcover), list(self.abstain_timing)
        return {"type": "v3", **d}


def peak_stage_wse(site, dry_time: str, wet_time: str, lookback_days: float = 10.0) -> dict[str, float]:
    """Highest water surface (NAVD88 m) at each gauge in the ``lookback_days`` before the wet acquisition.

    The window never reaches back past a dry reference that came *before* the flood; a dry reference taken after the
    flood (as at Pearl and Tangipahoa) does not limit it.
    """
    t1 = np.datetime64(wet_time.replace("Z", ""), "s")
    t0 = t1 - np.timedelta64(int(lookback_days * 86400), "s")
    td = np.datetime64(dry_time.replace("Z", ""), "s")
    if td < t1:
        t0 = max(t0, td)
    out = {}
    for g in site.gauges:
        s = usgs_series(site.gauges_dir, g)
        m = (s.times >= t0) & (s.times <= t1)
        out[g.name] = water_surface_navd88_m(g, float(s.stage_ft[m].max()))
    return out


def peak_envelope_wet(site, grid, dem, line, channel, wse_peak: dict[str, float]) -> np.ndarray:
    """Pixels hydraulically flooded at the crest water surface (same truth rules as the instant truth)."""
    gxy = [grid.to_xy(g.lon, g.lat) for g in site.gauges]
    t = hydraulic_truth(grid, dem, line, gxy, [wse_peak[g.name] for g in site.gauges], site.corridor_m,
                        site.margin_m, site.max_dry_height_m, channel_seeds=channel)
    return t.wet


@dataclass
class Scored:
    csi: float
    recall: float
    precision: float
    coverage: float        # share of confirmed flooding inside the mapped area
    wet_ha: float

    def to_dict(self):
        return asdict(self)


def score_v3(flooded, mapped, wet, dry, region, ambiguous=None, pixel_ha: float = 0.25) -> Scored:
    """Accuracy on the mapped area, plus coverage. ``ambiguous`` pixels (dry now, flooded at crest) are left out."""
    dry_ok = dry & ~ambiguous if ambiguous is not None else dry
    w, d = wet & region, dry_ok & region
    wm, dm = w & mapped, d & mapped
    tp, fn, fp = (flooded & wm).sum(), (~flooded & wm).sum(), (flooded & dm).sum()
    nan = float("nan")
    return Scored(csi=tp / (tp + fn + fp) if tp + fn + fp else nan, recall=tp / (tp + fn) if tp + fn else nan,
                  precision=tp / (tp + fp) if tp + fp else nan, coverage=wm.sum() / w.sum() if w.sum() else nan,
                  wet_ha=float(w.sum() * pixel_ha))


def otsu_threshold(x: np.ndarray, bins: int = 256) -> float:
    """Otsu's split of a 1-D sample (clipped to its 0.5-99.5 percentiles): the value that best separates two groups."""
    x = x[np.isfinite(x)]
    lo, hi = np.percentile(x, [0.5, 99.5])
    h, e = np.histogram(np.clip(x, lo, hi), bins=bins, range=(lo, hi))
    c = (e[:-1] + e[1:]) / 2
    w0 = np.cumsum(h)
    w1 = w0[-1] - w0
    s0 = np.cumsum(h * c)
    m0 = s0 / np.maximum(w0, 1)
    m1 = (s0[-1] - s0) / np.maximum(w1, 1)
    return float(c[np.argmax(w0 * w1 * (m0 - m1) ** 2)])


@dataclass(frozen=True)
class V3OtsuRule:
    """v3 with a threshold set by Otsu's split of the valley-floor change (adapts to how strong the flood signal is).

    No continuous parameter is tuned: the change is smoothed 3x3, the valley floor is forest/wetland (land-cover
    gate) under ``hand_max_m`` within ``valley_m`` of the line, and the split is floored at ``min_threshold_db``.
    """

    smooth_px: int = 3
    hand_max_m: float = 6.0
    valley_m: float = 4000.0
    min_threshold_db: float = 0.5
    landcover: tuple[int, ...] = (LC_TREE, LC_WETLAND, LC_OTHER)
    abstain_timing: tuple[int, ...] = (T_LATE,)

    def apply(self, f: PairFeatures, lc: np.ndarray, timing: np.ndarray, hand: np.ndarray, dist: np.ndarray):
        change = smooth_nan(f.d_hh, self.smooth_px)
        eligible = f.valid & np.isin(lc, self.landcover) & (hand < self.hand_max_m)
        floor = eligible & (dist < self.valley_m)
        if floor.sum() < 500:
            raise ValueError(f"too few valley-floor pixels ({int(floor.sum())})")
        thr = max(otsu_threshold(change[floor]), self.min_threshold_db)
        mapped = ~np.isin(timing, self.abstain_timing)
        return eligible & (change > thr) & mapped, mapped, thr

    def to_dict(self) -> dict:
        d = asdict(self)
        d["landcover"], d["abstain_timing"] = list(self.landcover), list(self.abstain_timing)
        return {"type": "v3_otsu", **d}
