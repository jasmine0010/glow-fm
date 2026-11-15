import numpy as np

from hidden_floods.detect import AbsoluteRule, ChangeRule, CombinedRule, PairFeatures, to_db
from hidden_floods.grid import Grid
from hidden_floods.metrics import block_bootstrap, block_ids, score, sweep_threshold
from hidden_floods.truth import ValleyLine, connected_to_channel, hydraulic_truth, interpolate_wse, refine_centerline


def _features(**kw):
    base = {k: np.zeros((2, 2)) for k in ("hh_dry", "hv_dry", "hh_wet", "hv_wet")}
    base.update(kw)
    return PairFeatures(**base)


def test_to_db_and_change_rule():
    assert np.isclose(to_db(np.array([0.1]))[0], -10.0)
    f = _features(hh_dry=np.full((2, 2), -8.0), hv_dry=np.array([[-12.0, -12.0], [-20.0, -12.0]]),
                  hh_wet=np.array([[-5.0, -7.0], [-2.0, np.nan]]), hv_wet=np.full((2, 2), -12.0))
    out = ChangeRule(2.0, -16.0).apply(f)
    # +3 dB in forest -> flagged; +1 dB -> not; +6 dB but non-forest -> not; NaN -> not
    assert out.tolist() == [[True, False], [False, False]]


def test_absolute_and_combined_rules():
    f = _features(hh_dry=np.full((1, 2), -4.0), hv_dry=np.full((1, 2), -12.0),
                  hh_wet=np.array([[-4.0, -4.0]]), hv_wet=np.array([[-12.0, -6.0]]))
    absolute = AbsoluteRule(hh_db=-6.0, ratio_db=5.0)
    assert absolute.apply(f).tolist() == [[True, False]]
    assert CombinedRule(ChangeRule(2.0), absolute).apply(f).tolist() == [[True, False]]


def test_valley_projection_on_straight_line():
    line = ValleyLine(np.array([0.0, 0.0]), np.array([1000.0, 0.0]))  # runs south along x = 0
    d, s = line.project(np.array([30.0, -50.0]), np.array([900.0, 250.0]))
    assert np.allclose(d, [30.0, 50.0]) and np.allclose(s, [100.0, 750.0])


def test_interpolate_wse_between_gauges():
    assert np.allclose(interpolate_wse(np.array([0, 50, 100, 150]), [0, 100], [10.0, 4.0]), [10.0, 7.0, 4.0, 4.0])


def test_connected_to_channel_drops_isolated_ponds():
    below = np.zeros((5, 7), bool)
    below[:, 0:2] = True       # river corridor
    below[2, 5] = True         # isolated depression
    seeds = np.zeros_like(below)
    seeds[:, 0] = True
    out = connected_to_channel(below, seeds)
    assert out[:, :2].all() and not out[2, 5]


def test_hydraulic_truth_on_synthetic_valley():
    grid = Grid("EPSG:32616", 0.0, 1000.0, 50.0, 20, 20)
    X, _ = grid.meshgrid()
    dem = 2.0 + 0.01 * np.abs(X - 500.0)              # V-shaped valley, floor 2 m on x = 500
    line = ValleyLine(np.array([500.0, 500.0]), np.array([1000.0, 0.0]))
    t = hydraulic_truth(grid, dem, line, gauge_xy=[(500.0, 1000.0), (500.0, 0.0)], gauge_wse_m=[4.0, 4.0],
                        corridor_m=600.0, margin_m=0.5, max_dry_height_m=5.0)
    # water at 4 m: flooded where ground < 3.5 m (|x-500| < 150), dry where ground in (4.5, 9) m (250 < |x-500| < 500)
    row = t.wet[10]
    assert row[grid.xs.tolist().index(525.0)] and not row[grid.xs.tolist().index(675.0)]
    assert t.dry[10][grid.xs.tolist().index(825.0)]
    assert not (t.wet & t.dry).any()


def test_refine_centerline_moves_to_channel():
    grid = Grid("EPSG:32616", 0.0, 10000.0, 50.0, 200, 200)
    channel = np.zeros(grid.shape, bool)
    channel[:, np.argmin(np.abs(grid.xs - 6000.0))] = True     # channel on x = 6000; coarse line on x = 5000
    coarse = ValleyLine(np.array([5000.0, 5000.0]), np.array([10000.0, 0.0]))
    fine = refine_centerline(coarse, channel, grid, search_m=1500.0, step_m=500.0, smooth=0)
    assert np.allclose(fine.x[3:-3], grid.xs[np.argmin(np.abs(grid.xs - 6000.0))])


def test_scores_bootstrap_and_sweep():
    rng = np.random.default_rng(1)
    wet = np.zeros((40, 40), bool)
    wet[:, :20] = True
    dry = ~wet
    score_map = np.where(wet, 3.0, 0.0) + rng.normal(0, 0.8, wet.shape)
    pred = score_map > 1.5
    s = score(pred, wet, dry)
    assert s.tp + s.fn == wet.sum() and s.fp + s.tn == dry.sum()
    chain = np.repeat(np.arange(40)[:, None] * 100.0, 40, axis=1)
    ci = block_bootstrap(pred, wet, dry, block_ids(chain, 500.0), n_boot=300)
    assert ci["csi"][0] <= s.csi <= ci["csi"][1]
    rows, best = sweep_threshold(score_map, np.ones_like(wet), wet, dry, None, [0.5, 1.5, 2.5])
    assert best == 1.5 and len(rows) == 3
