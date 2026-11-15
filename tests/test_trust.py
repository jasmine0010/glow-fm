import numpy as np

from hidden_floods.io.gauges import StageSeries
from hidden_floods.trust import timing_class, trust_class, worldcover_class


def _series(peak_hour: float, hours: int = 400):
    t = np.datetime64("2026-06-01T00:00", "s") + np.arange(hours) * np.timedelta64(3600, "s")
    stage = 10.0 - np.abs(np.arange(hours) - peak_hour) * 0.01
    return StageSeries(t, stage)


def test_timing_classes():
    s = _series(peak_hour=200)                     # crest at 2026-06-09T08:00
    assert timing_class(s, "2026-06-08T08:00:00Z") == 1   # a day before the crest: rising
    assert timing_class(s, "2026-06-10T08:00:00Z") == 2   # a day after: near crest
    assert timing_class(s, "2026-06-13T08:00:00Z") == 3   # four days after: receding
    assert timing_class(s, "2026-06-16T00:00:00Z") == 4   # ~6.7 days after: late recession


def test_worldcover_collapse():
    codes = np.array([10, 20, 30, 40, 50, 80, 90, 95, 0])
    assert worldcover_class(codes).tolist() == [1, 3, 3, 3, 0, 0, 2, 2, 0]


def test_trust_class_rules():
    assert trust_class({"truth_wet_ha": 50.0, "csi": 0.9}) == 0
    assert trust_class({"truth_wet_ha": 500.0, "csi": 0.8, "ci95": {"csi": (0.7, 0.9)}}) == 1
    assert trust_class({"truth_wet_ha": 500.0, "csi": 0.55, "ci95": {"csi": (0.1, 0.8)}}) == 2
    assert trust_class({"truth_wet_ha": 500.0, "csi": 0.1, "ci95": {"csi": (0.0, 0.2)}}) == 3
