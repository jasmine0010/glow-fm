import json
from types import SimpleNamespace

import numpy as np
import pytest

from hidden_floods import frozen_v3
from hidden_floods.config import Gauge
from hidden_floods.detect import PairFeatures
from hidden_floods.frozen_v3 import evaluate_frozen_v3, paired_csi_difference
from hidden_floods.v3 import V3OtsuRule, otsu_threshold, peak_stage_wse, score_v3


def test_otsu_splits_two_groups():
    rng = np.random.default_rng(0)
    x = np.concatenate([rng.normal(0.0, 0.4, 5000), rng.normal(3.0, 0.4, 2000)])
    assert 1.0 < otsu_threshold(x) < 2.0


def test_otsu_rule_gates_landcover_height_and_abstains():
    shape = (60, 60)
    rng = np.random.default_rng(1)
    d = rng.normal(0.0, 0.3, shape)
    d[:, :20] += 3.0                                  # flooded strip
    f = PairFeatures(np.zeros(shape), np.full(shape, -12.0), d, np.full(shape, -12.0))
    lc = np.ones(shape, np.uint8)
    lc[:10, :20] = 3                                  # farmland inside the strip: never mapped
    hand = np.zeros(shape)
    timing = np.full(shape, 2, np.uint8)
    timing[50:, :] = 4                                # late recession: abstain
    flooded, mapped, thr = V3OtsuRule(smooth_px=1).apply(f, lc, timing, hand, np.zeros(shape))
    assert 1.0 < thr < 2.5
    assert flooded[20:50, :20].mean() > 0.9 and not flooded[:10, :20].any()
    assert not mapped[50:].any() and not flooded[50:].any() and not flooded[:, 25:].any()


def test_score_v3_reports_coverage_and_drops_ambiguous():
    wet = np.zeros((10, 10), bool)
    wet[:, :5] = True
    dry = ~wet
    mapped = np.ones_like(wet)
    mapped[:, 4] = False                              # one wet column abstained
    flooded = wet & mapped
    flooded[:, 9] = True                              # a "false alarm" column ...
    amb = np.zeros_like(wet)
    amb[:, 9] = True                                  # ... that was flooded at the crest: left out
    s = score_v3(flooded, mapped, wet, dry, np.ones_like(wet), amb)
    assert s.csi == 1.0 and np.isclose(s.coverage, 0.8)
    assert score_v3(flooded, mapped, wet, dry, np.ones_like(wet)).precision < 1.0


def test_peak_window_ignores_a_dry_reference_after_the_flood(tmp_path):
    times = [f"2026-06-{d:02d}T00:00:00+00:00" for d in range(10, 25)]
    stage = [5, 5, 6, 8, 12, 14, 13, 11, 9, 8, 7, 6, 6, 5, 5]   # crest on Jun 15
    (tmp_path / "usgs_1_stage_15min.json").write_text(json.dumps(
        {"features": [{"properties": {"time": t, "value": str(v)}} for t, v in zip(times, stage, strict=True)]}))
    site = SimpleNamespace(gauges=[Gauge("G", "USGS-1", 0, 0, 0.0, 0.0)], gauges_dir=tmp_path)
    after = peak_stage_wse(site, dry_time="2026-08-20T00:00:00Z", wet_time="2026-06-21T00:00:00Z")
    before = peak_stage_wse(site, dry_time="2026-06-17T00:00:00Z", wet_time="2026-06-21T00:00:00Z")
    assert np.isclose(after["G"], 14 * 0.3048) and np.isclose(before["G"], 11 * 0.3048)


def test_paired_csi_difference_sign_and_identity():
    wet = np.zeros((40, 40), bool)
    wet[:, :20] = True
    dry = ~wet
    blocks = np.tile(np.arange(40), (40, 1))
    region = np.ones_like(wet)
    good, bad = wet.copy(), wet.copy()
    bad[:, 15:20] = False
    d = paired_csi_difference(good, bad, wet, dry, blocks, region, n_boot=200)
    assert d["difference"] == pytest.approx(0.25)
    assert d["ci95"][0] >= 0
    same = paired_csi_difference(good, good, wet, dry, blocks, region, n_boot=50)
    assert same["difference"] == 0 and same["ci95"] == (0.0, 0.0)


def test_frozen_v3_refuses_held_out_dev_checks_other_pairs_and_second_runs(tmp_path):
    site = SimpleNamespace(name="yellow")
    with pytest.raises(ValueError, match="held out"):
        evaluate_frozen_v3(site, "004A_oct12", tmp_path, development_check=True)
    with pytest.raises(ValueError, match="not a frozen"):
        evaluate_frozen_v3(site, "076A_oct17", tmp_path)
    (tmp_path / "frozen_v3_metrics.json").write_text("{}")
    with pytest.raises(FileExistsError):
        evaluate_frozen_v3(site, "004A_oct12", tmp_path)


def test_frozen_v3_refuses_when_a_hashed_file_changed(tmp_path, monkeypatch):
    site = SimpleNamespace(name="yellow")
    monkeypatch.setattr(frozen_v3, "check_receipt_v3", lambda _: {"receipt": {}, "changed_since_freeze": ["x.py"]})
    with pytest.raises(RuntimeError, match="not running"):
        evaluate_frozen_v3(site, "004A_oct12", tmp_path)
    assert not list(tmp_path.iterdir())          # nothing logged, nothing read
