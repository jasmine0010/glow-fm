import numpy as np

from hidden_floods.detect import PairFeatures
from hidden_floods.selfcal import SelfCalRule, channel_profile, gauge_supported, height_above_river, smooth_nan


def test_channel_profile_is_non_increasing_and_hand_is_relative():
    chain = np.repeat(np.arange(0, 10000, 100.0)[:, None], 5, axis=1)
    dist = np.tile(np.array([0.0, 100.0, 1000.0, 2000.0, 3000.0]), (100, 1))
    dem = 10.0 - chain / 1000.0 + dist / 500.0      # river falls 1 m/km; banks rise away from the line
    _, elev = channel_profile(dem, dist, chain)
    assert np.all(np.diff(elev) <= 1e-9)
    hand = height_above_river(dem, dist, chain)
    # bank 2 km from the line sits ~4 m above the river; 1 km percentile bins bias this by under 1 m
    assert np.allclose(hand[10:-10, 3], 4.0, atol=1.0) and hand[50, 4] > hand[50, 1]


def test_smooth_nan_ignores_nan():
    a = np.ones((5, 5))
    a[2, 2] = np.nan
    assert np.allclose(smooth_nan(a, 3), 1.0)


def test_selfcal_threshold_comes_from_reference_and_flags_floodplain():
    rng = np.random.default_rng(0)
    shape = (60, 60)
    hv = np.full(shape, -12.0)
    d = rng.normal(0.0, 0.5, shape)
    hand = np.full(shape, 20.0)          # upland reference everywhere ...
    hand[:, :20] = 1.0                   # ... except a floodplain strip
    d[:, :20] += 2.0                     # which brightened
    f = PairFeatures(np.zeros(shape), hv, d, hv)
    rule = SelfCalRule(q=90.0, hand_max_m=6.0, smooth_px=1)
    pred, thr = rule.apply(f, hand, np.zeros(shape))
    assert 0.5 <= thr < 1.2
    assert pred[:, :20].mean() > 0.9 and not pred[:, 20:].any()


def test_gauge_supported():
    chain = np.array([0.0, 5000.0, 15000.0, 30000.0])
    assert gauge_supported(chain, [0.0, 30000.0], 10000.0).tolist() == [True, True, False, True]
