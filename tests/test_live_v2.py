"""Protocol v2 for live cases (research/LIVE_PROTOCOL_V2.md): only the height source may change."""

import json

import numpy as np
import pytest

from hidden_floods import live, live_v2
from hidden_floods.config import REPO_ROOT

LIVE = REPO_ROOT / "app" / "data" / "live"
WORLD = sorted(p.parent for p in LIVE.glob("world_*/case.json") if not p.parent.name.endswith(live_v2.SUFFIX))
needs_cases = pytest.mark.skipif(not WORLD, reason="no published world cases")


def test_archive_names():
    assert live_v2.archive_for(16, 108) == "N10E100-N20E110_FABDEM_V1-2.zip"
    assert live_v2.archive_for(23, -110) == "N20W110-N30W100_FABDEM_V1-2.zip"
    assert live_v2.archive_for(-1, -1) == "S10W010-N00E000_FABDEM_V1-2.zip"


def test_heights_to_water_matches_v1_rule():
    dem = np.array([[5.0, 6.0, 9.0], [4.0, 7.0, 8.0]], np.float32)
    water = np.array([[False, False, False], [True, False, False]])
    hand, dist = live_v2.heights_to_water(dem, water)
    assert hand[1, 0] == 0 and hand[0, 0] == pytest.approx(1.0) and hand[1, 2] == pytest.approx(4.0)
    assert dist[1, 0] == 0 and dist[1, 2] == pytest.approx(100.0)
    hand, dist = live_v2.heights_to_water(dem, np.zeros_like(water))
    assert np.isnan(hand).all() and np.isinf(dist).all()


@needs_cases
@pytest.mark.parametrize("folder", WORLD, ids=lambda p: p.name)
def test_grid_rebuilt_from_corners(folder):
    rec = json.loads((folder / "case.json").read_text(encoding="utf8"))
    g = live_v2.grid_of(rec)
    assert g.shape == (rec["layout"]["height"], rec["layout"]["width"])
    assert np.allclose(np.array(live.corners_lonlat(g)), np.array(rec["corners"]), atol=2e-6)


@needs_cases
def test_twin_pack_changes_only_heights(tmp_path):
    folder = WORLD[0]
    rec = json.loads((folder / "case.json").read_text(encoding="utf8"))
    d = live.decode_pack(folder, rec["layout"])
    new = np.where(np.isfinite(d["hand"]), d["hand"] + 1.25, np.nan).astype(np.float32)
    live_v2.replace_heights(folder, rec["layout"], new, tmp_path)
    d2 = live.decode_pack(tmp_path, rec["layout"])
    for name, a in d.items():
        if name == "hand":
            continue
        assert np.array_equal(a, d2[name], equal_nan=True), name
    ok = np.isfinite(d["hand"]) & (np.abs(d["hand"]) < 300)
    assert np.allclose(d2["hand"][ok], d["hand"][ok] + 1.25, atol=0.006)
    assert (tmp_path / "pack.bin").stat().st_size == (folder / "pack.bin").stat().st_size
