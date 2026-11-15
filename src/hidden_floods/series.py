"""Yellow River through time: frozen v3, unchanged, on every usable NISAR pass of the Isaias flood.

These are follow-up scores. Only the Oct 16 pass is the pre-registered frozen test (research/V3_YELLOW_PROTOCOL.md).
Each track keeps the dry reference the protocol's selection rule chose for it. Oct 12 (track 004A) is left out because
the frozen run found no valid radar on any labelled pixel. ``sites/yellow.toml`` is hashed by the freeze receipt, so
the extra scenes are added here instead of being written there.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np

from hidden_floods.audit import truth_context
from hidden_floods.config import Pair, Site, data_root, load_site
from hidden_floods.detect import pair_features
from hidden_floods.io.dem import dem_on_grid
from hidden_floods.io.gauges import usgs_series
from hidden_floods.io.nisar import read_gcov
from hidden_floods.metrics import block_bootstrap, block_ids, score
from hidden_floods.pipeline import analysis_grid
from hidden_floods.selfcal import height_above_river
from hidden_floods.trust import timing_class, worldcover_class, worldcover_on_grid
from hidden_floods.v3 import V3OtsuRule

CHOCT = "../choctawhatchee/"
SERIES_GCOV = {
    "055D_20261004": "NISAR_L2_PR_GCOV_032_055_D_073_4005_DHDH_A_20261004T003648_20261004T003724_P05023_N_F_J_001",
    "076A_20261005": "NISAR_L2_PR_GCOV_032_076_A_017_4005_DHDH_A_20261005T110224_20261005T110258_P05023_N_F_J_001",
    "127D_20261009": "NISAR_L2_PR_GCOV_032_127_D_073_4005_DHDH_A_20261009T002830_20261009T002905_P05023_N_F_J_001",
    "076A_20260923": CHOCT + "NISAR_L2_PR_GCOV_031_076_A_017_4005_DHDH_A_20260923T110224_20260923T110258_P05023_N_F_J_001",
    "076A_20261017": CHOCT + "NISAR_L2_PR_GCOV_033_076_A_017_4005_DHDH_A_20261017T110224_20261017T110259_P05023_N_F_J_001",
    "127D_20260927": CHOCT + "NISAR_L2_PR_GCOV_031_127_D_073_4005_DHDH_A_20260927T002830_20260927T002905_P05023_N_F_J_001",
    "127D_20261021": CHOCT + "NISAR_L2_PR_GCOV_033_127_D_073_4005_DHDH_A_20261021T002830_20261021T002905_P05023_N_F_J_001",
}
SERIES_PAIRS = (
    Pair("055D_oct04", "055D_20261004", "055D_20260922", "2026-10-04T00:36:48Z", "2026-09-22T00:36:49Z"),
    Pair("076A_oct05", "076A_20261005", "076A_20260923", "2026-10-05T11:02:24Z", "2026-09-23T11:02:24Z"),
    Pair("127D_oct09", "127D_20261009", "127D_20260927", "2026-10-09T00:28:30Z", "2026-09-27T00:28:30Z"),
    Pair("055D_oct16", "055D_20261016", "055D_20260922", "2026-10-16T00:36:48Z", "2026-09-22T00:36:49Z"),
    Pair("076A_oct17", "076A_20261017", "076A_20260923", "2026-10-17T11:02:24Z", "2026-09-23T11:02:24Z"),
    Pair("127D_oct21", "127D_20261021", "127D_20260927", "2026-10-21T00:28:30Z", "2026-09-27T00:28:30Z"),
)
FROZEN_FRAME = "055D_oct16"
FT_TO_M = 0.3048


def yellow_series_site() -> Site:
    base = load_site("yellow")
    return replace(base, gcov={**base.gcov, **SERIES_GCOV}, pairs={p.name: p for p in SERIES_PAIRS})


@dataclass(frozen=True)
class Frame:
    pair: str
    time: str
    track: str
    frozen: bool
    threshold_db: float
    timing: list[str]
    stage_rise_m: list[float]
    flagged_ha: float
    confirmed_ha: float
    dry_ha: float
    flagged_on_dry_ha: float
    csi: float | None
    csi_ci95: tuple[float, float] | None
    recall: float | None
    precision: float | None
    coverage: float | None


def score_frame(site: Site, pair: Pair, rule: V3OtsuRule, n_boot: int = 2000, seed: int = 0) -> Frame:
    grid = analysis_grid(site)
    dem = dem_on_grid(site.dem_path, grid)
    ctx = truth_context(site, pair.wet_time, dem=dem, grid=grid)
    t = ctx.truth
    f = pair_features(read_gcov(site.gcov_path(pair.dry), grid), read_gcov(site.gcov_path(pair.wet), grid))
    hand = height_above_river(dem, t.distance_m, t.chainage_m)
    lc = worldcover_class(worldcover_on_grid(data_root() / "worldcover", grid))
    series = [usgs_series(site.gauges_dir, g) for g in site.gauges]
    classes = np.array([timing_class(s, pair.wet_time) for s in series], np.uint8)
    timing = classes[np.argmin(np.abs(t.chainage_m[..., None] - np.asarray(ctx.gauge_chainage_m)), axis=-1)]
    pred, mapped, thr = rule.apply(f, lc, timing, hand, t.distance_m)
    region = ctx.supported & ~ctx.permanent_water
    scored = region & mapped
    s = score(pred, t.wet, t.dry, scored)
    judged = s.tp + s.fn > 0
    area = grid.pixel_area_ha
    ci = None
    if judged:
        ci = block_bootstrap(pred, t.wet, t.dry, block_ids(t.chainage_m, 2000.0), scored, n_boot=n_boot, seed=seed)["csi"]
    wet_region = t.wet & region
    names = ("unknown", "rising", "near crest", "receding", "late recession")
    return Frame(
        pair.name, pair.wet_time, pair.name[:4], pair.name == FROZEN_FRAME, thr, [names[c] for c in classes],
        [round((a.at(pair.wet_time) - a.at(pair.dry_time)) * FT_TO_M, 2) for a in series],
        float((pred & region & t.corridor).sum() * area), float(wet_region.sum() * area), float((t.dry & region).sum() * area),
        float((pred & t.dry & scored).sum() * area), s.csi if judged else None, ci, s.recall if judged else None,
        s.precision if s.tp + s.fp else None, float((wet_region & mapped).sum() / wet_region.sum()) if wet_region.any() else None)
