"""The bare-earth test's fixed settings and its reading rules, on synthetic numbers only (no elevation data)."""

import numpy as np

from hidden_floods.frozen_bare_earth import (
    GUARD_AREA_RATIO,
    GUARD_SHARE_RATIO,
    HERO,
    P1_MAX_M,
    P2_MIN_PASSES,
    SELF,
    map_checks,
    read_mechanism,
    read_q1,
    read_q2,
    read_q3,
    wet_heights,
)
from hidden_floods.frozen_no_lidar import PASSES


def _row(fab, cop, lidar, fab_map=0.2, ci=(0.01, 0.1), area=(100.0, 100.0), share=(0.5, 0.5), site="x", pair="y", err=(0.5, 4.0), hero_m=0.5):
    m = lambda csi, a=100.0, s=0.5: {"csi": csi, "mapped_ha": a, "labelled_share": s}
    return {"site": site, "pair": pair, "best_limit_csi": fab_map,
            "maps": {"nisar_with_fabdem": m(fab, area[0], share[0]), "nisar_with_copernicus": m(cop), "nisar_with_lidar": m(lidar, area[1], share[1]), "fabdem_height_map": m(fab_map)},
            "q1_fabdem_minus_copernicus": {"ci95": ci}, "q2_nisar_minus_fabdem_map": {"ci95": ci},
            "wet_ground": {"fabdem": {"median_m": hero_m, "median_error_vs_lidar_m": err[0]}, "copernicus": {"median_m": 5.0, "median_error_vs_lidar_m": err[1]}}}


def test_same_passes_and_the_receipt_covers_the_earlier_freezes():
    assert len(PASSES) == 7 and HERO in PASSES
    assert {"research/BARE_EARTH_PROTOCOL.md", "research/bare_earth_tiles.json", "research/freeze_receipt_no_lidar.json"} <= set(SELF)
    assert (P1_MAX_M, P2_MIN_PASSES, GUARD_AREA_RATIO, GUARD_SHARE_RATIO) == (2.0, 5, 1.5, 0.5)


def test_q1_needs_a_clear_gain_on_three_passes_and_no_losses():
    rows = [_row(0.40, 0.30, 0.45) for _ in range(7)]
    assert read_q1(rows)["reading"] == "Supported"
    rows[0]["q1_fabdem_minus_copernicus"]["ci95"] = (-0.2, -0.01)
    assert read_q1(rows)["reading"] == "Partly supported"
    assert read_q1([_row(0.30, 0.30, 0.45, ci=(-0.1, 0.1)) for _ in range(7)])["reading"] == "Not supported"


def test_q1_guard_drops_a_level_when_the_map_grows_or_goes_unchecked():
    big = [_row(0.40, 0.30, 0.45, area=(200.0, 100.0)) for _ in range(7)]
    assert read_q1(big)["guard_triggered"] and read_q1(big)["reading"] == "Partly supported"
    unchecked = [_row(0.40, 0.30, 0.45, share=(0.2, 0.5)) for _ in range(7)]
    assert read_q1(unchecked)["reading"] == "Partly supported"


def test_q2_q3_and_mechanism_readings():
    rows = [_row(0.40, 0.30, 0.45, fab_map=0.2) for _ in range(7)]
    assert read_q2(rows)["reading"] == "Supported"
    assert read_q3(rows)["reading"] == "Small"
    assert read_q3([_row(0.20, 0.30, 0.45) for _ in range(7)])["reading"] == "Large"
    rows[0]["site"], rows[0]["pair"] = HERO
    mech = read_mechanism(rows)
    assert mech["p1_holds"] and mech["p2_holds"] and mech["p2_passes_closer"] == 7


def test_map_checks_and_wet_heights_on_a_tiny_grid():
    pred = np.array([[1, 1, 1, 0]], bool)
    wet, dry, scored = np.array([[1, 0, 0, 1]], bool), np.array([[0, 1, 0, 0]], bool), np.ones((1, 4), bool)
    depth = np.array([[0.5, -1.0, -6.0, 0.2]])
    c = map_checks(pred, wet, dry, scored, depth, 5.0)
    assert c["mapped_ha"] == 0.75 and abs(c["labelled_share"] - 2 / 3) < 1e-9 and c["ha_more_than_5m_above_water"] == 0.25
    h = wet_heights(np.array([[1.0, 9.0, 9.0, 3.0]]), np.array([[0.0, 0.0, 0.0, 0.0]]), wet & scored)
    assert h == {"median_m": 2.0, "median_error_vs_lidar_m": 2.0}
