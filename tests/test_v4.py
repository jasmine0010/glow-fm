import numpy as np
import pytest

from hidden_floods.stack import BLOCK, RangeFile, parse
from hidden_floods.v3 import LC_OPEN, LC_TREE, T_LATE
from hidden_floods.v4 import V4Rule, median_baseline, valley_shift


def scene(n=100, flood=3.0, wetting=0.0):
    """Top half is low ground with flooding on its left half. Bottom half is higher ground. Wetting raises HH and HV."""
    rng = np.random.default_rng(0)
    hand = np.full((n, n), 5.0)
    hand[: n // 2, :] = 1.0
    d_hh = rng.normal(wetting, 0.2, (n, n))
    d_hv = rng.normal(wetting, 0.2, (n, n))
    d_hh[: n // 2, : n // 2] += flood
    lc = np.full((n, n), LC_TREE, np.uint8)
    return d_hh, d_hv, lc, np.full((n, n), 2, np.uint8), hand, np.zeros((n, n))


def test_median_baseline_ignores_one_flooded_date_and_needs_enough_scenes():
    stack = np.stack([np.full((2, 2), v, float) for v in (-5.0, -5.0, 9.0)])
    stack[1:, 1, 1] = np.nan                       # this pixel has one good date only
    out = median_baseline(stack)
    assert out[0, 0] == -5.0
    assert np.isnan(out[1, 1])


def test_flood_check_finds_a_flood_and_declines_when_there_is_none():
    found = V4Rule(signal="hh", flood_check_db=0.5).apply(*scene(flood=3.0))
    assert found["flood_found"] and found["pred"][:50, :50].mean() > 0.9 and not found["pred"][:50, 55:].any()
    none = V4Rule(signal="hh", flood_check_db=0.5).apply(*scene(flood=0.0))
    assert not none["flood_found"] and not none["pred"].any()
    off = V4Rule(signal="hh", flood_check_db=None).apply(*scene(flood=0.0))
    assert off["flood_found"]


def test_default_rule_labels_low_confidence_but_still_maps():
    weak = V4Rule(signal="hh").apply(*scene(flood=0.0))
    assert weak["flood_found"] and not weak["confident"]
    strong = V4Rule(signal="hh").apply(*scene(flood=3.0))
    assert strong["confident"] and strong["pred"].any()


def test_adaptive_signal_switches_when_higher_ground_has_brightened():
    wet = V4Rule(signal="adaptive", flood_check_db=None).apply(*scene(wetting=2.0))
    assert wet["used_hh_minus_hv"] and wet["pred"][:50, :50].mean() > 0.9 and wet["pred"][60:, :].mean() < 0.01
    clean = V4Rule(signal="adaptive", flood_check_db=None).apply(*scene(wetting=0.0))
    assert not clean["used_hh_minus_hv"]


def test_gates_and_abstention_still_apply():
    d_hh, d_hv, lc, timing, hand, dist = scene()
    lc[:10, :] = LC_OPEN
    timing[20:30, :] = T_LATE
    r = V4Rule(signal="hh", flood_check_db=None).apply(d_hh, d_hv, lc, timing, hand, dist)
    assert not r["pred"][:10].any() and not r["pred"][20:30].any() and not r["mapped"][20:30].any()


def test_valley_shift_reports_when_it_cannot_be_computed():
    d_hh, _, lc, _, hand, dist = scene()
    assert valley_shift(d_hh, lc, np.full(hand.shape, 1.0), dist)["low_minus_high_db"] is None


class FakeRange(RangeFile):
    def __init__(self, data):
        self.data, self.requests = data, 0
        super().__init__("http://example.invalid/file", size=len(data))

    def _get(self, start, end):
        self.requests += 1
        return self.data[start:end + 1], f"bytes {start}-{end}/{len(self.data)}"


def test_range_file_reads_across_blocks_and_reuses_them():
    data = bytes(range(256)) * ((BLOCK * 2 + 500) // 256)
    f = FakeRange(data)
    f.seek(BLOCK - 10)
    assert f.read(20) == data[BLOCK - 10:BLOCK + 10]
    assert f.requests == 2
    f.seek(BLOCK - 5)
    assert f.read(5) == data[BLOCK - 5:BLOCK]
    assert f.requests == 2
    assert f.seek(0, 2) == len(data) and f.read(10) == b""


@pytest.mark.parametrize(("name", "track", "frame", "when"), [
    ("NISAR_L2_PR_GCOV_029_134_A_017_4005_DHDH_A_20260903T113542_20260903T113616_P05023_N_F_J_001", "134A", "017", "2026-09-03T11:35:42Z"),
    ("NISAR_L2_PR_GCOV_031_004_A_017_4005_DHDH_A_20260918T111043_20260918T111118_P05023_F_F_J_001", "004A", "017", "2026-09-18T11:10:43Z"),
])
def test_parse_granule_names(name, track, frame, when):
    p = parse(name)
    assert (p["track"], p["frame"], p["time"], p["mode"]) == (track, frame, when, "4005_DHDH")
