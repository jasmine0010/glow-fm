"""Trust map: where NISAR flooded-forest maps (method v2) can be relied on today, and where they can't.

Accuracy of the frozen v2 detector is scored against gauge + lidar truth for every NISAR pair, split by conditions
that are known *without* truth at mapping time:

- **flood timing** at the nearest gauge: rising, near crest (<= 2 days after), receding (2-6 days), late recession;
- **land cover** (ESA WorldCover 2021): tree cover, herbaceous wetland, cropland/grass/shrub, other;
- **incidence angle** of the NISAR acquisition.

Cells with enough flooded truth get a trust class (green / amber / red) from their CSI and its block-bootstrap
interval; the class can then be painted onto any new map from the same conditions.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import h5py
import numpy as np

from hidden_floods.audit import TruthContext, truth_context
from hidden_floods.detect import PairFeatures, pair_features
from hidden_floods.grid import Grid, warp_to_grid
from hidden_floods.io.dem import dem_on_grid
from hidden_floods.io.gauges import StageSeries, usgs_series
from hidden_floods.io.nisar import read_gcov
from hidden_floods.metrics import block_bootstrap, block_ids, score
from hidden_floods.pipeline import analysis_grid
from hidden_floods.selfcal import SelfCalRule, height_above_river

TIMING = {0: "unknown", 1: "rising", 2: "near crest", 3: "receding", 4: "late recession"}
LANDCOVER = {0: "other", 1: "tree cover", 2: "herbaceous wetland", 3: "crop/grass/shrub"}
INCIDENCE_EDGES = (0.0, 38.0, 42.0, 46.0, 90.0)
TRUST = {0: "insufficient data", 1: "green", 2: "amber", 3: "red"}


def timing_class(series: StageSeries, when: str, lookback_days: float = 10.0, lookahead_days: float = 3.0,
                 rise_tolerance_h: float = 6.0) -> int:
    """Flood timing at a gauge: 1 rising, 2 near crest (<= 2 d after), 3 receding (2-6 d), 4 late recession."""
    t = np.datetime64(when.replace("Z", ""), "s")
    sel = (series.times >= t - np.timedelta64(int(lookback_days * 86400), "s")) & \
          (series.times <= t + np.timedelta64(int(lookahead_days * 86400), "s"))
    if sel.sum() < 10:
        return 0
    crest = series.times[sel][int(np.argmax(series.stage_ft[sel]))]
    dt_h = (t - crest) / np.timedelta64(1, "h")
    if dt_h < -rise_tolerance_h:
        return 1
    days = max(dt_h, 0.0) / 24.0
    return 2 if days <= 2.0 else (3 if days <= 6.0 else 4)


def worldcover_class(codes: np.ndarray) -> np.ndarray:
    """Collapse WorldCover codes: 10 tree -> 1; 90 herbaceous wetland, 95 mangrove -> 2; 20/30/40 -> 3; else 0."""
    out = np.zeros(codes.shape, np.uint8)
    out[codes == 10] = 1
    out[np.isin(codes, (90, 95))] = 2
    out[np.isin(codes, (20, 30, 40))] = 3
    return out


def worldcover_on_grid(tiles_dir: Path, grid: Grid) -> np.ndarray:
    """WorldCover 2021 codes on ``grid`` (nearest), mosaicking every tile in ``tiles_dir``."""
    out = np.zeros(grid.shape, np.uint8)
    for path in sorted(Path(tiles_dir).glob("ESA_WorldCover_10m_2021_v200_*_Map.tif")):
        w = warp_to_grid(path, grid, categorical=True, nodata=0, dtype=np.uint8)
        out = np.where(out == 0, w, out)
    return out


def gcov_incidence_on_grid(path, grid: Grid) -> np.ndarray:
    """Incidence angle (deg) from the GCOV radar-grid cube at the height layer nearest 0 m, nearest-sampled."""
    with h5py.File(path, "r") as h:
        g = h["science/LSAR/GCOV/metadata/radarGrid"]
        k = int(np.abs(g["heightAboveEllipsoid"][:]).argmin())
        inc = g["incidenceAngle"][k]
        gx, gy = g["xCoordinates"][:], g["yCoordinates"][:]
    ci = np.clip(np.searchsorted(gx, grid.xs), 0, len(gx) - 1)
    ri = np.clip(np.searchsorted(-gy, -grid.ys), 0, len(gy) - 1)
    return inc[np.ix_(ri, ci)].astype(np.float32)


@dataclass
class PairEvaluation:
    site: str
    pair: str
    role: str                     # "development" or "held-out"
    grid: Grid
    ctx: TruthContext
    pred: np.ndarray
    threshold_db: float
    timing: np.ndarray            # per-pixel timing class (nearest gauge along the valley)
    landcover: np.ndarray
    incidence: np.ndarray


def evaluate_pair(site, pair_name: str, rule: SelfCalRule, worldcover_dir: Path, role: str) -> PairEvaluation:
    grid = analysis_grid(site)
    pair = site.pairs[pair_name]
    dem = dem_on_grid(site.dem_path, grid)
    ctx = truth_context(site, pair.wet_time, dem=dem, grid=grid)
    f: PairFeatures = pair_features(read_gcov(site.gcov_path(pair.dry), grid), read_gcov(site.gcov_path(pair.wet), grid))
    t = ctx.truth
    hand = height_above_river(dem, t.distance_m, t.chainage_m)
    pred, thr = rule.apply(f, hand, t.distance_m)
    g_chain = np.asarray(ctx.gauge_chainage_m)
    nearest = np.argmin(np.abs(t.chainage_m[..., None] - g_chain), axis=-1)
    classes = np.array([timing_class(usgs_series(site.gauges_dir, g), pair.wet_time) for g in site.gauges], np.uint8)
    return PairEvaluation(site.name, pair_name, role, grid, ctx, pred, thr, classes[nearest],
                          worldcover_class(worldcover_on_grid(worldcover_dir, grid)),
                          gcov_incidence_on_grid(site.gcov_path(pair.wet), grid))


def region_of(ev: PairEvaluation) -> np.ndarray:
    return ev.ctx.supported & ~ev.ctx.permanent_water


def pooled_scores(evals: list[PairEvaluation], cell_of, n_boot: int = 1000, seed: int = 0) -> dict:
    """Pool confusion counts over pairs for each cell label returned by ``cell_of(ev)`` (an int array per pair).

    Intervals: block bootstrap with blocks = (pair, 2 km chainage block), resampled jointly.
    """
    labels = sorted({int(v) for ev in evals for v in np.unique(cell_of(ev)[region_of(ev)])})
    out = {}
    for lab in labels:
        preds, wets, drys, blocks = [], [], [], []
        for i, ev in enumerate(evals):
            m = region_of(ev) & (cell_of(ev) == lab) & (ev.ctx.truth.wet | ev.ctx.truth.dry)
            preds.append(ev.pred[m])
            wets.append(ev.ctx.truth.wet[m])
            drys.append(ev.ctx.truth.dry[m])
            blocks.append(block_ids(ev.ctx.truth.chainage_m[m], 2000.0) + i * 10**6)
        p, w, d, b = (np.concatenate(x) for x in (preds, wets, drys, blocks))
        s = score(p, w, d)
        area = evals[0].grid.pixel_area_ha
        res = {**s.to_dict(area), "truth_wet_ha": float(w.sum() * area)}
        if w.sum() and (p & w).sum() + (p & d).sum():
            res["ci95"] = block_bootstrap(p, w, d, b, n_boot=n_boot, seed=seed)
        out[lab] = res
    return out


def trust_class(cell: dict, min_wet_ha: float = 150.0, green: float = 0.5, red: float = 0.25) -> int:
    """1 green: CSI >= ``green`` and CI lower bound >= ``red``; 3 red: CSI < ``red``; 2 amber otherwise;
    0 when the cell has under ``min_wet_ha`` of flooded truth."""
    if cell.get("truth_wet_ha", 0.0) < min_wet_ha or not np.isfinite(cell.get("csi", np.nan)):
        return 0
    csi, lo = cell["csi"], cell.get("ci95", {}).get("csi", (0.0, 0.0))[0]
    if csi >= green and lo >= red:
        return 1
    return 3 if csi < red else 2
