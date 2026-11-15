from types import SimpleNamespace

import pytest

from hidden_floods import frozen_v4
from hidden_floods.frozen_v4 import PASSES, evaluate_v4
from hidden_floods.v4 import V4Rule


def test_refuses_regression_checks_on_held_out_rivers_and_unknown_passes(tmp_path):
    for name, pair in PASSES.items():
        with pytest.raises(ValueError, match="held out"):
            evaluate_v4(SimpleNamespace(name=name), pair, [], V4Rule(), tmp_path, regression_check=True)
    with pytest.raises(ValueError, match="not a frozen"):
        evaluate_v4(SimpleNamespace(name="pee_dee"), "other", [], V4Rule(), tmp_path)
    with pytest.raises(ValueError, match="own out_dir"):
        evaluate_v4(SimpleNamespace(name="yellow"), "055D_oct16", [], V4Rule(), None, regression_check=True)


def test_refuses_second_runs_and_changed_files(tmp_path, monkeypatch):
    site = SimpleNamespace(name="pee_dee")
    monkeypatch.setattr(frozen_v4, "check_receipt", lambda: ["x.py"])
    with pytest.raises(RuntimeError, match="not running"):
        evaluate_v4(site, "098D_jul27", [], V4Rule(), tmp_path)
    assert not list(tmp_path.iterdir())           # nothing logged, nothing read
    (tmp_path / "frozen_v4_metrics.json").write_text("{}")
    with pytest.raises(FileExistsError):
        evaluate_v4(site, "098D_jul27", [], V4Rule(), tmp_path)
