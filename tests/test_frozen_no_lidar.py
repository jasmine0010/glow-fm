from hidden_floods.frozen_no_lidar import LAND, LIMIT_M, PASSES, SENSITIVITY_M


def test_all_judged_v4_frozen_passes_are_listed_including_the_failures():
    assert len(PASSES) == 7
    assert {r for r, _ in PASSES} >= {"pee_dee", "neuse", "lower_sabine"}


def test_height_map_uses_the_same_rule_as_the_lidar_map():
    assert LIMIT_M == 2.0
    assert LAND == (0, 1, 2)
    assert LIMIT_M in SENSITIVITY_M
