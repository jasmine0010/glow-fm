import numpy as np
import pytest

from hidden_floods.drivers import DriverInputs, response_curve, river_status, summarize, vegetation_status
from hidden_floods.v3 import LC_OPEN, LC_TREE


def scene(n=80):
    """Left half is flooded forest (ground under water, HH up, HV flat); right half is dry forest; bottom row is upland."""
    depth = np.tile(np.linspace(2.0, -4.0, n), (n, 1))
    wet, dry = depth > 0.5, (depth < -0.5) & (depth > -5.0)
    d_hh = np.where(depth > 0, 3.0, 0.0)
    d_hv = np.zeros_like(depth)
    flagged = depth > 0
    lc = np.full(depth.shape, LC_TREE, np.uint8)
    lc[:10, :] = LC_OPEN
    hand = np.clip(-depth, 0, None) + 1.0
    hand[-10:, :] = 20.0
    dist = np.zeros_like(depth)
    return DriverInputs(flagged, wet, dry, depth, d_hh, d_hv, lc, hand, dist, np.ones_like(wet), np.ones_like(wet), 1.5, 2.0)


def test_response_curve_jumps_at_the_water_line_and_drops_thin_bins():
    x = scene()
    curve = response_curve(x.depth, x.d_hh, x.d_hv, np.ones_like(x.wet), min_px=40)
    under = [c for c in curve if c["water_above_ground_m"] > 0]
    over = [c for c in curve if c["water_above_ground_m"] < 0]
    assert all(c["hh_db"] == 3.0 and c["hv_db"] == 0.0 for c in under)
    assert all(c["hh_db"] == 0.0 for c in over)
    assert response_curve(x.depth, x.d_hh, x.d_hv, np.zeros_like(x.wet)) == []


def test_summary_measures_each_explanation():
    x = scene()
    s = summarize(x)
    assert s["share_flagged_below_water"] == pytest.approx(1.0)
    assert s["flagged_hh_db"] == 3.0 and s["flagged_hv_db"] == 0.0
    assert s["upland_hh_db"] == 0.0
    assert s["open_land_bright_ha"] > 0
    assert s["contrast"]["hh_below_water_db"] == 3.0 and s["contrast"]["hh_above_water_db"] == 0.0
    assert s["status"]["river"] == "Best supported"
    assert s["status"]["ponding"] == "Not tested" and s["status"]["human"] == "Not assessed"


@pytest.mark.parametrize(("px", "share", "expected"), [(10, 1.0, "Too little mapped"), (100, None, "Too little mapped"),
                                                       (100, 0.9, "Best supported"), (100, 0.4, "Partly supported"),
                                                       (100, 0.1, "Weak here")])
def test_river_status_rules(px, share, expected):
    assert river_status(px, share) == expected


def test_vegetation_status_needs_a_quiet_upland():
    assert vegetation_status(0.2, 3.0) == "Unlikely"
    assert vegetation_status(0.66, 1.72) == "Cannot rule out"
    assert vegetation_status(0.2, 0.8) == "Cannot rule out"
    assert vegetation_status(None, 3.0) == "Not tested"
