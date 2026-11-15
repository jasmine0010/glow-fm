from types import SimpleNamespace

import numpy as np
import pytest

from hidden_floods import frozen_edouard
from hidden_floods.frozen_edouard import PASSES, WARNING_DB, evaluate_edouard, upland_warning
from hidden_floods.v3 import LC_TREE


def _upland(shift, n=40):
    shape = (n, n)
    return (np.full(shape, shift), np.ones(shape, bool), np.full(shape, LC_TREE, np.uint8), np.full(shape, 20.0), np.zeros(shape))


def test_upland_warning_fires_only_past_the_limit_in_either_direction():
    assert upland_warning(*_upland(WARNING_DB + 0.1))["warned"] is True
    assert upland_warning(*_upland(-WARNING_DB - 0.1))["warned"] is True
    assert upland_warning(*_upland(WARNING_DB))["warned"] is False


def test_upland_warning_says_so_when_it_cannot_be_computed():
    d, v, lc, hand, dist = _upland(1.0)
    hand[:] = 1.0                                 # no ground high enough
    assert upland_warning(d, v, lc, hand, dist) == {"upland_hh_db": None, "upland_px": 0, "warned": None}


def test_refuses_regression_checks_on_held_out_rivers_and_unknown_passes(tmp_path):
    for name in PASSES:
        with pytest.raises(ValueError, match="held out"):
            evaluate_edouard(SimpleNamespace(name=name), PASSES[name][0], tmp_path, regression_check=True)
    with pytest.raises(ValueError, match="not a frozen"):
        evaluate_edouard(SimpleNamespace(name="village_creek"), "076A_oct17", tmp_path)
    with pytest.raises(ValueError, match="own out_dir"):
        evaluate_edouard(SimpleNamespace(name="yellow"), "055D_oct16", None, regression_check=True)


def test_refuses_second_runs_and_changed_files(tmp_path, monkeypatch):
    site = SimpleNamespace(name="village_creek")
    monkeypatch.setattr(frozen_edouard, "check_receipt", lambda: ["x.py"])
    with pytest.raises(RuntimeError, match="not running"):
        evaluate_edouard(site, "134A_sep03", tmp_path)
    assert not list(tmp_path.iterdir())           # nothing logged, nothing read
    (tmp_path / "frozen_edouard_metrics.json").write_text("{}")
    with pytest.raises(FileExistsError):
        evaluate_edouard(site, "134A_sep03", tmp_path)
